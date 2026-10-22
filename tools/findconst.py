"""Find float32 constants in P5R.exe's data sections and list their code xrefs.

usage: .venv/bin/python -I tools/findconst.py <pe> <float>... [--tol 1e-6] [--noxref]
"""
import struct
import sys

import numpy as np

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from disasm import Image  # noqa: E402
from xref import xrefs  # noqa: E402

DATA = ('.debug', '.code', '.link', '.sdata', '.shared')

if __name__ == '__main__':
    img = Image(sys.argv[1])
    args = [a for a in sys.argv[2:]]
    tol = 1e-6
    if '--tol' in args:
        tol = float(args[args.index('--tol') + 1]); del args[args.index('--tol'):args.index('--tol') + 2]
    noxref = '--noxref' in args
    vals = [float(a) for a in args if not a.startswith('--')]
    for name, va, vs, ra, rs in img.secs:
        if name not in ('.debug',):  # rdata lives in ".debug"; .sdata is the Denuvo blob
            continue
        n = rs // 4
        arr = np.frombuffer(img.d, dtype='<f4', count=n, offset=ra)
        for v in vals:
            hits = np.nonzero(np.abs(arr - v) <= tol * max(1, abs(v)))[0]
            for h in hits:
                rva = va + 4 * int(h)
                print(f'{v}: {rva:#x} ({name}) = {arr[h]!r}')
                if not noxref:
                    for t, start, ins in xrefs(img, [rva]):
                        f = img.func(start)
                        print(f'    <- {start:#x} {ins.mnemonic} {ins.op_str}  fn {f[0]:#x}' if f else f'    <- {start:#x} {ins.mnemonic} {ins.op_str}')
