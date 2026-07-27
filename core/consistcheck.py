"""Does a whole unit's cars line up? Joint geometry, judged on the rendered sheets.

`convoy.py` establishes the engine's one rule - a car is trailed by the length of
the one in FRONT, and equal-length cars butt only if each body is drawn to its
declared length - and is emphatic that a .dat cannot be linted for it: mixed
lengths with off-centre art are correct, shipped pak128 art, so "these lengths
differ" is not a defect. This module respects that: it never judges the DECLARED
lengths. What it can honestly judge is what convoy.py could not see - the RENDERED
body against the length it was declared as.

THE ONE JUDGEMENT: body vs declared length, on the broadside view
    A car declared length L reserves L/16 of a tile of track. On the broadside
    heading (sw/ne) the body is seen full-length across the screen, so its
    silhouette WIDTH is (near enough) the body's length in pixels. If that width is
    far from the L/16-tile the engine reserves, the body was modelled or declared at
    the wrong length, and coupled cars overlap (body too long) or gap (too short) -
    on every heading, not just this one.

    This is the sheet-side twin of scenecheck's `length-mismatch`, which checks the
    3D model's X-span. Here it needs no .blend, so it works on a delivered or
    foreign addon, and it was the question the FLIRT raised. Measured answer: the
    FLIRT's ratio (0.89 cab, 0.81 int) is identical to the shipped, in-game-correct
    Civia (0.89) and Metro (0.81) - all length 8 - so the FLIRT bodies match their
    declared length exactly as well as art that couples cleanly. The band below is
    calibrated from those: correct art sits at ~0.8-0.9 (the rest of the tile is the
    coupler slack), so only a gross miss is flagged.

    END-ON (se/nw) is NOT used for this: its silhouette HEIGHT conflates the body's
    length with the car's actual height, so it is no clean measure of length.

Everything else - the per-joint gap, the art offset each car needs - is COMPUTED and
reported as INFORMATION, never judged, exactly as convoy.py prescribes.
"""

from typing import NamedTuple

from . import convoy, directioncheck
from .scenecheck import Finding, ERROR, WARNING, INFORMATION, blocking  # noqa: F401

# Broadside footprint / declared-length spacing. Correct shipped art measures
# 0.81-0.89 (Civia, Metro, FLIRT - all length 8), the shortfall being the coupler
# zone. The band is wide around that so only a body grossly mis-sized for its
# declared length - scenecheck's "declared 8, modelled 16" (ratio ~1.8) or its
# inverse (~0.44) - is flagged, and correct art never is.
LEN_RATIO_GAP = 0.55        # below: body too short for its length -> cars gap
LEN_RATIO_OVERLAP = 1.30    # above: body too long -> cars overlap

# The band and the 0.85 coupler-slack constant were calibrated ONLY on length-8 art
# (Civia, Metro, FLIRT). The coupler gap is a roughly fixed number of PIXELS, so as
# a fraction it grows on short cars - a length-2 tram could read below the gap floor
# with no fault. Until the band is validated against a measured short pak128 tram,
# do not judge lengths below this; the joint report still lists them, and
# scenecheck's 3D length-mismatch still covers the model side.
MIN_JUDGED_LENGTH = 4


class Car(NamedTuple):
    """One car of a unit, as this check needs it.

    metrics is {direction_code: spritemetrics.CellMetrics} for the car's own sheet -
    what spritemetrics.measure returns. length is the DECLARED length in carunits.
    """
    name: str
    length: int
    metrics: dict


def broadside_footprint(metrics):
    """The body's on-screen length in px: the mean broadside (sw/ne) silhouette
    width, over whichever of the two are present. None if neither is.

    If sw and ne disagree wildly, one of them is clipped or mis-rendered - and
    directioncheck's opposite-mismatch already owns that fault. Averaging a clipped
    cell could slip a bad ratio into the passing band, so we decline to judge length
    from it and return None rather than a misleading mean."""
    widths = [metrics[c].width for c in directioncheck.BROADSIDE
              if c in metrics and metrics[c].present]
    if not widths:
        return None
    if len(widths) == 2 and abs(widths[0] - widths[1]) > max(8, 0.08 * max(widths)):
        return None
    return sum(widths) / len(widths)


def length_spacing_px(length, tile_px):
    """The screen px a car of this length reserves along a broadside heading: one
    tile of that heading is tile_px across, and the car is length/16 of a tile."""
    return convoy.carunits_to_tiles(length) * tile_px


def body_length_ratio(car, tile_px):
    """Rendered broadside body length / declared-length spacing, or None if it
    cannot be measured (no broadside view, or a non-positive length)."""
    fp = broadside_footprint(car.metrics)
    if fp is None or car.length <= 0:
        return None
    return fp / length_spacing_px(car.length, tile_px)


def check(cars, tile_px):
    """Joint findings for an assembled unit -> (Finding, ...), ERROR first.

    cars: the unit's Car records, in coupling order (leading car first).
    """
    if tile_px <= 0:
        raise ValueError("tile_px must be positive")     # parity with spritemetrics.measure

    out = []

    for car in cars:
        if car.length < MIN_JUDGED_LENGTH:
            continue     # too short to judge from a ratio (see MIN_JUDGED_LENGTH)
        ratio = body_length_ratio(car, tile_px)
        if ratio is None:
            continue
        if ratio > LEN_RATIO_OVERLAP or ratio < LEN_RATIO_GAP:
            fp = broadside_footprint(car.metrics)
            sp = length_spacing_px(car.length, tile_px)
            kind = "overlap" if ratio > LEN_RATIO_OVERLAP else "gap"
            # The length that WOULD match this body, at the ~0.85 the coupler slack
            # leaves - a concrete number to declare instead of "resize it somehow".
            # Clamped to 1: a degenerate sliver body rounds toward 0, and length=0 is
            # not a value any .dat can carry.
            want = max(1, round(fp / tile_px * convoy.CARUNITS_PER_TILE / 0.85))
            out.append(Finding(
                WARNING, "length-fidelity",
                "%s: the side view is %.0f px but length=%d reserves %.0f px of "
                "track (ratio %.2f). The body is drawn for a different length, so "
                "coupled cars will %s. Declare length=%d, or resize the model"
                % (car.name, fp, car.length, sp, ratio, kind, want)))

    # Everything below is COMPUTED, never judged (convoy.py's rule).
    if len(cars) >= 2:
        names = [c.name for c in cars]
        lengths = [c.length for c in cars]
        for line in convoy.describe(names, lengths, tile_px):
            out.append(Finding(INFORMATION, "joint-plan", line))

    if cars:
        out.append(Finding(
            INFORMATION, "consist",
            "unit of %d cars: %s" % (len(cars),
                                     ", ".join("%s(len %d)" % (c.name, c.length)
                                               for c in cars))))

    order = {ERROR: 0, WARNING: 1, INFORMATION: 2}
    return tuple(sorted(out, key=lambda f: order[f.level]))
