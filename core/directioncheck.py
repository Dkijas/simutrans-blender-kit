"""Read a sheet's per-direction metrics and say what is wrong - after the render.

`scenecheck` catches the mistakes that are visible in the SCENE, before paying for
a render. This catches the ones that only exist in the finished SHEET: a direction
that came out empty, a model turned ninety degrees so its broadside and end-on
views are swapped, one heading rendered differently from its opposite, a body built
off the tile origin. None of these show up in the .dat or the scene bounds; all of
them are wrong in the game.

It works on ANY sheet, not only ones this kit rendered - it is handed decoded
pixels (see spritemetrics), so a foreign or hand-drawn sheet is checked the same
way. That is the property Sprite Studio will lean on.

GROUNDED IN MEASURED ART, NOT IN THEORY
    Every threshold below was set by measuring the kit's own shipped, in-game-
    correct vehicles (Civia 465, Metro 9000) and leaving a wide margin, exactly as
    scenecheck's docstring demands: a rule that refuses correct art gets turned off.
    The direction-family silhouette pattern - broadside widest, end-on narrowest -
    is not an assumption; it is what viewport geometry forces (directions.py) and
    what those sheets measure.

WHAT IS DELIBERATELY NOT HERE
    Whether consecutive cars gap or overlap. That is a property of the whole
    consist and its declared lengths, not of one sheet, and convoy.py is explicit
    that a tool may COMPUTE the joint offset but must not call a mixed-length unit a
    defect. It lives in the consist check (Phase 3), with the numbers it needs.
"""

from . import directions
from .scenecheck import Finding, ERROR, WARNING, INFORMATION, blocking  # noqa: F401

# The three silhouette families, from directions.py's measured geometry:
#   a vehicle on a world diagonal travels straight up/down the screen (end-on,
#   narrow) or straight across it (broadside, wide); the cardinals are the
#   three-quarter views in between.
BROADSIDE = ("sw", "ne")     # widest
END_ON = ("se", "nw")        # narrowest
CARDINAL = ("s", "w", "n", "e")

# Each heading and the opposite the engine would fall back to (directions.FALLBACK,
# both ways). Rendered separately for an 8-direction vehicle, they are the same
# body seen from opposite sides and must match in SIZE - never in pixels, since the
# far side genuinely differs.
OPPOSITE_PAIRS = (("s", "n"), ("w", "e"), ("sw", "ne"), ("se", "nw"))

# How far the opaque mass may sit from the cell's horizontal centre before we say
# so, as a fraction of the tile. Lenient on purpose: a cab car's nose shifts the
# mass a few pixels and that is correct art (measured: up to ~4 px on the Civia
# cab). A body actually built off the origin drifts far more.
OFF_CENTRE_TILES = 0.12

# Slack allowed between an opposite pair's box dimensions before it is a finding:
# the larger of a flat floor and a fraction of the dimension. The floor is what
# actually governs at pak128 scale - measured opposites vary only 2-3 px on correct
# art, so 8 px already clears every real difference. The relative term is kept small
# and only bites on much larger sprites; at 0.18 it opened a ~10 px window on a
# 57 px broadside (0.18*57=10.3), wide enough to hide a dropped coupler or car-end,
# so it is 0.08 - the floor stays in charge where the art was measured.
OPPOSITE_ABS_SLACK = 8
OPPOSITE_REL_SLACK = 0.08

# Slack on the facing-order test, same 8 px floor. Without it a strict inequality
# fires on a correct SHORT vehicle whose body is nearly as wide as it is long (a
# flatcar, a single-tile wagon): its end-on view can measure a pixel or two wider
# than its broadside one with no fault at all. The real 90-degree error is dramatic
# - a broadside of 57 against an end-on of 20 - so 8 px catches it and spares the
# near-square case.
FACING_ABS_SLACK = 8


def check(metrics, tile_px, expected_codes=None):
    """Everything worth saying about a measured sheet -> (Finding, ...), ERROR first.

    metrics: {code: spritemetrics.CellMetrics} - what `spritemetrics.measure` returns.
    expected_codes: the directions that SHOULD carry art (default: the keys given).
    A code that is expected but absent, or present but empty, is a missing render.
    """
    if expected_codes is None:
        expected_codes = tuple(metrics.keys())

    out = []
    out.extend(_check_present(metrics, expected_codes))
    out.extend(_check_facing(metrics))
    out.extend(_check_opposites(metrics))
    out.extend(_check_centre(metrics, tile_px))
    out.extend(_report_coverage(metrics))
    order = {ERROR: 0, WARNING: 1, INFORMATION: 2}
    return tuple(sorted(out, key=lambda f: order[f.level]))


def _present(metrics):
    """The codes that actually carry opaque art."""
    return {c: m for c, m in metrics.items() if m.present}


def _check_present(metrics, expected_codes):
    for code in expected_codes:
        m = metrics.get(code)
        if m is None or not m.present:
            yield Finding(ERROR, "missing-direction",
                          "Direction '%s' rendered nothing. The engine draws an "
                          "empty cell as an invisible vehicle at that heading"
                          % code)


def _check_facing(metrics):
    """Broadside (sw/ne) must be wider than end-on (se/nw). If it is not, the model
    is turned the wrong way or the cells were laid out in the wrong order - either
    way every diagonal heading faces wrong, and the sheet still lints and compiles.
    """
    have = _present(metrics)
    broad = [have[c].width for c in BROADSIDE if c in have]
    endon = [have[c].width for c in END_ON if c in have]
    if not broad or not endon:
        return
    if min(broad) + FACING_ABS_SLACK < max(endon):
        yield Finding(
            WARNING, "facing-order",
            "The end-on views (%s) are wider than the broadside views (%s): %d vs "
            "%d px. The model is likely turned 90 degrees, or the sheet's cells are "
            "in the wrong order" % ("/".join(END_ON), "/".join(BROADSIDE),
                                    max(endon), min(broad)))


def _check_opposites(metrics):
    have = _present(metrics)
    for a, b in OPPOSITE_PAIRS:
        if a not in have or b not in have:
            continue
        ma, mb = have[a], have[b]
        for dim, va, vb in (("width", ma.width, mb.width),
                            ("height", ma.height, mb.height)):
            slack = max(OPPOSITE_ABS_SLACK, OPPOSITE_REL_SLACK * max(va, vb))
            if abs(va - vb) > slack:
                yield Finding(
                    WARNING, "opposite-mismatch",
                    "Opposite headings '%s' and '%s' differ in %s by %d px (%d vs "
                    "%d). They are the same body from opposite sides and should be "
                    "the same size - check that both rendered the whole vehicle"
                    % (a, b, dim, abs(va - vb), va, vb))
                break     # one finding per pair is enough


def _check_centre(metrics, tile_px):
    centre = tile_px / 2.0
    tol = OFF_CENTRE_TILES * tile_px
    for code, m in metrics.items():
        if not m.present:
            continue
        off = m.cx - centre
        if abs(off) > tol:
            # Code is 'sprite-off-centre', distinct from scenecheck's 'off-centre':
            # that one measures the 3D model against the world origin before the
            # render; this measures opaque MASS against the cell centre after it.
            # The Quality Gate will pool both streams, and a shared stable code
            # would make them indistinguishable to anything routing by code.
            yield Finding(
                WARNING, "sprite-off-centre",
                "In direction '%s' the body's mass sits %.0f px %s of the cell "
                "centre. A vehicle is modelled on the tile origin; this one will "
                "make its joints uneven" % (code, abs(off),
                                            "right" if off > 0 else "left"))


def _report_coverage(metrics):
    """One measurement line per present direction. Never a judgement - the numbers
    are here so a human (or the consist check) can see the shape without re-running.

    Iterates the MEASURED codes, not the hardcoded engine order, so a sheet checked
    with custom --dirs codes still reports every cell it measured. Standard codes
    are shown in engine order first (that is the order `measure` built them in);
    any extra codes follow.
    """
    known = [c for c in directions.DIR_CODES if c in metrics]
    extra = [c for c in metrics if c not in directions.DIR_CODES]
    parts = []
    for code in known + extra:
        m = metrics[code]
        if m.present:
            parts.append("%s %dx%d" % (code, m.width, m.height))
    if parts:
        yield Finding(INFORMATION, "coverage",
                      "silhouettes: " + ", ".join(parts))
