# The Quality Gate and the QA toolchain

The kit answers one question per checker, and the Quality Gate turns those into a
single yes/no for a whole addon - plus a versioned contract another tool can trust.
Everything here is pure-stdlib Python: no Blender, no Pillow, no dependency to
install, so it runs at an artist's desk, in CI, or from an agent.

## The five checks

| Module | Question it answers | Level it can raise |
|---|---|---|
| `core/scenecheck.py` | Is this Blender scene worth rendering? (floating model, wrong length, empty collection) | ERROR / WARNING / INFO |
| `core/directioncheck.py` | Are the eight rendered headings consistent? (a dropped direction, a model turned 90°, opposite views that disagree, an off-centre body) | ERROR / WARNING / INFO |
| `core/colorcheck.py` | Do the special colours work? (a window painted a hair off the glow colour that will never light; where player colour sits) | WARNING / INFO |
| `core/consistcheck.py` | Do a whole unit's cars line up? (a body drawn for a different length than declared) | WARNING / INFO |
| `core/schema.py` (dat linter) | Does the `.dat` use keys the engine actually reads? | ERROR / WARNING |

`scenecheck` runs *before* the render (it needs the Blender scene); the other four
run on the finished sheet and `.dat`, so they work on a delivered or foreign addon
with no `.blend` in sight.

Each check emits `scenecheck.Finding(level, code, message)` with a stable `code`. A
WARNING is advice; only an ERROR blocks.

## Running it

**One sheet, at the desk or from a script:**

```
python tools/analyze_sheet.py sprites/cab_a.png            # direction checks
python tools/analyze_sheet.py --colours sprites/cab_a.png  # + special colours
python tools/analyze_sheet.py --json sprites/*.png         # machine-readable
```

Exit code is non-zero if any ERROR is raised, so it drops into a Makefile.

**A whole addon (the gate):**

```
python tools/quality_gate.py path/to/addon           # PASS / FAIL + findings
python tools/quality_gate.py path/to/addon --json    # machine-readable report
```

The addon directory is the layout the package builder emits: `dat/<name>.dat`
paired with `sprites/<name>.png`. The gate:

* lints every `.dat`;
* existence-, alpha- and colour-checks **every** sheet, whatever the object type;
* direction-checks every *vehicle* sheet (and reports, rather than mis-measures, a
  sheet that is not the canonical 4-columns × 1-or-2-rows layout);
* checks the joint geometry of each fixed unit, in coupling order.

It **PASSES** exactly when nothing raised an ERROR, and the process exit code follows
(0 pass, 1 fail), so it is a CI step. Fail-closed by design: a finding whose severity
it does not recognise counts as an ERROR.

**In Blender:** the panel's *QA Check Sheet* button runs the per-direction and
special-colour checks on the sheet you just rendered, reporting each finding in the
status bar.

## The manifest: the contract for a downstream tool

```
python tools/quality_gate.py --manifest              # print the JSON contract
python tools/quality_gate.py --manifest --out manifest.json
```

The manifest is a versioned JSON document describing what the kit enforces:

* `directions` - the eight `codes`, the `cols` (4) the gate requires, the silhouette
  `families` (broadside widest, end-on narrowest), and the 4-direction `fallback`
  (a 4-cell sheet is a complete symmetric vehicle; the engine reuses `image[dir-4]`);
* `reserved_colours` - the transparency key, both player-colour ramps, and the full
  15-entry lights table (paint colour → night colour);
* `glow_targets` - the window/headlight/lamp colours a near-miss check should target;
* `length` - `carunits_per_tile` (16) and the engine's trailing rule.

It is drawn live from the same modules the checks use, so it cannot drift from what
the kit enforces, and `manifest_version` lets a consumer refuse a document it
predates. This is how an independent tool (e.g. a sprite editor in a separate repo)
validates foreign sprites by the *same* rules **without importing this kit** - one
source of truth, no shared code.

## Calibration and honest limits

Every threshold was set by measuring the kit's own shipped, in-game-correct vehicles
(Civia 465, Metro 9000) and leaving a wide margin - the same zero-false-positives bar
the linter holds. Known limits, stated rather than hidden:

* `colorcheck` near-miss targets only glow *surfaces*; a dark-blue livery near the
  blue-grey window colour could draw an advisory WARNING (never a block).
* `consistcheck` calibrated its body-vs-length band on length-8 stock, so it does not
  judge very short cars (length < 4); `scenecheck` still covers the model side.
* The gate pairs sheets to dats by filename and expects one vehicle per dat with the
  canonical layout - the kit's own output. A non-standard layout is reported, not
  silently passed.

## Tests

Pure suites, one per module, each rule tried on a case that trips it and one that
must not (`tests/test_scenecheck.py`, `test_spritemetrics.py`, `test_directioncheck.py`,
`test_colorcheck.py`, `test_consistcheck.py`, `test_qualitygate.py`). Run them all with:

```
python tools/run_tests.py core scenecheck spritemetrics directioncheck \
    colorcheck consistcheck qualitygate
```

CI runs exactly this set on every push (`.github/workflows/tests.yml`).
