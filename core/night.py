"""What the sheet will look like after dark - the engine's arithmetic, not a filter.

Night in Simutrans is not a render effect and it is not a blue overlay. It is a
palette. display/simgraph16.cc rebuilds its colour maps whenever the hour changes
(calc_base_pal_from_night_shift), and every pixel of every sprite goes through
one of THREE completely different paths depending on which class of colour it is:

  ordinary pixel   quantised to RGB555, then scaled DOWN:
                       R,G  x  0.75^night          (simgraph16.cc:1854)
                       B    x  0.83^night          (simgraph16.cc:1855)
                   red and green fall faster than blue, which is why a night
                   scene goes cold rather than merely dim.

  LIGHT colour     NOT scaled at all. It is a straight linear blend between the
                   day table and the night table (simgraph16.cc:1917-1932):
                       out = (day*(4-n) + night*n) >> 2
                   so it keeps its full brightness while everything around it
                   darkens - that is the whole trick, and it is why a lit window
                   has to hit its day colour EXACTLY. One count out and the pixel
                   is an ordinary pixel, and ordinary pixels get dark.

  player colour    scaled like an ordinary pixel, but from its 888 value: the
                   pak stores an index, not a colour, so it never goes through
                   the 555 quantiser (simgraph16.cc:1891-1897).

night runs 0 (noon) to 4 (deep night): display/simview.cc hours2night[] is a
48-entry table of the day and its largest value is 4.

Why this module exists
----------------------
Because the alternative is launching the game, founding a company, laying track,
building a train, and waiting for dusk - every time you touch the livery. An
artist will not do that, so they will ship windows that never light. We did
exactly that: the first Civia had its glass one count off the engine's colour and
would have run dark for ever, and nothing anywhere would have said why.
"""

try:
    from . import colors, sheet
except ImportError:                       # standalone / Blender's flat sys.path
    import colors
    import sheet

# display/simview.cc hours2night[]: 4 is as dark as the clock ever gets.
NIGHT_MAX = 4

_PLAYER = frozenset(colors.PLAYER_COLORS)


def multipliers(night, light_level=0):
    """The engine's two scale factors. -> (rg, b)

    light_level is env_t's brightness slider; the game passes 0 by default and
    the term is written exactly as the engine writes it, ((l + 8) / 8), so that
    a non-zero slider gives the same numbers here as it does in the game.
    """
    return (0.75 ** night) * ((light_level + 8.0) / 8.0), \
           (0.83 ** night) * ((light_level + 8.0) / 8.0)


def _scale(rgb, rg, b):
    # (int) in C truncates, and the engine casts to uint8 - so do we, and clamp
    # rather than wrap, because a wrapped highlight would be a lie about the game
    r, g, bl = rgb
    return (min(255, int(r * rg)), min(255, int(g * rg)), min(255, int(bl * b)))


def shade(rgb, night, light_level=0):
    """One pixel, day -> night. rgb is a 3-tuple; the result is a 3-tuple.

    night=0 is NOT the identity, and that is on purpose: the ordinary path still
    goes through the 555 quantiser, because the game shows a 555 pixel at noon
    too. shade(rgb, 0) is what the artwork looks like in the game by DAY.
    """
    lit = colors.LIGHT_DAY.get(tuple(rgb))
    if lit is not None:
        # the lights: a blend, at full brightness, never darkened
        n = min(night, NIGHT_MAX)
        day_w = NIGHT_MAX - n
        night_rgb = lit[0]
        return tuple((rgb[i] * day_w + night_rgb[i] * n) >> 2 for i in range(3))

    rg, b = multipliers(night, light_level)
    if tuple(rgb) in _PLAYER:
        # an index in the pak, not a colour: no 555 quantiser on this path
        return _scale(rgb, rg, b)

    # everything else IS 555 in the pak, so throw away the low three bits first -
    # otherwise the preview would be kinder to the artwork than the game is
    return _scale((rgb[0] & 0xF8, rgb[1] & 0xF8, rgb[2] & 0xF8), rg, b)


def shade_pixels(pixels, night, light_level=0):
    """A whole image. Alpha is carried through untouched."""
    cache = {}
    out = []
    for px in pixels:
        key = (px[0], px[1], px[2])
        got = cache.get(key)
        if got is None:
            got = cache[key] = shade(key, night, light_level)
        out.append(got + (px[3],) if len(px) > 3 else got)
    return out


def lights_in(pixels, ignore_transparent=True):
    """Which light colours are present, and how many pixels of each.

    -> {day_rgb: count}, only for lights that actually CHANGE at night. The five
    non-darkening greys are in the engine's light table too, but their night
    entry equals their day entry: they hold their brightness, they do not glow.
    Counting them as "lights" would tell an artist their train lights up when it
    does not.
    """
    hits = {}
    for px in pixels:
        if ignore_transparent and len(px) > 3 and px[3] == 0:
            continue
        rgb = (px[0], px[1], px[2])
        lit = colors.LIGHT_DAY.get(rgb)
        if lit is None or lit[0] == rgb:
            continue
        hits[rgb] = hits.get(rgb, 0) + 1
    return hits


def preview(src_png, dst_png, night=NIGHT_MAX, light_level=0):
    """Write the night version of a sheet. -> {day_rgb: count} of what will glow."""
    width, height, has_alpha, px = sheet.read_png(src_png)
    sheet.write_png(dst_png, width, height, shade_pixels(px, night, light_level),
                    has_alpha=has_alpha)
    return lights_in(px)


def report(hits):
    """Human-readable lines for lights_in(), biggest first."""
    lines = []
    for rgb, count in sorted(hits.items(), key=lambda kv: -kv[1]):
        night, what = colors.LIGHT_DAY[rgb]
        lines.append("%d px #%02X%02X%02X -> #%02X%02X%02X at night (%s)"
                     % (count, rgb[0], rgb[1], rgb[2],
                        night[0], night[1], night[2], what))
    return lines
