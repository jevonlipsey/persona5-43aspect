"""offline model and patch checks for the p5r 4:3 ui transform.

the 2d context (21f010) maps ui canvas coordinates straight to screen pixels:
  screen_x = x * (render_w / 1920)
  screen_y = y * (render_h / 1080)
on a 1280x960 render that is 1280x960 on screen: the 1920x1080 canvas fills
the 4:3 display and nothing is left over.

ui_uniform (t2-t4) rewrote the y scale to render_w/1920 instead, so the canvas
was only 720px tall and anchored at the top. the event film overlay also draws
a 1280x720 tint quad in screen space, so its bottom 240px is left untinted.
both edges land on y=720: that is the band and the 16:9 frame line seen in the
t3 screenshots. t5 drops ui_uniform and retargets the film quad height to 960
(film43), so the ui fills and the overlay covers the whole screen.

usage: python3 -I tools/ui_harness.py [exe] [--report]
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
from sigscan import sections, rva2off

CANVAS_W = 1920.0
CANVAS_H = 1080.0
RENDER_W = 1280.0
RENDER_H = 960.0

F_1_1920 = 0x199d704
F_1_1080 = 0x199d728
F_1920 = 0x19a1730
F_960 = 0x19a0fd8
F_1440 = 0x18baaa0
F_720 = 0x187cc74
F_720_FILM = 0x19a0b98
F_075 = 0x199e3f8
F_4_3 = 0x199e8e0

CAVE = 0x17fef080
XTEXT_HDR_VSIZE = 0x398 + 8

UI_CVT_INIT = 0x1a4514
UI_MUL_INIT = 0x1a4529
UI_CVT_RESIZE = 0x1a1b10
UI_MUL_RESIZE = 0x1a1b1d

CVT_ORIG_INIT = bytes.fromhex('f3490f2ac5')
CVT_UNIFORM_INIT = bytes.fromhex('f3490f2ac4')
CVT_ORIG_RESIZE = bytes.fromhex('f3480f2ac0')
CVT_UNIFORM_RESIZE = bytes.fromhex('f3490f2ac5')


def scale(mode, w=RENDER_W, h=RENDER_H):
    """2d scale factors for a ui mode and render size."""
    sx = w / CANVAS_W
    sy = (w / CANVAS_W) if mode == 'ui_uniform' else (h / CANVAS_H)
    return sx, sy


def canvas_px(mode, w=RENDER_W, h=RENDER_H):
    """on-screen size of the full 1920x1080 canvas."""
    sx, sy = scale(mode, w, h)
    return CANVAS_W * sx, CANVAS_H * sy


def bottom_band(mode, w=RENDER_W, h=RENDER_H):
    return h - canvas_px(mode, w, h)[1]


def test_model():
    print('=== ui transform model (1280x960 render) ===')
    for mode in ('fill', 'ui_uniform'):
        sx, sy = scale(mode)
        cw, ch = canvas_px(mode)
        print(f'  {mode:10s} scale {sx:.4f} x {sy:.4f}  canvas {cw:.0f}x{ch:.0f}  bottom band {bottom_band(mode):.0f}px')
    assert bottom_band('fill') == 0.0, 'fill mode must cover the screen'
    assert bottom_band('ui_uniform') == 240.0, 'ui_uniform must leave a 240px band'
    # the t3 screenshots show ui bottoms at y=720 and the frame line at 720
    assert CANVAS_H * scale('ui_uniform')[1] == 720.0
    assert CANVAS_H * scale('fill')[1] == 960.0
    print('  model OK: t5 fills, ui_uniform leaves the 240px band seen in t3')


class Pe:
    def __init__(self, path):
        self.path = path
        self.d = open(path, 'rb').read()
        self.secs = sections(self.d)

    def off(self, rva):
        return rva2off(self.secs, rva)

    def u32(self, rva):
        o = self.off(rva)
        return struct.unpack_from('<I', self.d, o)[0]

    def f32(self, rva):
        o = self.off(rva)
        return struct.unpack_from('<f', self.d, o)[0]

    def bytes(self, rva, n):
        o = self.off(rva)
        return self.d[o:o + n]

    def raw(self, off, n):
        return self.d[off:off + n]

    def mul_target(self, site, length):
        """rip target of an 8-byte mulss [rip+disp32] at site."""
        b = self.bytes(site, length)
        assert b[:4] == bytes.fromhex('f30f5905'), f'{site:#x}: not mulss: {b.hex()}'
        disp = struct.unpack_from('<i', b, 4)[0]
        return site + length + disp

    def riprel_target(self, site, length, disp_off):
        """rip target of a rip-relative instruction with disp at disp_off."""
        disp = struct.unpack_from('<i', self.bytes(site, length), disp_off)[0]
        return site + length + disp


def check_constants(pe):
    print('\n=== shared constants ===')
    for addr, want in ((F_1_1920, 1 / 1920), (F_1_1080, 1 / 1080), (F_1920, 1920.0),
                       (F_960, 960.0), (F_1440, 1440.0), (F_720, 720.0),
                       (F_720_FILM, 720.0), (F_075, 0.75), (F_4_3, 4 / 3)):
        got = pe.f32(addr)
        assert abs(got - want) < 1e-6, f'{addr:#x}: {got} != {want}'
    print('  1/1920, 1/1080, 1920, 960, 1440, 720, 0.75, 4/3 all OK')


def detect_ui_mode(pe):
    init = pe.bytes(UI_CVT_INIT, 5)
    resize = pe.bytes(UI_CVT_RESIZE, 5)
    mt_init = pe.mul_target(UI_MUL_INIT, 8)
    mt_resize = pe.mul_target(UI_MUL_RESIZE, 8)
    if init == CVT_ORIG_INIT and resize == CVT_ORIG_RESIZE and mt_init == F_1_1080 and mt_resize == F_1_1080:
        return 'fill'
    if init == CVT_UNIFORM_INIT and resize == CVT_UNIFORM_RESIZE and mt_init == F_1_1920 and mt_resize == F_1_1920:
        return 'ui_uniform'
    return 'mixed'


def check_ui_scale(pe):
    print('\n=== ui scale patch state ===')
    mode = detect_ui_mode(pe)
    print(f'  mode: {mode}')
    print(f'  init   cvt {pe.bytes(UI_CVT_INIT, 5).hex()}  mul -> {pe.mul_target(UI_MUL_INIT, 8):#x}')
    print(f'  resize cvt {pe.bytes(UI_CVT_RESIZE, 5).hex()}  mul -> {pe.mul_target(UI_MUL_RESIZE, 8):#x}')
    return mode


def check_fit43(pe):
    print('\n=== fit43 ===')
    for site, old, new in ((0x1a1a02, 0x199e200, F_075), (0x1a1a1b, 0x199ea4c, F_4_3),
                           (0x1a1957, 0x199e200, F_075), (0x1a1970, 0x199ea4c, F_4_3)):
        got = pe.mul_target(site, 8)
        assert got == new, f'{site:#x}: target {got:#x}, expected {new:#x}'
        print(f'  {site:#x} -> {new:#x} ({pe.f32(new):g}) OK')


def check_cam43(pe):
    print('\n=== cam43 ===')
    vs = struct.unpack_from('<I', pe.d, XTEXT_HDR_VSIZE)[0]
    assert vs == 0x200, f'xtext vsize {vs:#x}'
    site = 0x1b1d2e
    b = pe.bytes(site, 5)
    assert b[0] == 0xe9, f'cam site not jmp: {b.hex()}'
    dest = site + 5 + struct.unpack_from('<i', b, 1)[0]
    assert dest == CAVE, f'cam jmp {dest:#x}'
    cave = pe.bytes(CAVE, 29)
    assert cave[:10] == bytes.fromhex('81bbac010000398ee33f'), f'cave cmp: {cave.hex()}'
    assert cave[12:16] == bytes.fromhex('f30f5905'), f'cave mulss: {cave.hex()}'
    mul = CAVE + 12 + 8 + struct.unpack_from('<i', cave, 16)[0]
    assert mul == F_075, f'cave mul target {mul:#x}'
    assert cave[25] == 0xe9, f'cave tail jmp: {cave[25:].hex()}'
    print('  cave, 0.75 mul and jmp OK')


def check_film43(pe):
    print('\n=== film43 ===')
    ok = True
    for site in (0xe0bfde, 0xe0c1cc):
        got = pe.riprel_target(site, 8, 4)
        if got != F_960:
            print(f'  FAIL {site:#x}: height target {got:#x}, expected {F_960:#x} (bottom 240px untinted)')
            ok = False
        else:
            print(f'  {site:#x} height -> {got:#x} ({pe.f32(got):g}) OK')
    for site in (0xe0c044, 0xe0c21f):
        b = pe.bytes(site, 5)
        if b[0] != 0xe8:
            print(f'  FAIL {site:#x}: draw call is {b.hex()} (cinemascope NOP?)')
            ok = False
        else:
            print(f'  {site:#x} draw call intact OK')
    return ok


def check_hud43(pe):
    print('\n=== hud_43 state (the 1440 constants should stay untouched) ===')
    sites = [(0xb9ee03, 1440.0), (0xb9fdfd, 1440.0), (0xba03ce, 1440.0), (0xba05ab, 1440.0),
             (0xb8b2b9, 720.0), (0xb748a5, 720.0), (0xb74915, 720.0),
             (0xc245ff, 1440.0), (0xc2b650, 1440.0), (0xc2b6d0, 1440.0),
             (0xc2c387, 1440.0), (0xcf4e77, 1440.0)]
    patched = []
    for site, value in sites:
        length, disp = (9, 5) if site in (0xb9ee03, 0xb9fdfd, 0xba03ce, 0xba05ab) else (8, 4)
        got = pe.riprel_target(site, length, disp)
        want = F_1920 if value == 1440.0 else F_960
        if got != want:
            patched.append(site)
    if patched:
        print(f'  hud_43 present at {len(patched)}/12 sites (elements shift left of a 1440 canvas)')
    else:
        print('  all 12 sites still target 1920.0/960.0')
    return patched


def verify(path, report=False):
    pe = Pe(path)
    print(f'\n=== {path} ({len(pe.d)} bytes) ===')
    mode = check_ui_scale(pe)
    check_constants(pe)
    check_fit43(pe)
    check_cam43(pe)
    film = check_film43(pe)
    hud = check_hud43(pe)
    band = bottom_band(mode)
    print(f'\n  ui mode {mode}, bottom band {band:.0f}px')
    if mode != 'fill' or hud or not film:
        if mode != 'fill':
            print('  FAIL: ui_uniform is present; the 1080-tall canvas is squashed to 720px')
        if hud:
            print('  FAIL: hud_43 is present; it assumes a 1440x1080 canvas that the scale never had')
        if not film:
            print('  FAIL: film43 is missing; the event overlay leaves the bottom 240px untinted')
        if not report:
            return 1
    else:
        print('  PASS: ui canvas fills 1280x960, no bottom band')
    return 0


if __name__ == '__main__':
    test_model()
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    path = args[0] if args else os.path.join(os.path.dirname(__file__), '..', 'build', 'P5R.t5.exe')
    if os.path.exists(path):
        sys.exit(verify(path, report='--report' in sys.argv))
    print(f'\nskip patch checks: {path} not found')
