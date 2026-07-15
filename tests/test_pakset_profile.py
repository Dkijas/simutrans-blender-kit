"""Do our pakset profiles match the REAL paksets they claim to describe?

    python tests/test_pakset_profile.py

core/paksets.py carries numbers that belong to the pakset, not to us: tile_height
and height_conversion_factor, both read out of the pakset's config/simuconf.tab.
test_core.py proves those numbers are internally consistent (a level rises the
right pixels, a double slope is two levels) - but consistency is not correctness.
It cannot catch a transcription that is self-consistent and simply wrong, nor a
pakset that changed the value in a new release. Its own module docstring names the
failure: "the sort of wrong number that waits" until something reads the field.

So read the field. This suite parses the real simuconf.tab of every pakset we can
find mounted and asserts our profile equals it. It needs the artefacts - the demo
pak in the engine source, and the pak128 testbed under build/game - so when
neither is present it SKIPS rather than fails: CI has no pakset, a local run does.

Prints PROFILE_OK, or PROFILE_SKIP when nothing is mounted to measure against.
"""

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from core import paksets                       # noqa: E402
from tools import measure_pakset               # noqa: E402

# Where the real paksets are mounted. The demo pak ships in the engine source; the
# pak128 testbed is a real pakset under build/game (see the testbed memory / the
# civia README). Either, both, or neither may be present.
_SRC = os.environ.get("SIMUTRANS_SRC", os.path.join(os.path.dirname(_ROOT), "simutrans"))

# (our profile, pakset root on disk). The demo pak's folder is literally "pak".
_TARGETS = (
    (paksets.PAK64, os.path.join(_SRC, "simutrans", "pak")),
    (paksets.PAK128, os.path.join(_ROOT, "build", "game", "pak128")),
)

FAILED = []


def check(name, cond, detail=""):
    if cond:
        print("  ok   %s" % name)
    else:
        print("  FAIL %s  %s" % (name, detail))
        FAILED.append(name)


def main():
    measured_any = False

    for profile, pakset_dir in _TARGETS:
        try:
            real = measure_pakset.measure(pakset_dir)
        except FileNotFoundError:
            print("  --   %s not mounted (%s) - skipping" % (profile.name, pakset_dir))
            continue
        except ValueError as exc:
            check("%s config is readable" % profile.name, False, str(exc))
            continue

        measured_any = True

        check("%s tile_height: profile %d == config %d"
              % (profile.name, profile.height_step, real["tile_height"]),
              profile.height_step == real["tile_height"],
              "our profile says %d, %s/config/simuconf.tab says %d - the transcribed"
              " number drifted from the real pakset"
              % (profile.height_step, profile.name, real["tile_height"]))

        check("%s height_conversion_factor: profile %d == config %d"
              % (profile.name, profile.height_conversion_factor,
                 real["height_conversion_factor"]),
              profile.height_conversion_factor == real["height_conversion_factor"],
              "our profile says %d, the real pakset says %d"
              % (profile.height_conversion_factor, real["height_conversion_factor"]))

        # The claim that matters to the artist: is the double slope the common
        # case? It is exactly the factor being 2, read from the real file.
        check("%s double_slope_default agrees with the real factor" % profile.name,
              profile.double_slope_default == (real["height_conversion_factor"] == 2))

    if not measured_any:
        print("PROFILE_SKIP: no real pakset mounted (looked for the demo pak under"
              " SIMUTRANS_SRC and pak128 under build/game)")
        return 2

    if FAILED:
        print("\nPROFILE_FAILED: %s" % ", ".join(FAILED))
        return 1
    print("\nPROFILE_OK: every mounted pakset's profile matches its own"
          " config/simuconf.tab")
    return 0


if __name__ == "__main__":
    sys.exit(main())
