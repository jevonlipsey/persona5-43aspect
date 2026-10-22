"""Find RIP-relative references to data RVAs in P5R.exe's code section (.xcode).

usage: .venv/bin/python -I tools/xref.py <pe> <rva hex>... [--ctx N]
Candidates are found by disp32 arithmetic (numpy), then confirmed with capstone
by decoding the instruction that ends at disp+4(+imm). Prints the instruction
and the containing function (from .pdata).
"""
import struct
import sys

import numpy as np

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from disasm import Image, BASE  # noqa: E402


def code_range(img):
    for name, va, vs, ra, rs in img.secs:
        if name == '.xcode':
            return va, ra, rs
    raise SystemExit('no .xcode')


_cache = {}


def func_insns(img, f):
    if f not in _cache:
        code = img.read(f[0], f[1] - f[0])
        _cache[f] = list(img.md.disasm(code, BASE + f[0]))
    return _cache[f]


def rip_target(ins):
    for op in ins.operands:
        if op.type == 3 and op.mem.base == 41:
            return ins.address + ins.size + op.mem.disp - BASE
    return None


def confirm(img, drva, t):
    """The instruction holding the disp32 at drva, if it really references t."""
    f = img.func(drva)
    if f:
        for ins in func_insns(img, f):
            a = ins.address - BASE
            if a < drva < a + ins.size:
                return ins if rip_target(ins) == t else None
        return None
    # leaf function without .pdata: longest decode that covers the disp
    for back in range(7, 0, -1):
        start = drva - back
        ins = next(img.md.disasm(img.read(start, 16), BASE + start), None)
        if ins and rip_target(ins) == t and start + ins.size > drva + 3:
            return ins
    return None


def xrefs(img, targets):
    va, ra, rs = code_range(img)
    buf = np.frombuffer(img.d, dtype=np.uint8, count=rs, offset=ra)
    disp = buf[:-4].view(np.uint8)
    d32 = (disp[:-3].astype(np.int64) | (disp[1:-2].astype(np.int64) << 8) |
           (disp[2:-1].astype(np.int64) << 16) | (disp[3:].astype(np.int64) << 24))
    d32 = np.where(d32 >= 1 << 31, d32 - (1 << 32), d32)
    pos = np.arange(len(d32), dtype=np.int64) + va  # rva of the disp field
    out = []
    for t in targets:
        for extra in (0, 1, 2, 4):
            hits = np.nonzero(pos + 4 + extra + d32 == t)[0]
            for h in hits:
                drva = int(pos[h])
                hit = confirm(img, drva, t)
                if hit:
                    out.append((t, hit.address - BASE, hit))
    return out


if __name__ == '__main__':
    img = Image(sys.argv[1])
    ts = [int(a, 16) for a in sys.argv[2:] if not a.startswith('--')]
    for t, start, ins in sorted(xrefs(img, ts), key=lambda x: (x[0], x[1])):
        f = img.func(start)
        fs = f'{f[0]:#x}' if f else '?'
        print(f'{t:#x} <- {start:#x} {ins.mnemonic} {ins.op_str}   fn {fs}')
