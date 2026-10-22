"""Read a CRI CPK's table of contents over ssh (ranged reads, never the whole archive)
and extract single files from it.

usage: python3 -I tools/cpk.py list <device cpk path> [pattern]   -> analysis/cpk/<name>.toc.tsv
       python3 -I tools/cpk.py get  <device cpk path> <dir/file> <out>
Files may be CRILAYLA-compressed; `get` decompresses them.
"""
import os
import struct
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, 'analysis', 'cpk')


def ssh_read(path, off, size):
    cmd = f"dd if='{path}' iflag=skip_bytes,count_bytes skip={off} count={size} bs=1M 2>/dev/null"
    return subprocess.run(['ssh', '-o', 'BatchMode=yes', 'droiddeck', cmd], capture_output=True, check=True).stdout


def unmask(b):
    if b[:4] == b'@UTF':
        return b
    m, out = 0x655f, bytearray()
    for x in b:
        out.append(x ^ (m & 0xff))
        m = (m * 0x4115) & 0xffffffff
    return bytes(out)


def utf(b):
    """Parse an @UTF table -> list of dict rows."""
    assert b[:4] == b'@UTF', b[:4]
    size, roff, soff, doff, nlen, ncol, rowlen, nrows = struct.unpack_from('>IHIIIHHI', b, 4)
    # header layout: size u32, unk u16 + rows offset u16 (roff), strings u32, data u32, name u32, cols u16, rowlen u16, rows u32
    base = 8
    roff = struct.unpack_from('>H', b, 10)[0]
    soff, doff, nameoff = struct.unpack_from('>III', b, 12)
    ncol, rowlen, nrows = struct.unpack_from('>HHI', b, 24)

    def s(o):
        o += base + soff
        return b[o:b.index(b'\0', o)].decode('latin1')

    fmt = {0: '>B', 1: '>b', 2: '>H', 3: '>h', 4: '>I', 5: '>i', 6: '>Q', 7: '>q', 8: '>f'}
    p = 32
    cols = []
    for _ in range(ncol):
        flags = b[p]; p += 1
        name = s(struct.unpack_from('>I', b, p)[0]); p += 4
        typ, store = flags & 0xf, flags & 0xf0
        const = None
        if store == 0x30:
            const, p = val(b, p, typ, s, fmt, base + doff)
        cols.append((name, typ, store, const))
    rows = []
    for r in range(nrows):
        p = base + roff + r * rowlen
        row = {}
        for name, typ, store, const in cols:
            if store == 0x50:
                row[name], p = val(b, p, typ, s, fmt, base + doff)
            elif store == 0x30:
                row[name] = const
            else:
                row[name] = None
        rows.append(row)
    return rows


def val(b, p, typ, s, fmt, dbase):
    if typ in fmt:
        f = fmt[typ]
        return struct.unpack_from(f, b, p)[0], p + struct.calcsize(f)
    if typ == 0xa:
        return s(struct.unpack_from('>I', b, p)[0]), p + 4
    if typ == 0xb:
        o, n = struct.unpack_from('>II', b, p)
        return b[dbase + o:dbase + o + n], p + 8
    raise ValueError(typ)


def header(path):
    h = ssh_read(path, 0, 0x800)
    n = struct.unpack_from('<I', h, 8)[0]
    return utf(unmask(h[0x10:0x10 + n]))[0]


def toc(path):
    name = os.path.basename(path)
    os.makedirs(CACHE, exist_ok=True)
    cache = os.path.join(CACHE, name + '.toc.tsv')
    if os.path.exists(cache):
        rows = []
        for line in open(cache):
            d, f, off, size, ext = line.rstrip('\n').split('\t')
            rows.append((d, f, int(off), int(size), int(ext)))
        return rows
    hd = header(path)
    tocoff, tocsize, contoff = hd['TocOffset'], hd['TocSize'], hd['ContentOffset']
    t = ssh_read(path, tocoff, tocsize)
    n = struct.unpack_from('<I', t, 8)[0]
    rows = utf(unmask(t[0x10:0x10 + n]))
    base = min(tocoff, contoff)
    out = []
    with open(cache, 'w') as fh:
        for r in rows:
            e = (r.get('DirName') or '', r.get('FileName') or '', base + r['FileOffset'], r['FileSize'], r.get('ExtractSize') or r['FileSize'])
            out.append(e)
            fh.write('\t'.join(map(str, e)) + '\n')
    return out


def layla(b):
    """CRILAYLA decompression."""
    assert b[:8] == b'CRILAYLA'
    usize, hoff = struct.unpack_from('<II', b, 8)
    prefix = b[0x10 + hoff:0x10 + hoff + 0x100]
    out = bytearray(usize)
    src = b[0x10:0x10 + hoff]
    pos = [len(src) * 8]

    def bits(n):
        v = 0
        for _ in range(n):
            pos[0] -= 1
            byte = src[pos[0] >> 3]
            # read from end, msb first per byte (reverse bit order)
            v = (v << 1) | ((byte >> (7 - (pos[0] & 7))) & 1)
        return v
    # Bitstream is read backwards byte-wise, msb-first within each byte.
    pos[0] = len(src) * 8
    data = src
    bitpos = [0]
    rev = data[::-1]

    def rb(n):
        v = 0
        for _ in range(n):
            i = bitpos[0]
            v = (v << 1) | ((rev[i >> 3] >> (7 - (i & 7))) & 1)
            bitpos[0] += 1
        return v
    w = usize - 1
    while w >= 0:
        if rb(1):
            off = rb(13) + 3
            ln = 3
            for lv in (2, 3, 5, 8):
                x = rb(lv)
                ln += x
                if x != (1 << lv) - 1:
                    break
            else:
                while True:
                    x = rb(8)
                    ln += x
                    if x != 255:
                        break
            for _ in range(ln):
                if w < 0:
                    break
                out[w] = out[w + off]
                w -= 1
        else:
            out[w] = rb(8)
            w -= 1
    return bytes(prefix) + bytes(out)


if __name__ == '__main__':
    cmd, path = sys.argv[1], sys.argv[2]
    rows = toc(path)
    if cmd == 'list':
        pat = sys.argv[3].lower() if len(sys.argv) > 3 else ''
        for d, f, off, size, ext in rows:
            if pat in (d + '/' + f).lower():
                print(f'{d}/{f}\t{size}\t{ext}')
    elif cmd == 'get':
        want = sys.argv[3].lower()
        for d, f, off, size, ext in rows:
            if (d + '/' + f).lower() == want or f.lower() == want:
                b = ssh_read(path, off, size)
                if b[:8] == b'CRILAYLA':
                    b = layla(b)
                open(sys.argv[4], 'wb').write(b)
                print(f'{d}/{f}: {size} -> {len(b)} bytes')
                break
        else:
            sys.exit('not found')
