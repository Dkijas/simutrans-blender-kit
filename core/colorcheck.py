"""Special-colour analysis with LOCATION and NEAR-MISSES - the two things scan can't say.

`colors.scan` answers "which reserved colours are present, and how many". That is
the whole check today, and it leaves two questions the artist actually asks:

  WHERE is the offending pixel?   scan returns a count, not a place. On a 512x256
      sheet "3 px hit player-blue" sends you hunting eight cells by eye.

  What about the colour that is ALMOST a light?   The costliest colour bug in the
      kit is not an exact reserved hit - it is a near miss. colors.py's own
      docstring: a window painted one count off WINDOW_DARK "stays black forever,
      and nothing tells you why". An exact-match scan is blind to it by definition.

This module adds both, on top of colors (it never re-defines a reserved value), and
emits scenecheck.Finding so the Quality Gate pools it with the other checks.

WHY NEAR-MISS IS SCOPED, NOT BLANKET
    A near-miss to just any reserved colour would cry wolf on correct art: the
    LIGHTS table holds five "non-darkening greys" that are ordinary bodywork
    colours, so a grey vehicle is full of pixels one or two counts off them - not a
    bug. So near-miss targets only the colours where "nearly right" almost always
    means "meant to light, painted dead": the WINDOW glow colours, the HEADLIGHT,
    and the one lamp whose paint value is a known trap - the PURPLE signal lamp,
    which colors.py documents as painted 0xFF017F but drawn 0xE100E1, so a one-off
    slip is especially easy. The saturated red/green/yellow/blue lamps are left out:
    those ARE common livery colours, and targeting them would false-positive.

TWO GUARDS AGAINST A FALSE POSITIVE ON CORRECT ART
    1. Only opaque pixels count (alpha >= OPAQUE_ALPHA), the same threshold the rest
       of the toolchain uses - a soft anti-aliased edge is not a painted surface.
    2. A near-miss to a glow colour is suppressed IN A CELL WHERE THAT EXACT GLOW
       COLOUR ALSO APPEARS. A correctly-painted window is a patch of the exact
       colour with an anti-aliased fringe a count or two off it; a DEAD window is
       the fringe with no exact core. Suppressing per-cell keeps the dead-window
       catch while sparing the fringe of a working one - the false positive an
       earlier version raised on hand-antialiased foreign art.

    Honest limit: WINDOW_DARK (0x57656F) is itself a desaturated blue-grey, so a
    vehicle in a dark-BLUE livery with no windows at all could draw an advisory
    near-glow-miss (a WARNING, never a block). No shipped pak128 art does; if it
    becomes a nuisance the fix is a minimum-area gate, not removing the target.
"""

from . import colors
from .scenecheck import Finding, ERROR, WARNING, INFORMATION, blocking  # noqa: F401
from .spritemetrics import OPAQUE_ALPHA

# The glow colours worth a near-miss check. A pixel a hair off one of these was
# meant to light and will not. See the docstring for what is deliberately absent.
NEARMISS_TARGETS = (
    (colors.WINDOW_DARK, "window (warm yellow at night)"),        # 0x57656F
    (colors.LIGHTS[11][0], "window (warm yellow at night)"),      # 0xC1B1D1, pale lavender variant
    (colors.WINDOW_LIGHT, "window (blue at night)"),              # 0x7F9BF1
    (colors.HEADLIGHT, "headlight (white by day, yellow at night)"),  # 0xE3E3FF
    (colors.LAMP_PURPLE, "purple signal lamp (paint #FF017F; the game draws #E100E1)"),
)

# How far off still counts as "you meant this glow colour". One or two counts is the
# documented mistake; wider than that and it is a different colour, not a slip.
NEARMISS_MAX_DIST = 2


def _cheby(a, b):
    """Chebyshev (max-channel) distance. The engine matches colour EXACTLY, so any
    non-zero distance already fails to light; this measures how near the miss was."""
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]), abs(a[2] - b[2]))


def nearest_glow(rgb):
    """(target_rgb, label, dist) of the nearest glow colour within range, or None.

    Returns None for a pixel that is exactly reserved (that is scan's job, not a
    miss) or that is not close to any glow colour."""
    if rgb in colors.RESERVED:
        return None
    best = None
    for target, label in NEARMISS_TARGETS:
        d = _cheby(rgb, target)
        if d <= NEARMISS_MAX_DIST and (best is None or d < best[2]):
            best = (target, label, d)
    return best


def _opaque(p):
    """A painted pixel, by the toolchain's shared threshold. A 3-tuple has no alpha
    and is opaque; a 4-tuple must clear OPAQUE_ALPHA, so edge feathering is excluded
    from colour analysis exactly as it is excluded from silhouette measurement."""
    return len(p) < 4 or p[3] >= OPAQUE_ALPHA


def _histogram(pixels):
    """{(r,g,b): count} over every OPAQUE pixel. RGB only: alpha is not a colour."""
    hist = {}
    for p in pixels:
        if not _opaque(p):
            continue
        rgb = (p[0], p[1], p[2])
        hist[rgb] = hist.get(rgb, 0) + 1
    return hist


def _locate(pixels, width, tile_px, wanted):
    """{rgb: {(row,col): count}} for the wanted colours, opaque pixels only. One pass,
    and only for the handful already flagged, so it stays cheap. Skips transparent
    pixels for the same reason _histogram does - read_png keeps RGB under alpha 0, so
    a transparent background must not add phantom cells to a colour's location."""
    out = {rgb: {} for rgb in wanted}
    if not wanted:
        return out
    for i, p in enumerate(pixels):
        if not _opaque(p):
            continue
        rgb = (p[0], p[1], p[2])
        if rgb not in out:
            continue
        cell = ((i // width) // tile_px, (i % width) // tile_px)
        out[rgb][cell] = out[rgb].get(cell, 0) + 1
    return out


def _fmt_cells(cells):
    return ", ".join("(%d,%d)" % rc for rc in sorted(cells))


def check(pixels, width, height, tile_px):
    """Special-colour findings for a decoded sheet -> (Finding, ...), ERROR first.

    pixels: flat RGB/RGBA tuples (core.sheet.read_png). width*height must match.
    """
    if len(pixels) != width * height:
        raise ValueError("pixels has %d entries, expected width*height=%d"
                         % (len(pixels), width * height))

    hist = _histogram(pixels)

    player = {rgb: n for rgb, n in hist.items() if rgb in colors.PLAYER_COLORS}
    near = {}
    for rgb in hist:
        g = nearest_glow(rgb)
        if g:
            near[rgb] = g                      # (target, label, dist)

    present_targets = {t for t, _label in NEARMISS_TARGETS if t in hist}
    wanted = set(player) | set(near) | present_targets
    loc = _locate(pixels, width, tile_px, wanted)
    exact_cells = {t: set(loc.get(t, {})) for t in present_targets}

    out = []

    # The actionable one: a surface that will not glow - reported only in cells that
    # do NOT also carry the exact glow colour (those are a working window's fringe).
    ranked = sorted(near.items(), key=lambda kv: -sum(loc.get(kv[0], {}).values()))
    for rgb, (target, label, dist) in ranked:
        cells = loc.get(rgb, {})
        suppress = exact_cells.get(target, set())
        kept = {c: n for c, n in cells.items() if c not in suppress}
        if not kept:
            continue                           # only ever near a correct window's edge
        n = sum(kept.values())
        out.append(Finding(
            WARNING, "near-glow-miss",
            "%d px are %d off the %s colour #%02X%02X%02X (painted #%02X%02X%02X, "
            "cells %s). The engine matches colour exactly, so these render flat and "
            "never light. Paint the exact value to glow"
            % (n, dist, label, target[0], target[1], target[2],
               rgb[0], rgb[1], rgb[2], _fmt_cells(kept))))

    # Informational: exact player colours. Could be a livery, could be an accident -
    # only the artist knows, so we locate it and let them judge, never block.
    for rgb, n in sorted(player.items(), key=lambda kv: -kv[1]):
        out.append(Finding(
            INFORMATION, "player-colour",
            "%d px are exactly %s #%02X%02X%02X (cells %s) - recoloured per player "
            "at runtime. Intended for a livery stripe; a bug on other bodywork"
            % (n, colors.classify(rgb), rgb[0], rgb[1], rgb[2],
               _fmt_cells(loc.get(rgb, {})))))

    order = {ERROR: 0, WARNING: 1, INFORMATION: 2}
    return tuple(sorted(out, key=lambda f: order[f.level]))
