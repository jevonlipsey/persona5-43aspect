"""Find IDA-style byte signatures in a PE file and print file offset, RVA and section.

usage: python3 -I tools/sigscan.py <pe> "<hex sig with ??>" [...]
"""
import re
import struct
import sys


def sections(d):
    pe = struct.unpack_from('<I', d, 0x3c)[0]
    n = struct.unpack_from('<H', d, pe + 6)[0]
    osz = struct.unpack_from('<H', d, pe + 20)[0]
    s = pe + 24 + osz
    out = []
    for i in range(n):
        o = s + 40 * i
        name = d[o:o + 8].rstrip(b'\0').decode('latin1')
        vs, va, rs, ra = struct.unpack_from('<IIII', d, o + 8)
        out.append((name, va, vs, ra, rs))
    return out


def off2rva(secs, off):
    for name, va, vs, ra, rs in secs:
        if ra <= off < ra + rs:
            return va + off - ra, name
    return None, None


def rva2off(secs, rva):
    for name, va, vs, ra, rs in secs:
        if va <= rva < va + min(vs, rs):
            return ra + rva - va
    return None


def compile_sig(sig):
    parts = []
    for tok in sig.split():
        parts.append(b'.' if tok in ('?', '??') else re.escape(bytes([int(tok, 16)])))
    return re.compile(b''.join(parts), re.S)


def scan(d, sig):
    return [m.start() for m in compile_sig(sig).finditer(d)]


if __name__ == '__main__':
    d = open(sys.argv[1], 'rb').read()
    secs = sections(d)
    for sig in sys.argv[2:]:
        hits = scan(d, sig)
        print(f'{sig}: {len(hits)} hit(s)')
        for h in hits[:20]:
            rva, name = off2rva(secs, h)
            print(f'  off {h:#x} rva {rva:#x} {name}')
