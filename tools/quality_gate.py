"""One command, one verdict for a whole addon - and the contract for Sprite Studio.

    python tools/quality_gate.py <asset_dir>
    python tools/quality_gate.py <asset_dir> --json
    python tools/quality_gate.py --manifest            # print the Sprite Studio contract
    python tools/quality_gate.py --manifest --out manifest.json

<asset_dir> is a delivered/source addon holding `dat/` and `sprites/` (the layout the
kit's package builder emits): each `dat/<name>.dat` is paired with `sprites/<name>.png`.
The gate runs, and pools into ONE pass/fail:

  * the per-direction sheet check   (core.directioncheck)   - dropped/mis-facing headings
  * the special-colour check        (core.colorcheck)       - dead windows, player colour
  * the whole-unit joint check      (core.consistcheck)     - body vs declared length
  * the .dat linter                 (core.schema)           - keys the engine won't read

It PASSES when nothing raised an ERROR (a WARNING is advice, not a blocker), and the
process exit code follows, so it drops into CI or a Makefile. The scene audit
(core.scenecheck) is not here: it needs the Blender scene, which a delivered addon no
longer has - it runs at render time, inside the panel.

`--manifest` emits the versioned JSON contract (reserved colours, the 8-direction
layout, the glow colours, the carunit) that the independent Sprite Studio reads so it
can validate foreign sprites by the SAME rules, without importing this kit.
"""

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core import (colorcheck, consistcheck, directioncheck, directions,  # noqa: E402
                  paksets, qualitygate, schema, sheet, spritemetrics)
from core.qualitygate import ERROR, WARNING, Finding                # noqa: E402


def _adapt_lint(f):
    """A core.schema linter finding -> the common scenecheck.Finding shape.

    Maps explicitly and fails CLOSED: schema emits "error"/"warning" today, but any
    future or unexpected level becomes an ERROR rather than being silently downgraded
    to a non-blocking WARNING."""
    level = {"error": ERROR, "warning": WARNING}.get(f.level, ERROR)
    where = "%s:%d " % (os.path.basename(f.path or ""), f.line) if f.path else ""
    return Finding(level, f.code or "dat-lint", where + f.message)


def _codes_and_cols(w, h, tile_px):
    cells = (w // tile_px) * (h // tile_px)
    codes = directions.codes_for(8) if cells >= 8 else \
        directions.codes_for(4) if cells >= 4 else directions.DIR_CODES[:cells]
    return codes, w // tile_px


def gather(asset_dir, tile_px):
    """Run every check over an addon dir -> (groups, ok_to_score).

    groups is a list of (source, findings) ready for qualitygate.combine. ok_to_score
    is False only when there was nothing to check (no dats), so the caller can refuse
    to call an empty addon a PASS.

    IN-CONTRACT LAYOUT: this pairs each `dat/<name>.dat` with `sprites/<name>.png` -
    what the kit's package builder emits. EVERY dat's sheet is existence-, alpha- and
    colour-checked, whatever the object type; only vehicle sheets get the 8-direction
    and consist checks. A vehicle sheet that is not the canonical 4-columns x 1-or-2-
    rows layout is REPORTED and its direction check skipped, rather than silently
    passed or measured wrong.
    """
    dat_dir = os.path.join(asset_dir, "dat")
    sprite_dir = os.path.join(asset_dir, "sprites")
    if not os.path.isdir(dat_dir):
        return [("gate", (Finding(ERROR, "no-dats",
                 "no dat/ directory in %s" % asset_dir),))], False

    texts = []
    for name in sorted(os.listdir(dat_dir)):
        if name.lower().endswith(".dat"):
            with open(os.path.join(dat_dir, name), encoding="utf-8",
                      errors="replace") as fh:
                texts.append((os.path.join(dat_dir, name), fh.read()))
    if not texts:
        return [("gate", (Finding(ERROR, "no-dats", "no .dat files"),))], False

    groups = [("dat-lint", tuple(_adapt_lint(f) for f in schema.lint_files(texts)))]

    # Declared vehicles, with a guard against two dats claiming the same name (the
    # pakset loader rejects that; better to say so than to silently pair one sheet).
    vehicles = []
    seen_name = {}
    dupes = []
    veh_bases = set()
    veh_sheet = {}
    for path, text in texts:
        base = os.path.splitext(os.path.basename(path))[0]
        vs = schema.vehicles_in(text, path)
        if vs:
            veh_bases.add(base)
        for v in vs:
            if v.name in seen_name:
                dupes.append(Finding(ERROR, "duplicate-name",
                    "vehicle name %r is declared in both %s and %s"
                    % (v.name, os.path.basename(seen_name[v.name]),
                       os.path.basename(path))))
            else:
                seen_name[v.name] = path
            vehicles.append(v)
            veh_sheet[v.name] = os.path.join(sprite_dir, base + ".png")
    if dupes:
        groups.append(("names", tuple(dupes)))

    # metrics per vehicle sheet base, only for well-formed sheets, for the consist.
    metrics_by_base = {}

    # EVERY dat's sheet: exists? has alpha? colour? Vehicles also: layout + direction.
    for path, text in texts:
        base = os.path.splitext(os.path.basename(path))[0]
        spath = os.path.join(sprite_dir, base + ".png")
        src = "sprite:%s" % base
        if not os.path.exists(spath):
            groups.append((src, (Finding(ERROR, "no-sprite",
                           "dat %s.dat has no sheet at %s" % (base, spath)),)))
            continue
        try:
            w, h, has_alpha, px = sheet.read_png(spath)
        except Exception as e:      # noqa: BLE001 - a corrupt PNG is a bad-sheet, not a crash
            groups.append((src, (Finding(ERROR, "bad-sheet",
                           "%s: cannot decode: %s" % (base, e)),)))
            continue
        if not has_alpha:
            groups.append((src, (Finding(ERROR, "no-alpha",
                           "%s: no alpha channel - silhouettes cannot be measured"
                           % base),)))
            continue

        groups.append(("colour:%s" % base, colorcheck.check(px, w, h, tile_px)))

        if base not in veh_bases:
            continue                                  # a building/way/etc: colour only

        grid_cols, grid_rows = w // tile_px, h // tile_px
        if grid_cols != 4 or grid_rows not in (1, 2):
            groups.append(("direction:%s" % base, (Finding(WARNING, "unusual-layout",
                "%s is %d cols x %d rows; the standard vehicle sheet is 4 cols x 1 or "
                "2 rows, so the direction check was skipped - verify it by hand"
                % (base, grid_cols, grid_rows)),)))
            continue
        codes, cols = _codes_and_cols(w, h, tile_px)
        m = spritemetrics.measure(px, w, h, tile_px, codes, cols)
        metrics_by_base[base] = m
        groups.append(("direction:%s" % base,
                       directioncheck.check(m, tile_px, expected_codes=codes)))

    # Per fixed unit: the joint geometry, in coupling order.
    for chain in schema.chains(vehicles):
        cars = []
        for v in chain:
            spath = veh_sheet.get(v.name)
            base = os.path.splitext(os.path.basename(spath))[0] if spath else None
            m = metrics_by_base.get(base)
            if m is None:
                continue        # sheet missing / bad / non-standard - already reported
            cars.append(consistcheck.Car(v.name, v.length, m))
        if cars:
            groups.append(("consist:%s" % chain[0].name,
                           consistcheck.check(cars, tile_px)))

    return groups, True


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                 allow_abbrev=False)
    ap.add_argument("asset_dir", nargs="?", help="addon dir with dat/ and sprites/")
    ap.add_argument("--pakset", default="pak128")
    ap.add_argument("--tile", type=int, default=None)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--manifest", action="store_true",
                    help="emit the Sprite Studio contract and exit")
    ap.add_argument("--out", default=None, help="write --manifest here instead of stdout")
    args = ap.parse_args(argv)

    tile_px = args.tile if args.tile else paksets.get(args.pakset).tile_px

    if args.manifest:
        m = qualitygate.manifest(args.pakset, tile_px)
        text = json.dumps(m, indent=2)
        if args.out:
            with open(args.out, "w", encoding="utf-8") as fh:
                fh.write(text + "\n")
            print("wrote manifest %s to %s" % (m["manifest_version"], args.out))
        else:
            print(text)
        return 0

    if not args.asset_dir:
        ap.error("an asset_dir is required (or use --manifest)")

    groups, scored = gather(args.asset_dir, tile_px)
    result = qualitygate.combine(groups)
    passed = result.passed and scored

    if args.json:
        print(json.dumps({
            "asset": args.asset_dir,
            "passed": passed,
            "counts": {k: v for k, v in result.counts.items()},
            "sources": {src: [{"level": f.level, "code": f.code, "message": f.message}
                              for f in fs]
                        for src, fs in result.by_source.items()},
        }, indent=2))
        return 0 if passed else 1

    print("Quality Gate: %s   (%d error, %d warning, %d info)\n"
          % ("PASS" if passed else "FAIL", result.counts[ERROR],
             result.counts[WARNING], result.counts[qualitygate.INFORMATION]))
    for src, fs in result.by_source.items():
        shown = [f for f in fs if f.level != qualitygate.INFORMATION]
        if not shown:
            continue
        print("  %s:" % src)
        for f in shown:
            print("    %-8s %-16s %s" % (f.level, f.code, f.message[:100]))
    print("\n%s" % ("PASS" if passed else "FAIL"))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
