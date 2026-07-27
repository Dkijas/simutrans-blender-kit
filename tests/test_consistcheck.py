"""Joint geometry of a whole unit, judged on the rendered sheets.

    python tests/test_consistcheck.py

The one judgement (body vs declared length) is tested three ways: a correctly-sized
body is silent, a body too long for its length warns of an overlap, a body too short
warns of a gap. The test that keeps the tool honest is the MIXED-length unit: convoy
.py proves that different lengths with off-centre art are correct shipped pak128 art,
so a unit of lengths [8,4,4] whose bodies each match their own length must raise NO
warning - only the computed, non-judgemental joint report. A real Civia pair closes
it: zero false positives on shipped, in-game-correct art.
"""

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core import consistcheck, sheet, spritemetrics                 # noqa: E402
from core import directions                                          # noqa: E402

FAILED = []
TILE = 128


def check(name, cond, detail=""):
    if cond:
        print("  ok   %s" % name)
    else:
        print("  FAIL %s  %s" % (name, detail))
        FAILED.append(name)


def codes(findings):
    return [f.code for f in findings]


def _cm(code, width):
    """A CellMetrics carrying just the broadside width the check reads; the rest is
    plausible filler."""
    return spritemetrics.CellMetrics(
        code=code, present=True, width=width, height=28, coverage=width * 28,
        cx=64.0, cy=90.0, left=64 - width // 2, right=64 + width // 2,
        top=76, bottom=104)


def _car(name, length, broadside_width):
    return consistcheck.Car(name, length,
                            {"sw": _cm("sw", broadside_width),
                             "ne": _cm("ne", broadside_width)})


def test_a_correctly_sized_unit_is_not_flagged():
    # length 8 reserves 64 px; a 54 px body is ratio 0.84, right where shipped art sits
    cars = [_car("A", 8, 54), _car("B", 8, 54), _car("C", 8, 54)]
    f = consistcheck.check(cars, TILE)
    check("no length-fidelity warning on correctly-sized cars",
          "length-fidelity" not in codes(f), str(codes(f)))
    check("it does report the joint plan", "joint-plan" in codes(f))
    check("and a consist summary", "consist" in codes(f))


def test_a_body_too_long_warns_of_overlap():
    cars = [_car("A", 8, 120)]        # 120 px vs 64 reserved: ratio 1.875
    f = consistcheck.check(cars, TILE)
    check("an over-long body is a length-fidelity warning",
          "length-fidelity" in codes(f))
    check("it does not block",
          "length-fidelity" not in codes(consistcheck.blocking(f)))
    check("the message says overlap",
          any("overlap" in x.message for x in f if x.code == "length-fidelity"))


def test_a_body_too_short_warns_of_gap():
    cars = [_car("A", 16, 57)]        # 57 px vs 128 reserved: ratio 0.45
    f = consistcheck.check(cars, TILE)
    check("an under-long body is a length-fidelity warning",
          "length-fidelity" in codes(f))
    check("the message says gap",
          any("gap" in x.message for x in f if x.code == "length-fidelity"))


def test_a_mixed_length_unit_is_not_a_defect():
    """convoy.py: lengths [8,4,4] with bodies each matching their own length is
    correct, shipped art. The joint gaps are COMPUTED and reported, never warned."""
    cars = [_car("front", 8, 54), _car("mid", 4, 27), _car("rear", 4, 27)]
    f = consistcheck.check(cars, TILE)
    check("a legitimately mixed-length unit raises NO length-fidelity warning",
          "length-fidelity" not in codes(f), str(codes(f)))
    check("its joints are reported as INFORMATION, not judged",
          "joint-plan" in codes(f)
          and all(x.level == consistcheck.INFORMATION
                  for x in f if x.code == "joint-plan"))


def test_a_car_with_no_broadside_view_is_skipped_not_crashed():
    car = consistcheck.Car("odd", 8, {"s": _cm("s", 50)})   # no sw/ne
    f = consistcheck.check([car], TILE)
    check("a car with no broadside view raises no length-fidelity and no crash",
          "length-fidelity" not in codes(f))


def test_the_band_edges_are_pinned():
    """Pin LEN_RATIO_GAP=0.55 and LEN_RATIO_OVERLAP=1.30 near their edges, so the
    calibrated band cannot drift undetected. Length 8 reserves 64 px."""
    def warns(width):
        return "length-fidelity" in codes(consistcheck.check([_car("X", 8, width)], TILE))
    check("ratio 1.25 (w80) is just inside -> silent", not warns(80))
    check("ratio 1.41 (w90) is just over -> overlap warning", warns(90))
    check("ratio 0.58 (w37) is just above the floor -> silent", not warns(37))
    check("ratio 0.48 (w31) is just below -> gap warning", warns(31))


def test_a_short_car_is_not_judged():
    """The band was calibrated on length-8 art only; a length-2 tram whose body is a
    small fraction of a tile must not be accused, so short cars are skipped."""
    f = consistcheck.check([_car("tram", 2, 6)], TILE)   # ratio 6/16=0.375 if judged
    check("a length-2 car raises no length-fidelity", "length-fidelity" not in codes(f),
          str(codes(f)))
    check("but it still appears in the consist summary", "consist" in codes(f))


def test_the_suggested_length_is_never_zero():
    f = consistcheck.check([_car("sliver", 8, 2)], TILE)   # ratio 0.03 -> gap warning
    msgs = [x.message for x in f if x.code == "length-fidelity"]
    check("a sliver body still warns", len(msgs) == 1, str(len(msgs)))
    check("and never advises the invalid length=0",
          msgs and "length=0" not in msgs[0], msgs[0] if msgs else "none")


def test_tile_px_must_be_positive():
    for bad in (0, -5):
        try:
            consistcheck.check([_car("A", 8, 54)], bad)
            check("check refuses tile_px=%d" % bad, False, "no error")
        except ValueError:
            check("check refuses tile_px=%d rather than crashing later" % bad, True)


def test_a_divergent_broadside_pair_is_not_averaged_into_the_band():
    """If sw and ne disagree wildly one is clipped; directioncheck flags that, and
    consistcheck must not average them into a passing ratio."""
    car = consistcheck.Car("clipped", 8,
                           {"sw": _cm("sw", 100), "ne": _cm("ne", 20)})
    f = consistcheck.check([car], TILE)
    check("a divergent broadside pair yields no length-fidelity (declined, not averaged)",
          "length-fidelity" not in codes(f), str(codes(f)))


def test_the_real_civia_pair_is_clean():
    """Zero false positives on shipped art: two real Civia sheets, both length 8."""
    paths = [os.path.join(_ROOT, "assets", "civia_465", "sprites", n)
             for n in ("civia465_cab_a.png", "civia465_cab_b.png")]
    if not all(os.path.exists(p) for p in paths):
        print("  note skipping real-sheet check: Civia sheets not rendered")
        return
    cars = []
    for i, p in enumerate(paths):
        w, h, _a, px = sheet.read_png(p)
        m = spritemetrics.measure(px, w, h, TILE, directions.codes_for(8), cols=4)
        cars.append(consistcheck.Car("civia_%d" % i, 8, m))
    f = consistcheck.check(cars, TILE)
    check("the real Civia pair raises no length-fidelity warning",
          "length-fidelity" not in codes(f),
          "; ".join(x.message[:80] for x in f if x.code == "length-fidelity"))


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            print("\n%s" % name)
            fn()
    print()
    if FAILED:
        print("CONSISTCHECK_TESTS_FAILED: %d" % len(FAILED))
        for f in FAILED:
            print("  - %s" % f)
        sys.exit(1)
    print("CONSISTCHECK_TESTS_OK")


if __name__ == "__main__":
    main()
