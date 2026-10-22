"""List direct callers (E8 call / E9 jmp rel32) of functions in P5R.exe's .xcode.

usage: .venv/bin/python -I tools/callers.py <pe> <rva hex>... [--count]
"""
import sys

import numpy as np

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from disasm import Image  # noqa: E402
from xref import code_range, func_insns  # noqa: E402


def callers(img, targets):
    va, ra, rs = code_range(img)
    b = np.frombuffer(img.d, dtype=np.uint8, count=rs, offset=ra)
    rel = (b[1:-3].astype(np.int64) | (b[2:-2].astype(np.int64) << 8) |
           (b[3:-1].astype(np.int64) << 16) | (b[4:].astype(np.int64) << 24))
    rel = np.where(rel >= 1 << 31, rel - (1 << 32), rel)
    op = b[:-4]
    pos = np.arange(len(rel), dtype=np.int64) + va
    dest = pos + 5 + rel
    out = {}
    for t in targets:
        hits = np.nonzero((dest == t) & ((op == 0xE8) | (op == 0xE9)))[0]
        res = []
        for h in hits:
            a = int(pos[h])
            f = img.func(a)
            if f:  # confirm instruction boundary
                if not any(i.address - 0x140000000 == a for i in func_insns(img, f)):
                    continue
            res.append((a, f))
        out[t] = res
    return out


if __name__ == '__main__':
    img = Image(sys.argv[1])
    ts = [int(a, 16) for a in sys.argv[2:] if not a.startswith('--')]
    for t, res in callers(img, ts).items():
        print(f'{t:#x}: {len(res)} callers')
        if '--count' not in sys.argv:
            for a, f in res:
                print(f'   {a:#x}  fn {f[0]:#x}' if f else f'   {a:#x}  fn ?')
