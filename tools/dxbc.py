"""List the DXBC shaders embedded in P5R.exe with their RDEF reflection
(constant buffers, variables, offsets), input/output signatures.

usage: python3 -I tools/dxbc.py <pe> [--grep NAME] [--dump DIR]
"""
import re
import struct
import sys


def cstr(b, o):
    return b[o:b.index(b'\0', o)].decode('latin1')


def parse(d, off):
    magic, = struct.unpack_from('<4s', d, off)
    total, nchunks = struct.unpack_from('<II', d, off + 24)
    blob = d[off:off + total]
    chunks = {}
    for i in range(nchunks):
        co, = struct.unpack_from('<I', blob, 32 + 4 * i)
        tag = blob[co:co + 4].decode('latin1')
        sz, = struct.unpack_from('<I', blob, co + 4)
        chunks[tag] = blob[co + 8:co + 8 + sz]
    return blob, chunks


def rdef(c):
    ncb, cboff, nbind, bindoff, minor, major, ptype, flags, creator = struct.unpack_from('<IIIIBBHII', c, 0)
    out = {'type': {0xFFFE: 'vs', 0xFFFF: 'ps', 0x4353: 'cs', 0x4753: 'gs'}.get(ptype, hex(ptype)), 'cbs': [], 'binds': []}
    for i in range(nbind):
        name, typ, ret, dim, ns, bp, bc, fl = struct.unpack_from('<IIIIIIII', c, bindoff + 32 * i)
        out['binds'].append((cstr(c, name), typ, bp))
    for i in range(ncb):
        name, nvar, varoff, size, fl, typ = struct.unpack_from('<IIIIII', c, cboff + 24 * i)
        vs = []
        stride = 40 if major >= 5 else 24
        for j in range(nvar):
            vn, so, sz, vf, vt, dv = struct.unpack_from('<IIIIII', c, varoff + stride * j)
            vs.append((cstr(c, vn), so, sz))
        out['cbs'].append((cstr(c, name), size, vs))
    return out


def sig(c):
    n, _ = struct.unpack_from('<II', c, 0)
    res = []
    for i in range(n):
        name, idx, sv, ct, reg, mask = struct.unpack_from('<IIIIIB', c, 8 + 24 * i)
        res.append(f'{cstr(c, name)}{idx}')
    return res


if __name__ == '__main__':
    d = open(sys.argv[1], 'rb').read()
    grep = sys.argv[sys.argv.index('--grep') + 1] if '--grep' in sys.argv else None
    dump = sys.argv[sys.argv.index('--dump') + 1] if '--dump' in sys.argv else None
    for i, m in enumerate(re.finditer(b'DXBC', d)):
        off = m.start()
        try:
            blob, ch = parse(d, off)
        except Exception as e:
            continue
        if 'RDEF' not in ch:
            continue
        r = rdef(ch['RDEF'])
        text = f'#{i} off {off:#x} {r["type"]} size {len(blob)} in={sig(ch["ISGN"]) if "ISGN" in ch else "?"} out={sig(ch["OSGN"]) if "OSGN" in ch else "?"}\n'
        text += f'   binds: {r["binds"]}\n'
        for name, size, vs in r['cbs']:
            text += f'   cbuffer {name} ({size}): ' + ', '.join(f'{v}@{o:#x}' for v, o, s in vs) + '\n'
        if grep and grep not in text:
            continue
        print(text, end='')
        if dump:
            open(f'{dump}/shader_{i:03d}_{r["type"]}.dxbc', 'wb').write(blob)
