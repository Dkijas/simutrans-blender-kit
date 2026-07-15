# Changelog

## 0.3.0

The release that made the kit's own claims true and closed the gaps that let
broken art ship green.

### Fixed — things that produced wrong artefacts

- **Signals never lit.** The purple signal lamp was written as `#E100E1`, the
  colour the game *draws*, not `#FF017F`, the colour makeobj *matches*. A signal
  painted the way the kit recommended compiled its lamp as a flat colour that
  could never light. The reserved-colour table is now read from the engine source,
  not transcribed, and every one of the 31 colours is checked byte-for-byte inside
  a real `.pak`.
- **Ways and catenary were invisible on slopes.** Neither emitted slope images, and
  the engine has no fallback for them (`weg.cc:545`, `wayobj.cc:270` are unguarded),
  so anything the kit made vanished on every hill. The artist now models one more
  shape (`way_slope` / `wayobj_slope`) and the four slope images are emitted — all
  four or none, because the engine indexes them by position and a partial set draws
  the wrong image.
- **The pakset height step was wrong.** It was hard-coded to 16 for every pakset;
  pak128's own `simuconf.tab` says 8. It had never bitten because the field was
  read by nobody — until the slopes needed it. Now taken per pakset.
- **Sprites carried the author's home directory.** Blender writes the `.blend`'s
  absolute path into every PNG's metadata; every published sprite leaked it. Turned
  off, and pinned by a byte-scan test.
- **The render engine and colour management were unpinned.** The same `.blend` gave
  different sprites under EEVEE and Cycles, and the tone-mapping-off setting was
  wrapped in a silent `try/except`. Both are now set and verified; the kit refuses
  to render rather than produce silently wrong colour.

### Added

- **Material buttons.** Player colour, the night lights and plain paint now have a
  panel button. They were reachable only from a script before — the one thing an
  artist most needs, and the hardest to get to.
- **Render warnings reach the panel.** Clipping and accidental-reserved-colour
  warnings used to print to a console no artist has open while the panel said
  "Rendered". They are reported in the panel now.
- **Linter: value validation, rule codes, `--json`, and an ignore pragma.** It
  checks that a number key is given a number, tags each finding with a stable code,
  can emit JSON, and honours `# bkit: ignore=<code>`. Two silent bugs fixed: it
  crashed on a malformed range, and its missing-icon rule was masked for a second
  object of the same type in one file.

### Changed

- **The test loop is closed.** Nothing used to compile the `.pak` the game suites
  loaded; they ran against art that could be days old. The runner now renders,
  compiles and installs from this run's sources, and the game scenarios assert what
  they report (car count, order, that the unit is really electric, that it moved)
  instead of printing it.
- **Licence is MIT** (see `LICENSING.md`), replacing an Artistic 1.0 claim that was
  GPL-incompatible for a `bpy` add-on.
- **The project is a git repository**, and the test scenarios live in source rather
  than only inside `build/`.
- **The example trains credit their modeller** (`victor_18993`), not the tool.
- The toolchain (makeobj, Blender, the headless engine) is discovered rather than
  assumed to sit at Windows paths, so the suite runs on Linux and macOS too.

## 0.2.0

Kept `spec.py` out of the published add-on; internal cleanup.
