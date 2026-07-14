"""
Simutrans reserved colours, and a validator for accidental hits.

Values taken from the engine's own palette, documentation/simutrans-palette.pal
(JASC-PAL, 256 entries), NOT copied from a wiki page:

  entries  0..7   player-colour ramp 1 ("blue"):  36,75,103  ->  176,210,255
  entries 24..31  player-colour ramp 2 ("gold"): 123,88,3    ->  255,249,13

The transparency key 231,255,255 is deliberately NOT in that palette: it is not
a colour the game ever draws, it is a marker that makeobj turns into alpha.

Why the validator matters
-------------------------
The engine stores colour in 15 bits and matches reserved colours EXACTLY, so a
stray pixel that happens to land on a player-colour blue will be recoloured at
runtime - a shirt, a window, a bit of sky in a reflection. pak128's own
devdocs/128painting.txt shouts about this:

    "It is important to check your images for unwanted occurrence of those
     colors!!!!"

and no existing tool checks it. This module does.
"""

# makeobj turns exactly this colour into transparency.
TRANSPARENT = (231, 255, 255)

# Recoloured per player at runtime.
PLAYER_RAMP_BLUE = (
    (36, 75, 103), (57, 94, 124), (76, 113, 145), (96, 132, 167),
    (116, 151, 189), (136, 171, 211), (156, 190, 233), (176, 210, 255),
)

PLAYER_RAMP_GOLD = (
    (123, 88, 3), (142, 111, 4), (161, 134, 5), (180, 157, 7),
    (198, 180, 8), (217, 203, 10), (236, 226, 11), (255, 249, 13),
)

PLAYER_COLORS = PLAYER_RAMP_BLUE + PLAYER_RAMP_GOLD

# THE LIGHTS. This is how a lit window happens in Simutrans, and it is not a
# render trick: it is a colour swap. So a train whose windows are painted
# (87,101,111) glows warm yellow after dark, and one whose windows are painted
# (86,92,100) - one count away - stays black forever, and nothing tells you why.
#
# WHICH TABLE. The engine has TWO, and taking the wrong one is a silent, total
# failure:
#
#   descriptor/image.cc     image_t::rgbtab[]      what MAKEOBJ matches against
#   display/simgraph16.cc   display_day_lights[]   what the game DRAWS
#
# The first column below is rgbtab - the colour the artist must actually PAINT,
# because image_writer.cc:96 compares each pixel against rgbtab and nothing else.
# Miss it by one and the pixel is compiled as an ordinary colour that will never
# light up.
#
# The two tables agree on fourteen of the fifteen entries, which is why this went
# unnoticed. They disagree on the purple:
#
#     rgbtab            0xFF017F   <- paint this
#     display_day_light  0xE100E1   <- and the game shows you this
#
# This module used to list 0xE100E1 as the colour to paint. Every signal built
# with the kit compiled its purple lamp as a flat colour, and it never lit.
#
# The greys are in the table too, for menu art that must not darken at night;
# they are here because hitting one by ACCIDENT on a vehicle is its own bug - a
# patch of bodywork that refuses to get dark while everything round it does.
#
# tests/test_schema_drift.py re-reads both tables out of the engine source and
# compares them with this one, entry by entry. Copying a table by hand is what
# caused the bug; the fix is not to copy it more carefully.
#
#         paint this (rgbtab)      shown at night           what it is
LIGHTS = (
    ((0x57, 0x65, 0x6F), (0xD3, 0xC3, 0x80), "dark window, lit yellow at night"),
    ((0x7F, 0x9B, 0xF1), (0x80, 0xC3, 0xD3), "light window, lit blue at night"),
    ((0xFF, 0xFF, 0x53), (0xFF, 0xFF, 0x53), "yellow light"),
    ((0xFF, 0x21, 0x1D), (0xFF, 0x21, 0x1D), "red light"),
    ((0x01, 0xDD, 0x01), (0x01, 0xDD, 0x01), "green light"),
    ((0x6B, 0x6B, 0x6B), (0x6B, 0x6B, 0x6B), "non-darkening grey 1"),
    ((0x9B, 0x9B, 0x9B), (0x9B, 0x9B, 0x9B), "non-darkening grey 2"),
    ((0xB3, 0xB3, 0xB3), (0xB3, 0xB3, 0xB3), "non-darkening grey 3"),
    ((0xC9, 0xC9, 0xC9), (0xC9, 0xC9, 0xC9), "non-darkening grey 4"),
    ((0xDF, 0xDF, 0xDF), (0xDF, 0xDF, 0xDF), "non-darkening grey 5"),
    ((0xE3, 0xE3, 0xFF), (0xFF, 0xFF, 0xE3), "white by day, yellow by night"),
    ((0xC1, 0xB1, 0xD1), (0xD3, 0xC3, 0x80), "window, lit yellow"),
    ((0x4D, 0x4D, 0x4D), (0xD3, 0xC3, 0x80), "window, lit yellow"),
    ((0xFF, 0x01, 0x7F), (0xE1, 0x00, 0xE1), "purple signal light"),
    ((0x01, 0x01, 0xFF), (0x01, 0x01, 0xFF), "blue light"),
)

# The purple is the one light whose painted colour is not what you see, so the
# artist needs it by name rather than by counting rows.
LAMP_PURPLE = LIGHTS[13][0]      # paint 0xFF017F; the game draws 0xE100E1

LIGHT_DAY = {day: (night, what) for day, night, what in LIGHTS}

# The handy ones, named, so nobody has to count rows in a table:
WINDOW_DARK = LIGHTS[0][0]       # goes warm yellow at night. The one you want.
WINDOW_LIGHT = LIGHTS[1][0]      # goes blue at night
HEADLIGHT = LIGHTS[10][0]        # near-white by day, yellow after dark
LAMP_YELLOW = LIGHTS[2][0]
LAMP_RED = LIGHTS[3][0]
LAMP_GREEN = LIGHTS[4][0]

# Everything an artist must not hit by accident.
RESERVED = frozenset(PLAYER_COLORS) | frozenset(LIGHT_DAY) | {TRANSPARENT}


def classify(rgb: tuple) -> str | None:
    """Name the reserved meaning of a colour, or None if it is a free colour."""
    if rgb == TRANSPARENT:
        return "transparency key"
    if rgb in PLAYER_RAMP_BLUE:
        return "player colour (blue ramp)"
    if rgb in PLAYER_RAMP_GOLD:
        return "player colour (gold ramp)"
    if rgb in LIGHT_DAY:
        night, what = LIGHT_DAY[rgb]
        return "night light: %s -> %s at night" % (what, night)
    return None


def scan(pixels, ignore_transparent: bool = True) -> dict:
    """Count reserved-colour hits in an iterable of (r, g, b) tuples.

    Returns {rgb: count} for every reserved colour actually present. The
    transparency key is normally intentional (it IS the background), so it is
    ignored by default; pass ignore_transparent=False to include it.
    """
    hits = {}
    for rgb in pixels:
        if rgb not in RESERVED:
            continue
        if ignore_transparent and rgb == TRANSPARENT:
            continue
        hits[rgb] = hits.get(rgb, 0) + 1
    return hits


def report(hits: dict) -> list:
    """Human-readable lines for scan() output, worst offender first."""
    lines = []
    for rgb, count in sorted(hits.items(), key=lambda kv: -kv[1]):
        lines.append(
            "%d px hit %s -> #%02X%02X%02X %s"
            % (count, classify(rgb), rgb[0], rgb[1], rgb[2], rgb)
        )
    return lines
