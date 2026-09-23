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

def _PAETH(a, b, c):
    """The PNG Paeth predictor (W3C PNG, 9.4). A tie goes to the neighbour that comes
    first in the order left (a), above (b), upper-left (c) - by POSITION, not by value.
    Taking min() over (distance, value) pairs broke ties by the smaller value instead,
    which decoded a 2x Blender render wrong on 1.7 % of its pixels."""
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


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


def outline_cells(pixels, width, height, tile_px, colour,
                  thickness=1, alpha_on=48):
    """Ink a flat per-cell contour outward around the opaque silhouette.

    Within each tile_px cell a transparent pixel within Chebyshev radius `thickness`
    of an opaque one becomes `colour`; opaque pixels are never overwritten and the
    neighbourhood is clamped to the cell (no cross-cell bleed).

    Idempotent: a pixel already exactly `colour` is kept but never seeds a new ring,
    so outline_cells(outline_cells(x)) == x. PRECONDITION: the caller must reserve
    `colour` for the contour and not use it as a legitimate body colour - a body
    pixel that happens to equal `colour` is preserved but will not seed.

    A 3-tuple `colour` is taken as opaque (alpha 255). Returns a NEW list; `pixels`
    is not mutated.
    """
    def _int(v):
        return isinstance(v, int) and not isinstance(v, bool)

    # Contract. makeobj cell addressing and the per-cell clamp both depend on it.
    if not (_int(width) and _int(height) and width > 0 and height > 0):
        raise ValueError("width and height must be positive integers")
    if not (_int(tile_px) and tile_px > 0):
        raise ValueError("tile_px must be a positive integer")
    if width % tile_px or height % tile_px:
        raise ValueError("width and height must be multiples of tile_px")
    try:
        count = len(pixels)
    except TypeError:
        raise ValueError("pixels must be a sized sequence") from None
    if count != width * height:
        raise ValueError("pixels has %d entries, expected width*height=%d"
                         % (count, width * height))
    if not (_int(thickness) and thickness >= 1):
        raise ValueError("thickness must be an integer >= 1")
    if not (_int(alpha_on) and 0 <= alpha_on <= 255):
        raise ValueError("alpha_on must be an integer in 0..255")
    try:
        channels = tuple(colour)
    except TypeError:
        raise ValueError("colour must have 3 or 4 integer components in 0..255") from None
    if (len(channels) not in (3, 4)
            or not all(_int(c) and 0 <= c <= 255 for c in channels)):
        raise ValueError("colour must have 3 or 4 integer components in 0..255")

    colour = channels + (255,) if len(channels) == 3 else channels

    def alpha(i):
        p = pixels[i]
        return p[3] if len(p) >= 4 else 255

    def is_body(i):
        # An opaque pixel seeds the contour, unless it is already the reserved ink:
        # keeping a prior contour without re-seeding is what makes a re-run a no-op.
        if alpha(i) < alpha_on:
            return False
        p = pixels[i]
        return (p if len(p) >= 4 else (p[0], p[1], p[2], 255)) != colour

    out = list(pixels)
    cols = width // tile_px
    rows = height // tile_px
    for cr in range(rows):
        for cc in range(cols):
            x0, y0 = cc * tile_px, cr * tile_px
            x1, y1 = x0 + tile_px, y0 + tile_px
            for y in range(y0, y1):
                for x in range(x0, x1):
                    if alpha(y * width + x) >= alpha_on:
                        continue                       # opaque: never overwrite
                    hit = False
                    for dy in range(-thickness, thickness + 1):
                        ny = y + dy
                        if ny < y0 or ny >= y1:
                            continue
                        for dx in range(-thickness, thickness + 1):
                            nx = x + dx
                            if nx < x0 or nx >= x1:
                                continue
                            if is_body(ny * width + nx):
                                hit = True
                                break
                        if hit:
                            break
                    if hit:
                        out[y * width + x] = colour
    return out


def add_outline_file(path, tile_px, colour, thickness=1, alpha_on=48):
    """Read a finished sheet, add a flat per-cell contour, write it back in place.

    Meant to run between the render and makeobj so the compiled .pak carries the
    contour. Returns the (r, g, b) that was inked.
    """
    w, h, _a, px = read_png(path)
    out = outline_cells(px, w, h, tile_px, colour, thickness, alpha_on)
    write_png(path, w, h, out, has_alpha=True)
    return tuple(colour[:3])


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
