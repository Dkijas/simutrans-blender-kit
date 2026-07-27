"""The one-verdict roll-up and the downstream contract.

    python tests/test_qualitygate.py

combine() is pure severity arithmetic, so it is tested from literal findings: an
ERROR anywhere fails the gate, a WARNING never does, and the pooled list comes out
ERROR-first. manifest() is the contract another repo depends on, so it is tested for
the fields that contract promises and for being JSON-serialisable and stable.
"""

import json
import os
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core import qualitygate, sheet                                 # noqa: E402
from core.qualitygate import ERROR, WARNING, INFORMATION           # noqa: E402
from core.scenecheck import Finding                                 # noqa: E402
from tools import quality_gate                                      # noqa: E402

FAILED = []


def check(name, cond, detail=""):
    if cond:
        print("  ok   %s" % name)
    else:
        print("  FAIL %s  %s" % (name, detail))
        FAILED.append(name)


def test_no_findings_passes():
    r = qualitygate.combine([("direction", ()), ("colour", ())])
    check("an addon with no findings passes", r.passed)
    check("counts are all zero", r.counts[ERROR] == 0 and r.counts[WARNING] == 0)
    check("both sources are recorded", set(r.by_source) == {"direction", "colour"})


def test_a_single_error_fails_the_gate():
    groups = [("direction", (Finding(WARNING, "facing-order", "x"),)),
              ("colour", (Finding(ERROR, "missing-direction", "y"),))]
    r = qualitygate.combine(groups)
    check("one ERROR anywhere fails the gate", r.passed is False)
    check("the error is counted", r.counts[ERROR] == 1)
    check("the warning is counted too", r.counts[WARNING] == 1)


def test_warnings_and_info_alone_pass():
    groups = [("a", (Finding(WARNING, "w", "x"), Finding(INFORMATION, "i", "y")))]
    r = qualitygate.combine(groups)
    check("warnings and information do not fail the gate", r.passed)


def test_the_pool_is_error_first():
    groups = [("a", (Finding(INFORMATION, "i", "x"),
                     Finding(ERROR, "e", "y"),
                     Finding(WARNING, "w", "z")))]
    r = qualitygate.combine(groups)
    levels = [f.level for f in r.findings]
    check("pooled findings are ERROR, then WARNING, then INFORMATION",
          levels == [ERROR, WARNING, INFORMATION], str(levels))


def test_manifest_carries_the_contract_fields():
    m = qualitygate.manifest("pak128", 128)
    # Pinned to a LITERAL, not to the constant it is emitted from: an undeclared
    # version bump must fail this test, not tautologically pass it.
    check("the version is exactly 1.0", m.get("manifest_version") == "1.0",
          str(m.get("manifest_version")))
    check("tile size and pakset", m["tile_px"] == 128 and m["pakset"] == "pak128")
    check("all eight directions", len(m["directions"]["codes"]) == 8)
    check("the silhouette families", set(m["directions"]["families"]) ==
          {"broadside", "end_on", "cardinal"})
    check("the 4-direction fallback mapping", set(m["directions"]["fallback"]) ==
          {"n", "e", "ne", "nw"})
    check("16 player-colour ramp entries",
          len(m["reserved_colours"]["player_ramp_blue"]) == 8
          and len(m["reserved_colours"]["player_ramp_gold"]) == 8)
    check("the full lights table", len(m["reserved_colours"]["lights"]) == 15)
    check("at least the three glow targets", len(m["glow_targets"]) >= 3)
    check("the carunit definition", m["length"]["carunits_per_tile"] == 16)


def test_manifest_entry_shapes_are_the_contract():
    """Sprite Studio reads entry KEYS, not just counts. A same-arity re-key upstream
    would pass a length check but silently break the contract, so pin the shape."""
    m = qualitygate.manifest()
    check("every glow target is {paint, label}",
          all(set(g) == {"paint", "label"} for g in m["glow_targets"]))
    check("every light is {paint, night, what}",
          all(set(l) == {"paint", "night", "what"}
              for l in m["reserved_colours"]["lights"]))
    check("a glow paint is a 3-channel colour",
          all(len(g["paint"]) == 3 for g in m["glow_targets"]))


def test_manifest_is_json_serialisable_and_stable():
    a = qualitygate.manifest()
    # json.dumps does NOT raise on a stray tuple (it serialises to an array); the
    # b == a round-trip below is the real guard, since json.loads returns lists and
    # a leaked tuple would then compare unequal.
    b = json.loads(json.dumps(a))
    check("the manifest round-trips through JSON (no leaked tuple)", b == a)
    check("two calls are identical", qualitygate.manifest() == a)


# ---------------------------------------------------------------- gather() (the CLI)
#
# The orchestration - pairing dats with sheets, deciding what to check - is where the
# real false-PASS lived, and combine()/manifest() tests could not see it. These drive
# gather() over a temporary addon on disk.

_TILE = 128
_GOOD_DIR = {"s": (52, 42), "n": (52, 42), "w": (52, 42), "e": (52, 42),
             "sw": (57, 28), "ne": (57, 28), "se": (20, 46), "nw": (20, 46)}
_CODES = ("s", "w", "sw", "se", "n", "e", "ne", "nw")


def _good_vehicle_sheet(drop=None):
    """A well-formed 4x2 eight-direction sheet; `drop` blanks one direction's cell."""
    cols, rows = 4, 2
    W, H = cols * _TILE, rows * _TILE
    px = [(0, 0, 0, 0)] * (W * H)
    place = {c: divmod(i, cols) for i, c in enumerate(_CODES)}
    for code, (w, h) in _GOOD_DIR.items():
        if code == drop:
            continue
        r, c = place[code]
        x0, y0 = (_TILE - w) // 2 + c * _TILE, (_TILE - h) // 2 + r * _TILE
        for y in range(y0, y0 + h):
            for x in range(x0, x0 + w):
                px[y * W + x] = (180, 60, 60, 255)
    return W, H, px


def _make_addon(root, dats, sheets):
    """dats: {base: dat_text}; sheets: {base: (W,H,px) or 'RAW:<bytes hex>' or None}."""
    os.makedirs(os.path.join(root, "dat"))
    os.makedirs(os.path.join(root, "sprites"))
    for base, text in dats.items():
        with open(os.path.join(root, "dat", base + ".dat"), "w") as fh:
            fh.write(text)
    for base, s in sheets.items():
        if s is None:
            continue
        p = os.path.join(root, "sprites", base + ".png")
        if isinstance(s, bytes):
            with open(p, "wb") as fh:
                fh.write(s)
        else:
            W, H, px = s
            sheet.write_png(p, W, H, px, has_alpha=True)


def _veh(name, length=8, nxt=None):
    t = "obj=vehicle\nname=%s\nlength=%d\n" % (name, length)
    if nxt:
        t += "Constraint[Next][0]=%s\n" % nxt
    return t


def _gate(root):
    groups, scored = quality_gate.gather(root, _TILE)
    r = qualitygate.combine(groups)
    return r, (r.passed and scored)


def test_a_good_vehicle_addon_passes():
    with tempfile.TemporaryDirectory() as d:
        _make_addon(d, {"cab_a": _veh("A")}, {"cab_a": _good_vehicle_sheet()})
        r, passed = _gate(d)
        check("a well-formed vehicle addon passes", passed,
              str([f.code for f in r.findings if f.level == ERROR]))


def test_a_blanked_direction_fails():
    with tempfile.TemporaryDirectory() as d:
        _make_addon(d, {"cab_a": _veh("A")}, {"cab_a": _good_vehicle_sheet(drop="ne")})
        r, passed = _gate(d)
        check("a dropped direction fails the gate", not passed)
        check("with a missing-direction error",
              any(f.code == "missing-direction" for f in r.findings))


def test_a_non_vehicle_with_no_sheet_fails():
    """The false PASS the review caught: a building was graded on dat-lint alone."""
    with tempfile.TemporaryDirectory() as d:
        _make_addon(d, {"house": "obj=building\nname=MyHouse\n"}, {"house": None})
        r, passed = _gate(d)
        check("a non-vehicle addon whose sheet is missing FAILS (not graded on lint alone)",
              not passed)
        check("with a no-sprite error", any(f.code == "no-sprite" for f in r.findings))


def test_a_corrupt_sheet_is_a_finding_not_a_crash():
    with tempfile.TemporaryDirectory() as d:
        corrupt = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\x0dIHDR" + b"\xde\xad" * 8
        _make_addon(d, {"cab_a": _veh("A")}, {"cab_a": corrupt})
        r, passed = _gate(d)      # must not raise
        check("a corrupt sheet fails the gate rather than crashing it", not passed)
        check("as a bad-sheet error", any(f.code == "bad-sheet" for f in r.findings))


def test_an_unusual_layout_is_reported_not_measured_wrong():
    with tempfile.TemporaryDirectory() as d:
        # an 8x1 strip: valid to makeobj, but not the canonical 4x2 the manifest declares
        W, H = 8 * _TILE, _TILE
        px = [(180, 60, 60, 255)] * (W * H)
        _make_addon(d, {"cab_a": _veh("A")}, {"cab_a": (W, H, px)})
        r, _passed = _gate(d)
        check("a non-standard layout is reported as unusual-layout",
              any(f.code == "unusual-layout" for f in r.findings))


def test_a_duplicate_vehicle_name_is_an_error():
    with tempfile.TemporaryDirectory() as d:
        _make_addon(d, {"a": _veh("SAME"), "b": _veh("SAME")},
                    {"a": _good_vehicle_sheet(), "b": _good_vehicle_sheet()})
        r, passed = _gate(d)
        check("two dats sharing a vehicle name fail the gate", not passed)
        check("with a duplicate-name error",
              any(f.code == "duplicate-name" for f in r.findings))


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            print("\n%s" % name)
            fn()
    print()
    if FAILED:
        print("QUALITYGATE_TESTS_FAILED: %d" % len(FAILED))
        for f in FAILED:
            print("  - %s" % f)
        sys.exit(1)
    print("QUALITYGATE_TESTS_OK")


if __name__ == "__main__":
    main()
