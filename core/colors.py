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
# render trick: it is a colour swap. display/simgraph16.cc holds two tables,
# display_day_lights[] and display_night_lights[], matched EXACTLY, entry for
# entry; as night falls the engine fades each day colour into its night one.
#
# So a train whose windows are painted (87,101,111) glows warm yellow after dark
# and one whose windows are painted (86,92,100) - one count away - stays black
# forever, and nothing anywhere tells you why. The values below are copied from
# the engine, in order, with the engine's own comments.
#
# The greys are in the table too, for menu art that must not darken at night;
# they are listed because hitting one by ACCIDENT on a vehicle is its own bug -
# a patch of bodywork that refuses to get dark while everything round it does.
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
    ((0xE1, 0x00, 0xE1), (0xE1, 0x00, 0xE1), "purple signal light"),
    ((0x01, 0x01, 0xFF), (0x01, 0x01, 0xFF), "blue light"),
)

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
