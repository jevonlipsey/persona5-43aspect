"""Minimal SM4/SM5 (DXBC SHDR/SHEX) disassembler, enough to read small vertex shaders.

usage: python3 -I tools/sm4dis.py <pe-or-dxbc> [file offset of DXBC]
"""
import struct
import sys

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from dxbc import parse  # noqa: E402

OPS = ('add and break breakc call callc case continue continuec cut default deriv_rtx deriv_rty discard div '
       'dp2 dp3 dp4 else emit emitthencut endif endloop endswitch eq exp frc ftoi ftou ge iadd if ieq ige ilt '
       'imad imax imin imul ine ineg ishl ishr itof label ld ld_ms log loop lt mad min max customdata mov movc '
       'mul ne nop not or resinfo ret retc round_ne round_ni round_pi round_z rsq sample sample_c sample_c_lz '
       'sample_l sample_d sample_b sqrt switch sincos udiv ult uge umul umad umax umin ushr utof xor '
       'dcl_resource dcl_constantbuffer dcl_sampler dcl_index_range dcl_gs_output_topology dcl_gs_input_primitive '
       'dcl_max_output_vertex_count dcl_input dcl_input_sgv dcl_input_siv dcl_input_ps dcl_input_ps_sgv '
       'dcl_input_ps_siv dcl_output dcl_output_sgv dcl_output_siv dcl_temps dcl_indexable_temp dcl_global_flags').split()
REG = {0: 'r', 1: 'v', 2: 'o', 3: 'x', 6: 's', 7: 't', 8: 'cb', 9: 'icb', 4: 'l'}


def operand(t, i):
    tok = t[i]; i += 1
    ncomp = tok & 3
    sel = (tok >> 2) & 3
    typ = (tok >> 12) & 0xff
    dim = (tok >> 20) & 3
    reps = [(tok >> 22) & 7, (tok >> 25) & 7, (tok >> 28) & 7]
    ext = tok >> 31
    mod = ''
    if ext:
        e = t[i]; i += 1
        m = (e >> 6) & 0xff
        mod = {1: '-', 2: '|', 3: '-|'}.get(m, '')
    if typ == 4:
        n = 4 if ncomp == 2 else 1
        vals = t[i:i + n]; i += n
        fl = [struct.unpack('<f', struct.pack('<I', v))[0] for v in vals]
        return f'l({", ".join(f"{f:g}" if abs(f) < 1e6 and (f == 0 or abs(f) > 1e-6) else hex(v) for f, v in zip(fl, vals))})', i
    name = REG.get(typ, f'T{typ}')
    if typ == 0x0b or typ == 0x0c:
        name = {0x0b: 'oDepth?', 0x0c: 'null'}[typ]
    idx = []
    for d in range(dim):
        r = reps[d]
        if r == 0:
            idx.append(str(t[i])); i += 1
        elif r == 2:
            sub, i = operand(t, i)
            idx.append(sub)
        elif r == 3:
            c = t[i]; i += 1
            sub, i = operand(t, i)
            idx.append(f'{sub} + {c}')
        else:
            idx.append('?'); i += 1
    if typ in (0, 1, 2, 6, 7):
        s = name + (idx[0] if idx else '') + ''.join(f'[{x}]' for x in idx[1:])
    else:
        s = name + ''.join(f'[{x}]' for x in idx)
    comp = ''
    if ncomp == 2:
        b = (tok >> 4) & 0xff
        if sel == 0:
            comp = '.' + ''.join(c for k, c in enumerate('xyzw') if b & (1 << k))
        elif sel == 1:
            comp = '.' + ''.join('xyzw'[(b >> (2 * k)) & 3] for k in range(4))
        else:
            comp = '.' + 'xyzw'[b & 3]
    s = s + comp
    if mod == '-':
        s = '-' + s
    elif mod == '|':
        s = f'|{s}|'
    elif mod == '-|':
        s = f'-|{s}|'
    return s, i


def disasm(code):
    t = struct.unpack(f'<{len(code) // 4}I', code)
    ver, length = t[0], t[1]
    out = [f'; version {ver:#x} ({["ps", "vs", "gs", "hs", "ds", "cs"][(ver >> 16) & 0xf] if ((ver >> 16) & 0xf) < 6 else ver})']
    i = 2
    while i < length:
        tok = t[i]
        op = tok & 0x7ff
        ln = (tok >> 24) & 0x7f
        if op == 53:
            ln = t[i + 1]
            out.append(f'  customdata ({ln} dwords)')
            i += ln
            continue
        name = OPS[op] if op < len(OPS) else f'op{op}'
        if tok & (1 << 13) and op < 88:
            name += '_sat'
        j = i + 1
        while t[j - 1] >> 31 and j < i + ln and op < 88:
            j += 1  # extended opcode tokens
        args = []
        if op in (104, 106, 89, 90, 88, 95, 96, 97, 98, 101, 102, 103):
            if op == 104 or op == 106:
                args = [str(t[j])]
            else:
                try:
                    a, k = operand(t, j)
                    args = [a] + [str(x) for x in t[k:i + ln]]
                except Exception:
                    args = [hex(x) for x in t[j:i + ln]]
        else:
            k = j
            while k < i + ln:
                try:
                    a, k = operand(t, k)
                except Exception:
                    args.append('??'); break
                args.append(a)
        out.append(f'  {name} {", ".join(args)}')
        i += max(ln, 1)
    return out


if __name__ == '__main__':
    d = open(sys.argv[1], 'rb').read()
    off = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0
    blob, ch = parse(d, off)
    code = ch.get('SHEX') or ch.get('SHDR')
    print('\n'.join(disasm(code)))
