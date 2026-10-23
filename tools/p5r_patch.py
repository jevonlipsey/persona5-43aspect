"""Apply the 4:3 byte patches to P5R.exe (Windows build, 395876288 bytes).

usage: python3 -I tools/p5r_patch.py <in.exe> <out.exe> [--set NAME[,NAME]]
Every patch carries the bytes it expects to find; any mismatch aborts.
RVAs are image-relative (image base 0x140000000), file offsets come from the section table.
"""
import hashlib
import struct
import sys


def sections(d):
    pe = struct.unpack_from('<I', d, 0x3c)[0]
    n = struct.unpack_from('<H', d, pe + 6)[0]
    s = pe + 24 + struct.unpack_from('<H', d, pe + 20)[0]
    return [struct.unpack_from('<IIII', d, s + 40 * i + 8) for i in range(n)]  # vs, va, rs, ra


def rva2off(secs, rva):
    for vs, va, rs, ra in secs:
        if va <= rva < va + min(vs, rs):
            return ra + rva - va
    raise SystemExit(f'rva {rva:#x} not in file')


def rd32(d, secs, rva):
    o = rva2off(secs, rva)
    return d[o:o + 4]


F_075 = 0x199e3f8   # float 0.75
F_4_3 = 0x199e8e0   # float 1.3333334


def retarget(insn_rva, length, newtarget):
    """New disp32 for a rip-relative instruction of `length` bytes at insn_rva."""
    return struct.pack('<i', newtarget - (insn_rva + length))


def fit43():
    """Fit the render area to 4:3 instead of 16:9 (both copies of the resize code)."""
    out = []
    for base_sc, base_ar in ((0x1a1a02, 0x1a1a1b), (0x1a1957, 0x1a1970)):
        # mulss xmm0,[rip+d] (8 bytes): 0.5625 -> 0.75, 1.7777778 -> 1.3333334
        out.append((f'fit h={base_sc:x}', base_sc + 4, retarget(base_sc, 8, 0x199e200), retarget(base_sc, 8, F_075)))
        out.append((f'fit w={base_ar:x}', base_ar + 4, retarget(base_ar, 8, 0x199ea4c), retarget(base_ar, 8, F_4_3)))
    return out


F_1_1920 = 0x199d704  # float 1/1920
F_1_1080 = 0x199d728  # float 1/1080


def ui_uniform():
    """2D scale: y scale = x scale (width/1920) instead of height/1080.
    not in t5: it squashes the 1080-tall canvas to 720px and leaves the bottom band."""
    out = []
    # init (1a4390): xmm0 = (float)r13 (height) -> (float)r12 (width); * 1/1080 -> * 1/1920
    out.append(('ui init cvt', 0x1a4514, bytes.fromhex('f3490f2ac5'), bytes.fromhex('f3490f2ac4')))
    out.append(('ui init mul', 0x1a4529 + 4, retarget(0x1a4529, 8, F_1_1080), retarget(0x1a4529, 8, F_1_1920)))
    # resize (1a1a80): xmm0 = (float)rax (height) -> (float)r13 (width); * 1/1080 -> * 1/1920
    out.append(('ui resize cvt', 0x1a1b10, bytes.fromhex('f3480f2ac0'), bytes.fromhex('f3490f2ac5')))
    out.append(('ui resize mul', 0x1a1b1d + 4, retarget(0x1a1b1d, 8, F_1_1080), retarget(0x1a1b1d, 8, F_1_1920)))
    return out


XTEXT_HDR_VSIZE_OFF = 0x398 + 8   # .xtext section header, VirtualSize (0x61 -> 0x200 so the cave is mapped)
CAVE = 0x17fef080                 # unused tail of .xtext (RWX, file bytes zero; file offset 0x17846e80)


def jmp(frm, to):
    return b'\xe9' + struct.pack('<i', to - (frm + 5))


def cam43():
    """Vert+ for 16:9 cameras: scale the projection's Y term by 0.75 so a 4:3 target
    shows the same horizontal extent as 16:9 plus more vertically."""
    site = 0x1b1d2e   # movss [rbx+0x74], xmm0   (P[1][1] = cot(fov/2)) in the camera matrix build 1b1c30
    cave = (bytes.fromhex('81bbac01000039 8e e3 3f'.replace(' ', ''))   # cmp dword [rbx+0x1ac], 16/9
            + bytes.fromhex('7508')                                     # jne +8
            + bytes.fromhex('f30f5905') + struct.pack('<i', F_075 - (CAVE + 12 + 8))  # mulss xmm0,[0.75]
            + bytes.fromhex('f30f114374')                               # movss [rbx+0x74], xmm0
            + jmp(CAVE + 25, 0x1b1d33))
    return [('cam hdr vsize', 'RAW', XTEXT_HDR_VSIZE_OFF, struct.pack('<I', 0x61), struct.pack('<I', 0x200)),
            ('cam cave', 'RAW', 0x17846e80, bytes(len(cave)), cave),
            ('cam site', site, bytes.fromhex('f30f114374'), jmp(site, CAVE))]


def cinemascope():
    """Remove hardcoded 16:9 CinemaScope letterbox bars in event/dialogue scenes."""
    # NOP out the two call 141590580 quad-drawing instructions in evt_letter_box render (0xe0c044, 0xe0c21f)
    return [
        ('cinemascope call1', 0xe0c044, bytes.fromhex('e837457800'), bytes.fromhex('9090909090')),
        ('cinemascope call2', 0xe0c21f, bytes.fromhex('e85c437800'), bytes.fromhex('9090909090')),
    ]


def cam_aspect_defaults():
    """Retarget default camera builds and aspect checks from 16:9 to 4:3."""
    out = []
    # 0x13ca9e9, 0x13cac47, 0x1450d65: movss xmm1/2, [16/9] -> [4/3]
    out.append(('cam default 1', 0x13ca9e9 + 4, retarget(0x13ca9e9, 8, 0x199ea4c), retarget(0x13ca9e9, 8, F_4_3)))
    out.append(('cam default 2', 0x13cac47 + 4, retarget(0x13cac47, 8, 0x199ea4c), retarget(0x13cac47, 8, F_4_3)))
    out.append(('cam default 3', 0x1450d65 + 4, retarget(0x1450d65, 8, 0x199ea4c), retarget(0x1450d65, 8, F_4_3)))
    # 0x1da29d: comiss xmm0, [16/9] -> [4/3]
    out.append(('aspect cmp 1da29d', 0x1da29d + 3, retarget(0x1da29d, 7, 0x199ea4c), retarget(0x1da29d, 7, F_4_3)))
    return out


F_1440 = 0x18baaa0   # float 1440.0
F_720 = 0x187cc74    # float 720.0
F_960 = 0x19a0fd8    # float 960.0


def hud_43():
    """Re-anchor battle party panel, command wheel center, calendar/weather, and dialogue to 4:3.
    only valid with a 1440x1080 canvas (x scale width/1440); t5 keeps width/1920, so this is not used."""
    out = []
    # 1. Battle party panel width: retarget 1920.0 -> 1440.0
    for site in (0xb9ee03, 0xb9fdfd, 0xba03ce, 0xba05ab):
        out.append((f'btl panel w {site:x}', site + 5, retarget(site, 9, 0x19a1730), retarget(site, 9, F_1440)))
    # 2. Battle command wheel center: 960.0 -> 720.0 (center of 1440)
    out.append(('btl wheel center', 0xb8b2b9 + 4, retarget(0xb8b2b9, 8, F_960), retarget(0xb8b2b9, 8, F_720)))
    # 3. Calendar / weather screen center: 960.0 -> 720.0
    for site in (0xb748a5, 0xb74915):
        out.append((f'calendar center {site:x}', site + 4, retarget(site, 8, F_960), retarget(site, 8, F_720)))
    # 4. Field HUD & Dialogue box width: 1920.0 -> 1440.0
    for site in (0xc245ff, 0xc2b650, 0xc2b6d0, 0xc2c387, 0xcf4e77):
        out.append((f'field/dlg w {site:x}', site + 4, retarget(site, 8, 0x19a1730), retarget(site, 8, F_1440)))
    return out


SETS = {
    'fit43': fit43,
    'ui_uniform': ui_uniform,
    'cam43': cam43,
    'cinemascope': cinemascope,
    'cam_aspect_defaults': cam_aspect_defaults,
    'hud_43': hud_43,
}


def build(names):
    ps = []
    for n in names:
        ps += SETS[n]()
    return ps


def apply(src, names):
    d = bytearray(src)
    secs = sections(d)
    for p in build(names):
        if p[1] == 'RAW':   # (name, 'RAW', file offset, old, new)
            name, _, o, old, new = p
            rva = o
        else:
            name, rva, old, new = p
            o = rva2off(secs, rva)
        if bytes(d[o:o + len(old)]) != old:
            raise SystemExit(f'{name}: bytes at {rva:#x} are {bytes(d[o:o+len(old)]).hex()}, expected {old.hex()}')
        d[o:o + len(new)] = new
    return d


def resolved(src, names):
    """[(name, file offset, old bytes, new bytes)] with every RVA turned into a file offset."""
    secs = sections(src)
    out = []
    for p in build(names):
        if p[1] == 'RAW':
            out.append((p[0], p[2], p[3], p[4]))
        else:
            out.append((p[0], rva2off(secs, p[1]), p[2], p[3]))
    return sorted(out, key=lambda x: x[1])


if __name__ == '__main__' and '--json' in sys.argv:
    # tools/p5r_patch.py --json <in.exe> <out.js> [--set a,b]  -> web patch table
    import json
    a = [x for x in sys.argv[1:] if x != '--json']
    names = ['fit43']
    if '--set' in a:
        i = a.index('--set'); names = a[i + 1].split(','); del a[i:i + 2]
    src = open(a[0], 'rb').read()
    tab = {'size': len(src), 'sha256': hashlib.sha256(src).hexdigest(), 'sets': names,
           'patches': [{'name': n, 'offset': o, 'old': ob.hex(), 'new': nb.hex()} for n, o, ob, nb in resolved(src, names)]}
    open(a[1], 'w').write('/* generated by tools/p5r_patch.py --json; do not edit */\nglobalThis.P5R_PATCHES = ' + json.dumps(tab, indent=1) + ';\n')
    sys.exit(0)

if __name__ == '__main__':
    a = sys.argv[1:]
    names = ['fit43']
    if '--set' in a:
        i = a.index('--set')
        names = a[i + 1].split(',')
        del a[i:i + 2]
    src = open(a[0], 'rb').read()
    out = apply(src, names)
    open(a[1], 'wb').write(out)
    print('in ', hashlib.sha256(src).hexdigest())
    print('out', hashlib.sha256(out).hexdigest(), names)
