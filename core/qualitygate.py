"""One verdict for a whole addon, and the contract a downstream tool can trust.

The kit grew a checker per question - a scene audit, a per-direction sheet check, a
special-colour check, a consist-joint check, a .dat linter. Each is honest on its
own and each prints its own findings. What was missing is the single yes/no an
author (or a CI step, or an agent) actually needs: is this addon good to ship?

`combine` is that yes/no. It pools findings from every source into one list, rolls
the severities up, and PASSES exactly when nothing raised an ERROR - a WARNING is
advice, not a blocker, matching every module's own `blocking()`. It does not run the
checks (that needs decoded sheets, a Scene, .dat text - all I/O); the CLI in
tools/quality_gate.py gathers those and hands the finding groups in. Keeping the
roll-up pure means it is tested from literals, like everything else in core.

`manifest` is the contract. The independent Sprite Studio validates FOREIGN, non-
Blender sprites and must agree with this kit on what the reserved colours are, how
the eight directions map onto a sheet, which surfaces are meant to glow, and what a
carunit is - WITHOUT importing this kit's code (a separate repo). So the gate emits
those facts as a versioned JSON document, drawn live from the same modules the
checks use, and Sprite Studio reads that. One source of truth, no shared code, and
`manifest_version` lets the two repos evolve without silently disagreeing.
"""

from typing import NamedTuple

from . import colorcheck, colors, convoy, directioncheck, directions
from .scenecheck import Finding, ERROR, WARNING, INFORMATION  # noqa: F401

# Bump the MINOR on an additive change (a new field), the MAJOR when an existing
# field changes shape or meaning, so a consumer can refuse a manifest it predates.
MANIFEST_VERSION = "1.0"

_ORDER = {ERROR: 0, WARNING: 1, INFORMATION: 2}


class GateResult(NamedTuple):
    """passed is the single yes/no; findings is every source's output, ERROR first;
    counts is per-level totals; by_source keeps each group for a detailed report."""
    passed: bool
    findings: tuple
    counts: dict
    by_source: dict


def combine(groups):
    """Pool finding groups into one verdict.

    groups: iterable of (source_name, findings) where findings are scenecheck.Finding
    (the .dat linter's findings are adapted to that shape by the caller, so the pool
    is uniform). PASSES iff no ERROR was raised anywhere.
    """
    all_findings = []
    by_source = {}
    for source, findings in groups:
        findings = tuple(findings)
        # Accumulate, never overwrite: two groups may legitimately share a name
        # (e.g. two fixed units with the same lead car), and dropping one would hide
        # findings that are still counted.
        by_source[source] = by_source.get(source, ()) + findings
        all_findings.extend(findings)

    counts = {ERROR: 0, WARNING: 0, INFORMATION: 0}
    for f in all_findings:
        # Fail CLOSED: a finding whose level is not one of the three canonical
        # constants (a mis-adapted or future level) counts as an ERROR, so it can
        # never silently pass the gate.
        counts[f.level if f.level in counts else ERROR] += 1

    ordered = tuple(sorted(all_findings, key=lambda f: _ORDER.get(f.level, 0)))
    return GateResult(counts[ERROR] == 0, ordered, counts, by_source)


def manifest(pakset="pak128", tile_px=128):
    """The versioned contract Sprite Studio consumes. Pure; drawn from the same
    modules the checks use, so it can never drift from what the kit enforces."""
    return {
        "manifest_version": MANIFEST_VERSION,
        "generator": "simutrans-blender-kit",
        "pakset": pakset,
        "tile_px": tile_px,
        "directions": {
            "codes": list(directions.DIR_CODES),
            "cols": 4,
            "azimuth_base_deg": directions.BASE_AZIMUTH_DEG,
            "families": {
                "broadside": list(directioncheck.BROADSIDE),
                "end_on": list(directioncheck.END_ON),
                "cardinal": list(directioncheck.CARDINAL),
            },
            # A 4-code sheet (s,w,sw,se) is a COMPLETE symmetric vehicle: the engine
            # reuses image[dir-4] for the opposite heading. A consumer must accept a
            # 4-cell sheet and apply this fallback, not flag n/e/ne/nw as missing.
            "fallback": dict(directions.FALLBACK),
            "note": "broadside (sw/ne) widest silhouette, end-on (se/nw) narrowest; "
                    "the gate enforces exactly 'cols' columns, 1 or 2 rows",
        },
        "reserved_colours": {
            "transparent": list(colors.TRANSPARENT),
            "player_ramp_blue": [list(c) for c in colors.PLAYER_RAMP_BLUE],
            "player_ramp_gold": [list(c) for c in colors.PLAYER_RAMP_GOLD],
            "lights": [{"paint": list(day), "night": list(night), "what": what}
                       for day, night, what in colors.LIGHTS],
        },
        "glow_targets": [{"paint": list(t), "label": label}
                         for t, label in colorcheck.NEARMISS_TARGETS],
        "length": {
            "carunits_per_tile": convoy.CARUNITS_PER_TILE,
            "note": "a vehicle is trailed by the length of the car in FRONT of it",
        },
    }
