"""
PNG I/O and sprite-sheet assembly - stdlib only (zlib + struct).

No Pillow. That is deliberate: this has to run inside Blender's bundled Python,
which ships zlib but not Pillow, and it keeps the add-on dependency-free.

Reads every non-interlaced PNG colour type: greyscale, RGB, RGBA and - the one
that matters in practice - PALETTED, at 1/2/4/8/16 bits. Blender writes 8-bit
RGBA, but real pakset art does not: pak128's own marker.png is a 2-bit indexed
image. Without palette support the kit could not so much as look at the artwork
it is meant to be compatible with.

write_png only ever emits 8-bit RGB/RGBA; makeobj is happy with that.

Sheet layout
------------
makeobj addresses images as `file.row.col` (.Y.X, zero-based) on an imaginary
grid of tile_px x tile_px cells, and requires the sheet's dimensions to be a
multiple of tile_px. assemble() lays the directions out left-to-right and hands
back the (row, col) of each so the .dat can be written without anyone counting
cells by hand - which is the single most error-prone step of the whole pipeline.
"""

import struct
import zlib

_PAETH = lambda a, b, c: min((abs(b - c), a), (abs(a - c), b), (abs(a + b - 2 * c), c))[1]


_SAMPLES = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}   # channels per colour type


def _unpack_samples(line, depth, count):
    """Split a scanline into `count` samples of `depth` bits, scaled to 0..255."""
    if depth == 8:
        return list(line[:count])
    if depth == 16:
        return [line[2 * i] for i in range(count)]      # high byte is enough

    out = []
    per_byte = 8 // depth
    mask = (1 << depth) - 1
    scale = 255 // mask                                  # 1->255, 2->85, 4->17
    for i in range(count):
        byte = line[i // per_byte]
        shift = 8 - depth * (i % per_byte + 1)
        out.append(((byte >> shift) & mask) * scale)
    return out


def read_png(path):
    """-> (width, height, has_alpha, pixels) with pixels a flat list of tuples."""
    with open(path, "rb") as f:
        data = f.read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("%s: not a PNG" % path)

    pos = 8
    idat = bytearray()
    palette = None
    trns = None
    width = height = depth = ctype = None
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        tag = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        pos += 12 + length  # length + tag + body + crc

        if tag == b"IHDR":
            width, height, depth, ctype, _, _, interlace = struct.unpack(">IIBBBBB", body)
            if ctype not in _SAMPLES:
                raise ValueError("%s: unknown PNG colour type %d" % (path, ctype))
            if depth not in (1, 2, 4, 8, 16):
                raise ValueError("%s: bad PNG bit depth %d" % (path, depth))
            if interlace:
                raise ValueError("%s: interlaced PNG not supported" % path)
        elif tag == b"PLTE":
            palette = [tuple(body[i:i + 3]) for i in range(0, len(body), 3)]
        elif tag == b"tRNS":
            trns = body
        elif tag == b"IDAT":
            idat += body
        elif tag == b"IEND":
            break

    if ctype == 3 and palette is None:
        raise ValueError("%s: paletted PNG with no PLTE chunk" % path)

    nch = _SAMPLES[ctype]
    bits = nch * depth
    stride = (width * bits + 7) // 8
    bpp = max(1, bits // 8)             # filter unit, per the PNG spec

    raw = zlib.decompress(bytes(idat))
    rows = []
    prev = bytearray(stride)
    p = 0
    for _ in range(height):
        filt = raw[p]
        p += 1
        line = bytearray(raw[p:p + stride])
        p += stride

        if filt == 1:      # Sub
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 0xFF
        elif filt == 2:    # Up
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif filt == 3:    # Average
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 0xFF
        elif filt == 4:    # Paeth
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                c = prev[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + _PAETH(a, prev[i], c)) & 0xFF
        elif filt != 0:
            raise ValueError("%s: bad PNG filter %d" % (path, filt))

        rows.append(line)
        prev = line

    # samples -> RGB/RGBA tuples
    if ctype == 3:
        # tRNS, when present, gives one alpha byte per palette index
        alphas = list(trns) if trns else []
        has_alpha = bool(alphas)
        lut = []
        for i, rgb in enumerate(palette):
            a = alphas[i] if i < len(alphas) else 255
            lut.append(rgb + (a,) if has_alpha else rgb)
    else:
        has_alpha = ctype in (4, 6)

    pixels = []
    for line in rows:
        s = _unpack_samples(line, depth, width * nch)
        if ctype == 3:
            # indices must NOT be scaled - undo the 0..255 stretch
            back = 255 // ((1 << depth) - 1) if depth < 8 else 1
            for i in range(width):
                pixels.append(lut[s[i] // back])
        elif ctype == 0:
            for i in range(width):
                pixels.append((s[i], s[i], s[i]))
        elif ctype == 4:
            for i in range(width):
                g, a = s[2 * i], s[2 * i + 1]
                pixels.append((g, g, g, a))
        else:
            for i in range(width):
                pixels.append(tuple(s[i * nch:(i + 1) * nch]))

    return width, height, has_alpha, pixels


def write_png(path, width, height, pixels, has_alpha=True):
    """pixels: flat list of 3- or 4-tuples, len == width*height."""
    nch = 4 if has_alpha else 3
    raw = bytearray()
    for y in range(height):
        raw.append(0)  # filter: None
        for x in range(width):
            px = pixels[y * width + x]
            raw.extend(px[:nch] if len(px) >= nch else tuple(px) + (255,))

    def chunk(tag, body):
        out = struct.pack(">I", len(body)) + tag + body
        return out + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6 if has_alpha else 2, 0, 0, 0)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", ihdr))
        f.write(chunk(b"IDAT", zlib.compress(bytes(raw), 9)))
        f.write(chunk(b"IEND", b""))


def grid_placement(keys, cols=None):
    """Where each key lands on the sheet -> {key: (row, col)}.

    A PURE function of the key ORDER and the column count. It reads no pixels,
    because the .dat only ever refers to a cell by row and column - which is what
    makes it possible to rewrite a .dat WITHOUT re-rendering. assemble() uses this
    for the placement and only touches the images to paint the sheet.
    """
    if cols is None:
        cols = len(keys) or 1
    return {key: divmod(idx, cols) for idx, key in enumerate(keys)}


def assemble(frames, tile_px, cols=None, out_path=None):
    """Lay rendered frames onto a tile grid.

    frames: list of (key, path) - key is the dat direction code.
    Returns {key: (row, col)} so the caller can emit exact image references.
    Every frame must already be tile_px x tile_px (that is what the rig renders).
    """
    n = len(frames)
    if cols is None:
        cols = n or 1
    rows = (n + cols - 1) // cols

    placement = grid_placement([key for key, _ in frames], cols)

    sheet_w, sheet_h = cols * tile_px, rows * tile_px
    canvas = [(0, 0, 0, 0)] * (sheet_w * sheet_h)

    for key, path in frames:
        r, c = placement[key]
        w, h, _alpha, px = read_png(path)
        if (w, h) != (tile_px, tile_px):
            raise ValueError("%s is %dx%d, expected %dx%d - wrong ortho_scale or "
                             "render resolution?" % (path, w, h, tile_px, tile_px))
        for y in range(h):
            base = (r * tile_px + y) * sheet_w + c * tile_px
            for x in range(w):
                p = px[y * w + x]
                canvas[base + x] = p if len(p) == 4 else (p[0], p[1], p[2], 255)

    if out_path:
        write_png(out_path, sheet_w, sheet_h, canvas, has_alpha=True)
    return placement
