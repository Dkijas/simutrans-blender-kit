"""Check a .dat against what the engine actually reads.

    python tools/lint_dat.py myvehicle.dat
    python tools/lint_dat.py pak128/vehicles/           (recurses)
    python tools/lint_dat.py --json vehicles/           (machine-readable)
    python tools/lint_dat.py --couplings vehicles/      (see below)

Each finding carries a stable CODE (no-icon, dup-key, bad-int, ...). A line
`# bkit: ignore=no-icon, dup-key` anywhere in a .dat silences those codes for that
file - the escape valve for a finding you have read and accept.

No Blender, no dependencies - useful to anyone who writes .dat files by hand,
which is still most of the pakset world.

The key list is not hand-maintained: it is extracted from the engine's own
descriptor writers (see tools/extract_dat_schema.py), so it cannot quietly fall
behind the game.

Exit code 1 if anything is an error.

--couplings is a REPORT, not a check
------------------------------------
It follows every fixed unit (each vehicle whose Constraint[Next] names exactly one
successor - the chain a depot builds from a single click) and, where the cars do
not share a length, prints how far off-centre each car's art has to be drawn for
the joints to close. See core/convoy.py for the arithmetic and for the measurement
that says pak128's own artists do exactly this.

It is deliberately NOT part of the lint pass. A .dat does not say where the ink
sits inside the cell, so unequal lengths are not a defect - and treating them as
one accuses 56 pieces of perfectly good pak128 art.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import convoy, schema        # noqa: E402


def dat_files(paths):
    for p in paths:
        if os.path.isdir(p):
            for dirpath, _dirs, files in os.walk(p):
                for f in sorted(files):
                    if f.lower().endswith(".dat"):
                        yield os.path.join(dirpath, f)
        else:
            yield p


def couplings(texts, tile_px=128):
    """Print the art offset every fixed unit needs. -> how many units needed one."""
    vehicles = []
    for path, text in texts:
        vehicles.extend(schema.vehicles_in(text, path))

    mixed = 0
    for chain in schema.chains(vehicles):
        lengths = [v.length for v in chain]
        if len(set(lengths)) == 1:
            continue                      # equal lengths: nothing to do, ever
        mixed += 1
        print("\n%s: %d cars, lengths %s"
              % (chain[0].name, len(chain), "-".join(str(n) for n in lengths)))
        for line in convoy.describe([v.name for v in chain], lengths, tile_px):
            print("    " + line)

    print("\n%d fixed unit(s) mix lengths, and every one of them needs its art drawn\n"
          "off-centre by the amounts above. That is not a fault: it is how the engine\n"
          "lays a convoy out (core/convoy.py), and pak128's artists already do it."
          % mixed)
    return mixed


def main(argv):
    want_couplings = "--couplings" in argv
    want_json = "--json" in argv
    argv = [a for a in argv if a not in ("--couplings", "--json")]
    if not argv:
        print(__doc__)
        return 2

    unreadable = 0

    texts = []
    for path in dat_files(argv):
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                texts.append((path, f.read()))
        except OSError as e:
            print("%s: cannot read: %s" % (path, e))
            unreadable += 1

    if want_couplings:
        couplings(texts)
        return 0

    findings = sorted(schema.lint_files(texts), key=lambda f: (f.path or "", f.line))
    errors = sum(1 for f in findings if f.level == "error") + unreadable
    warnings = len(findings) - sum(1 for f in findings if f.level == "error")

    if want_json:
        json.dump([f.as_dict() for f in findings], sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 1 if errors else 0

    for f in findings:
        code = " [%s]" % f.code if f.code else ""
        print("%s:%d: %s%s: %s" % (f.path, f.line, f.level, code, f.message))

    print("\n%d file(s), %d error(s), %d warning(s)   [engine %s, %d keys]"
          % (len(texts), errors, warnings, schema.ENGINE_VERSION,
             sum(len(t["keys"]) for t in schema.OBJ_TYPES.values())))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
