# Changelog

## 0.7.0

Pakset profiles measured against the real pakset, not transcribed and hoped.

### Changed

- **The pakset profile is now checked against the pakset's own `simuconf.tab`.**
  `core/paksets.py` carries numbers that belong to the pakset - `tile_height`, and
  now `height_conversion_factor` - and its own docstring warned about "the sort of
  wrong number that waits" until something reads the field (pak128's `tile_height`
  was 16-for-everyone once, twice too steep). The existing test proved those
  numbers were self-consistent; consistency is not correctness. A new `profile`
  test suite reads the real `config/simuconf.tab` of every mounted pakset (the demo
  pak in the engine source, the pak128 testbed under `build/game`) with the
  engine's own parsing - `#` a comment only at column 0, values read strtol-style -
  and asserts the profile equals it. It SKIPS when no pakset is mounted, so CI
  stays green while a local run verifies against the artefact. `tools/measure_pakset.py`
  is the instrument.

### Added

- **`height_conversion_factor` in the profile, measured (pak128 = 2, demo pak = 1).**
  With factor 2 the engine turns a terrain step into a DOUBLE-height slope
  (`slope_from_slope4`, grund.cc / tunnelboden.cc / brueckenboden.cc), so pak128's
  ordinary hill is double. That makes the double-slope way/wayobj image (`imageup2`,
  the `way_slope2` model) the common case for pak128, not the optional decoration
  it is for a factor-1 pakset. The profile exposes `double_slope_default` and the
  double ramp's rise (`double_slope_rise_px` / `_world`, exactly two single levels)
  for the artist.

- **The panel warns when a pak128 way has no `way_slope2` model.** The measured
  fact above, put in front of the artist: render a way for a double-slope pakset
  with a single ramp but no double one, and the panel now says the single-height
  image will be stretched over every ordinary hill, and to model `way_slope2`. It
  stays silent for a single-height pakset (the demo pak), where the double slope is
  genuinely rare, and once the double ramp is modelled. The decision is pure and
  tested without Blender (`ways.double_slope_advisory`); a panel test proves the
  warning reaches the artist's screen, not just the console.

## 0.6.0

The release that finished the object types: everything a pakset is built from can
now come out of the kit.

### Added — four new object types

- **Tunnels.** A portal in four directions and two layers (back behind the
  vehicle, front over it), modelled on a north-facing ramp in `tunnel_portal` /
  `tunnel_portal_front`. Grounded in `tunnel_writer.cc` and the engine's
  `slope_indices`; the mandatory icon is emitted (without it the engine gives the
  tunnel no builder). Verified buildable in the running game.

- **Stations and depots.** A stop, a depot or an extension is a building with a
  `type`, a `waytype` and — because a player places it — an icon, without which
  `hausbauer.cc` gives it no builder and it silently cannot be built. Pick the kind
  and set what it accepts (passengers, mail, goods). Verified: the stop turns up in
  the engine's own station builder list.

- **Bridges.** The four image groups the engine reads — span (ns/ew), start and
  ramp (n/s/e/w), pillar (s/w) — each in a back and an optional front layer, plus
  the length, height and pillar-spacing limits. Modelled in `bridge_span`,
  `bridge_start`, `bridge_ramp`, `bridge_pillar`. Verified buildable in game.

- **Factories.** A building plus its economics in one `obj=factory`: the mandatory
  minimap colour, productivity, location, and the goods it makes or consumes (each
  a cross-reference that must resolve at load). The sprites are the ordinary
  building render. Verified: the factory loads with its good resolved and appears
  in the engine's factory table.

Every one is grounded in the engine's own writers, checked against makeobj (which
fatals on a missing `freightimagetype`, `mapcolor` or icon), rendered and pixel-
checked in Blender, and loaded in the running engine. One caveat held honestly: the
exact portal/piece-on-which-hill mapping for tunnels and bridges is derived from
the engine's slope tables but is the reflection the way slopes proved you confirm
by eye in a windowed game, not headless — the pieces are verified buildable; their
per-slope orientation is the one thing a headless run cannot see.

### Note

Cargo variants (freight images) shipped in 0.5.0.

## 0.5.0

### Added

- **Cargo variants (freight images).** A wagon can now show a different sprite for
  each good it carries — empty, loaded with coal, loaded with oil. Put each load in
  a collection `freight_0`, `freight_1`, … (the same additive convention as
  seasons), list the goods in the new **Cargo variants** field (`Kohle, Oel`), and
  the render produces the empty sheet plus one loaded sheet per good and writes the
  `emptyimage` / `freightimage[i]` / `freightimagetype[i]` `.dat` the engine needs.

  Grounded in the engine source throughout: the engine requires exactly one
  `freightimagetype` per freight image and makeobj FATALs without it; it shows the
  empty image when the wagon is unloaded and the matching freight image when it is
  not, falling back to index 0. There are no "livery" images in base Simutrans —
  that is a Simutrans Extended feature — so this is freight, precisely.

  Verified end to end: the emitted `.dat` compiles under makeobj (and fails without
  the `freightimagetype` lines); the empty and loaded sprites differ pixel for pixel
  in every heading; and the wagon loads in the running engine, is buyable, and its
  freight goods really resolve — which only the game can prove, because makeobj
  defers the goods to load time.

## 0.4.0

### Added

- **Render Sheet shows progress and can be cancelled.** A vehicle render fires the
  renderer eight times with the UI frozen and no way out. It now renders one heading
  per tick with a progress bar and a status-bar readout (`heading N/8`), and **Esc**
  stops it. Because the render call is itself blocking, the gain is an
  update-and-cancel point between headings — which is where the seconds actually go.
  A cancelled render is left on disk but not recorded, so *Write .dat* still builds
  only from the last complete render, never half a sheet.

### Changed

- **CI runs the core suite on every push** (GitHub Actions, Python 3.10–3.12): the
  ~970 Blender-free checks — projection, colours, the `.dat` linter, schema drift.
- `doc_url` and the README now point at the GitHub repository and its releases.

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
- **Write .dat without re-rendering.** Change a number — power, cost, a coupling —
  and rewrite the `.dat` from the last render's frames instead of rendering every
  heading again.
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
