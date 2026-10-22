"""Disassemble a P5R.exe function (bounds from .pdata) with RIP-relative
operands resolved: float/double/int values and ascii strings are shown inline.

usage: .venv/bin/python -I tools/disasm.py <pe> <rva hex> [--len N] [--raw]
  --raw   disassemble N bytes from the rva instead of the .pdata function
"""
import bisect
import struct
import sys

import capstone
from capstone import x86

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from sigscan import sections, rva2off  # noqa: E402

BASE = 0x140000000


class Image:
    def __init__(self, path):
        self.d = open(path, 'rb').read()
        self.secs = sections(self.d)
        pe = struct.unpack_from('<I', self.d, 0x3c)[0]
        dd = pe + 24 + 112
        prva, psz = struct.unpack_from('<II', self.d, dd + 3 * 8)
        po = rva2off(self.secs, prva)
        self.funcs = []
        for i in range(psz // 12):
            b, e, u = struct.unpack_from('<III', self.d, po + 12 * i)
            self.funcs.append((b, e))
        self.funcs.sort()
        self.starts = [f[0] for f in self.funcs]
        self.md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
        self.md.detail = True

    def func(self, rva):
        i = bisect.bisect_right(self.starts, rva) - 1
        if i >= 0 and self.funcs[i][0] <= rva < self.funcs[i][1]:
            return self.funcs[i]
        return None

    def read(self, rva, n):
        o = rva2off(self.secs, rva)
        if o is None:
            return None
        return self.d[o:o + n]

    def describe(self, rva, size):
        b = self.read(rva, 16)
        if b is None:
            return ''
        out = []
        if size == 4 or size == 16:
            f = struct.unpack_from('<f', b)[0]
            i = struct.unpack_from('<i', b)[0]
            out.append(f'f={f:.6g} i={i}')
        if size == 8:
            out.append(f'd={struct.unpack_from("<d", b)[0]:.6g} q={struct.unpack_from("<q", b)[0]:#x}')
        if size == 16:
            out.append('xmm=' + ','.join(f'{x:.5g}' for x in struct.unpack_from('<4f', b)))
        s = self.read(rva, 48)
        if s and 32 <= s[0] < 127:
            t = s.split(b'\0')[0]
            if len(t) >= 4 and all(32 <= c < 127 for c in t):
                out.append(repr(t.decode()))
        return ' '.join(out)

    def disasm(self, rva, n):
        code = self.read(rva, n)
        lines = []
        for ins in self.md.disasm(code, BASE + rva):
            note = ''
            for op in ins.operands:
                if op.type == x86.X86_OP_MEM and op.mem.base == x86.X86_REG_RIP:
                    tgt = ins.address + ins.size + op.mem.disp - BASE
                    note = f'  ; [{tgt:#x}] {self.describe(tgt, op.size)}'
            if ins.mnemonic in ('call', 'jmp') and ins.operands and ins.operands[0].type == x86.X86_OP_IMM:
                note = f'  ; -> {ins.operands[0].imm - BASE:#x}'
            lines.append(f'{ins.address - BASE:8x}: {ins.bytes.hex():24s} {ins.mnemonic} {ins.op_str}{note}')
        return lines


if __name__ == '__main__':
    img = Image(sys.argv[1])
    rva = int(sys.argv[2], 16)
    n = 256
    if '--len' in sys.argv:
        n = int(sys.argv[sys.argv.index('--len') + 1], 0)
    if '--raw' not in sys.argv:
        f = img.func(rva)
        if f:
            print(f'; function {f[0]:#x}-{f[1]:#x} ({f[1]-f[0]} bytes)')
            rva, n = f[0], f[1] - f[0]
    print('\n'.join(img.disasm(rva, n)))
