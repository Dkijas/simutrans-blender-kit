"""Read a real pakset's config and report the profile numbers we depend on.

core/paksets.py carries a handful of numbers - tile_height, height_conversion_
factor - that are NOT ours to invent: they belong to the pakset and live in its
config/simuconf.tab. This module reads them straight off the real file so a test
can pin our transcription to the source of truth (see the profile test in
tests/test_core.py). The module docstring in core/paksets.py warns about exactly
the failure this guards: "the sort of wrong number that waits" until something
reads the field.

Only the keys the profile actually uses are parsed. The values are read with the
engine's own clamping (settings.cc), so what we report is what the engine would
load, not the raw text.

Run it against a mounted pakset:

    python tools/measure_pakset.py build/game/pak128
"""

import os
import sys


# settings.cc:1342 - get_int_clamped("height_conversion_factor", default, 1, 2)
_HEIGHT_CONVERSION_BOUNDS = (1, 2)
_ENGINE_DEFAULT_FACTOR = 1     # environment.cc:43


def _clamp(value, lo, hi):
    return max(lo, min(hi, value))


def _leading_int(text):
    """The integer at the front of `text`, the way the engine's strtol reads it.

    tabfile.cc reads a value with strtol, which consumes an optional sign and the
    leading digits and stops at the first non-digit - so `8`, `8 # note` and `8x`
    all read as 8. A '#' is only a comment at column 0 (tabfile.cc:523), never
    mid-value, so we must NOT treat a trailing '#...' as special: strtol already
    stops at the space before it. Mirroring strtol keeps what we measure equal to
    what the engine loads.
    """
    text = text.strip()
    i = 0
    if i < len(text) and text[i] in "+-":
        i += 1
    start = i
    while i < len(text) and text[i].isdigit():
        i += 1
    if i == start:
        raise ValueError("no integer at the front of %r" % text)
    return int(text[:i])


def parse_simuconf(path):
    """Parse a simuconf.tab into {key: raw string value}, engine-style.

    The .tab grammar is deliberately tiny: `key = value`, one per line, '#' opens
    a comment (only at column 0, like every Simutrans tab - see core/datgen.py on
    why a '#' mid-line is NOT a comment). Later assignments win, which is how the
    engine's own layered config works.
    """
    values = {}
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if not line or line[0] == "#":
                continue
            if "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            if not key:
                continue
            # A trailing comment is not stripped: '#' mid-line is a literal here,
            # so we take the whole right-hand side and only trim whitespace.
            values[key] = val.strip()
    return values


def measure(pakset_dir):
    """-> {'tile_height': int, 'height_conversion_factor': int} from the real config.

    `pakset_dir` is a pakset root (the folder holding config/simuconf.tab).
    Raises FileNotFoundError if the config is not there - the caller decides
    whether that is a skip (testbed absent) or a failure.
    """
    conf = os.path.join(pakset_dir, "config", "simuconf.tab")
    if not os.path.isfile(conf):
        raise FileNotFoundError(conf)

    raw = parse_simuconf(conf)

    if "tile_height" not in raw:
        # The engine has no universal default for this - a pakset that omits it is
        # relying on the built-in, but every real pakset states it. Say so rather
        # than guess.
        raise ValueError("%s states no tile_height" % conf)
    tile_height = _leading_int(raw["tile_height"])

    if "height_conversion_factor" in raw:
        factor = _leading_int(raw["height_conversion_factor"])
    else:
        factor = _ENGINE_DEFAULT_FACTOR
    factor = _clamp(factor, *_HEIGHT_CONVERSION_BOUNDS)

    return {"tile_height": tile_height, "height_conversion_factor": factor}


def main(argv):
    if len(argv) != 2:
        sys.stderr.write("usage: measure_pakset.py <pakset_dir>\n")
        return 2
    try:
        m = measure(argv[1])
    except (FileNotFoundError, ValueError) as exc:
        sys.stderr.write("cannot measure %s: %s\n" % (argv[1], exc))
        return 1
    for key in ("tile_height", "height_conversion_factor"):
        sys.stdout.write("%s = %d\n" % (key, m[key]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
