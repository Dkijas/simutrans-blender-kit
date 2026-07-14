"""Has the engine moved without us?

    python tests/test_schema_drift.py [path-to-simutrans]

core/dat_schema.json is generated from the engine's descriptor writers. If prissi
adds a key, renames one, or adds an object type, our shipped copy is stale and
the linter starts lying - it will call a brand-new, perfectly valid key "unknown",
which is worse than having no linter at all.

So: re-extract from the source and compare. This is the whole reason the schema
is generated instead of hand-written.

Needs the Simutrans source. Prints SCHEMA_OK on success.
"""

import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from core import colors                     # noqa: E402
from tools import extract_colors            # noqa: E402
from tools import extract_dat_schema        # noqa: E402

SRC = (sys.argv[1] if len(sys.argv) > 1
       else os.environ.get("SIMUTRANS_SRC",
                           os.path.join(os.path.dirname(_ROOT), "simutrans")))
SHIPPED = os.path.join(_ROOT, "core", "dat_schema.json")


def colour_drift():
    """Do our reserved colours still match the engine's, entry for entry?

    core/colors.py was written by transcribing a table by hand, and it took the
    wrong one: display_day_lights[] (what the game DRAWS) instead of rgbtab[]
    (what makeobj MATCHES). They agree on every entry but the purple signal light,
    so nothing looked wrong, and every signal the kit produced compiled its purple
    lamp as a flat colour that could never light up.

    The answer to a table transcribed wrongly is not to transcribe it again more
    carefully. It is to read it.
    """
    out = []
    players, lights = extract_colors.extract(SRC)

    if list(colors.PLAYER_COLORS) != players:
        for i, (mine, theirs) in enumerate(zip(colors.PLAYER_COLORS, players)):
            if mine != theirs:
                out.append("player colour %d: we say #%02X%02X%02X, image.cc rgbtab"
                           " says #%02X%02X%02X" % ((i,) + mine + theirs))

    if len(colors.LIGHTS) != len(lights):
        out.append("we list %d lights, the engine has %d"
                   % (len(colors.LIGHTS), len(lights)))
    else:
        for i, ((paint, night, what), (t_paint, t_night)) in enumerate(
                zip(colors.LIGHTS, lights)):
            if paint != t_paint:
                out.append("light %d (%s): we tell the artist to paint #%02X%02X%02X,"
                           " but makeobj only recognises #%02X%02X%02X (image.cc"
                           " rgbtab) - a pixel painted our colour will NOT light up"
                           % ((i, what) + paint + t_paint))
            if night != t_night:
                out.append("light %d (%s): we say it turns #%02X%02X%02X after dark,"
                           " the engine draws #%02X%02X%02X (simgraph16.cc"
                           " display_night_lights)" % ((i, what) + night + t_night))
    return out


def main():
    if not os.path.isdir(os.path.join(SRC, "src", "simutrans", "descriptor", "writer")):
        print("SCHEMA_SKIP: no Simutrans source at %s (set SIMUTRANS_SRC)" % SRC)
        return 2

    fresh = extract_dat_schema.extract(SRC)
    with open(SHIPPED, encoding="utf-8") as f:
        shipped = json.load(f)

    problems = []

    if fresh["engine_version"] != shipped["engine_version"]:
        problems.append("engine version: shipped %s, source %s"
                        % (shipped["engine_version"], fresh["engine_version"]))

    a, b = set(shipped["obj_types"]), set(fresh["obj_types"])
    for t in sorted(b - a):
        problems.append("NEW object type in the engine: obj=%s" % t)
    for t in sorted(a - b):
        problems.append("object type GONE from the engine: obj=%s" % t)

    for t in sorted(a & b):
        ka = set(shipped["obj_types"][t]["keys"])
        kb = set(fresh["obj_types"][t]["keys"])
        for k in sorted(kb - ka):
            problems.append("obj=%s: NEW key %r (the linter would call it unknown)"
                            % (t, k))
        for k in sorted(ka - kb):
            problems.append("obj=%s: key %r no longer read by the engine" % (t, k))

        pa = set(shipped["obj_types"][t]["patterns"])
        pb = set(fresh["obj_types"][t]["patterns"])
        for p in sorted(pb ^ pa):
            problems.append("obj=%s: image key pattern changed: %r" % (t, p))

    ca, cb = set(shipped["common_keys"]), set(fresh["common_keys"])
    for k in sorted(cb ^ ca):
        problems.append("common key changed: %r" % k)

    problems += colour_drift()

    n = sum(len(t["keys"]) for t in fresh["obj_types"].values())
    print("engine %s: %d object types, %d keys"
          % (fresh["engine_version"], len(fresh["obj_types"]), n))

    if problems:
        print("\nThe shipped schema is STALE. Regenerate it:")
        print("    python tools/extract_dat_schema.py %s > core/dat_schema.json\n" % SRC)
        for p in problems:
            print("  - %s" % p)
        print("\nSCHEMA_FAILED")
        return 1

    print("\nSCHEMA_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
