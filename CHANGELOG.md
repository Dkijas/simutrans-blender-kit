# Changelog

## 0.10.0

0.9 got you a family. This gets you a *train* — and puts the scene back afterwards.

### The research that shaped it

`can_follow` (`vehicle_desc.h:219`) decides all coupling, and everything falls out
of one line: **`prev_veh == NULL` means "nothing in front of me" — the head.**

| Written | `can_follow(NULL)` — at the head | `can_follow(X)` — behind X |
|---|---|---|
| *(nothing)* | true | true |
| `none` | **true** (NULL==NULL) | false |
| `any` | **false** (the `prev_veh!=NULL` guard) | **true** |

So **`any` is how you say "middle only"** — the reverse of how the word reads.
`vehicle_writer.cc:271` makes `none` a NULL child; `pakset_manager.cc:238` makes
`any` a real sentinel. Full table in
[docs/constraints-in-simutrans.md](docs/constraints-in-simutrans.md).

### Added

- **Consist Manager.** Describe the train; the coupling rules fall out. Handles
  head/tail/middle-only, optional cars, repeatable sections (which may follow
  **themselves** — forget that and "2 to 6 coaches" builds exactly one), reversible
  sets and articulated pairs.

  **The union is the point.** A vehicle in two formations must accept every
  neighbour either gives it. Miss one and the game does not complain — it just
  refuses to let the player build that train, and never says why.

  `datgen` stays the canonical source: this generates the `constraint_prev` /
  `constraint_next` tuples `vehicle_dat()` already took. It formats no `.dat` line,
  and a test reads the AST to hold that.

  **Show Constraints prints a diff and writes nothing.** A tool that silently
  rewrites the coupling of every vehicle in a project is one nobody should press.

  The summary refuses to invent: totals are `CONFIRMED`, `COMPUTED` or
  `UNAVAILABLE`, and a weight missing two cars is unavailable rather than a sum
  over the cars that happened to have figures.

- **Eight-direction contact sheet.** Phase 2 proved one heading byte-identical to
  the final render; all eight now are. It is an *extra* artefact built **from** the
  finished frames — it never touches them. The order is the engine's own
  (`s w sw se n e ne nw`), so the page is **labelled rather than reordered**.

- **A real component catalogue** — wheelset, two-axle bogie, pantograph, headlight,
  coupler. **Built, not committed as art**: `tools/build_components.py` defines each
  as primitives, so the provenance *is* the source and the licence is unambiguous.
  Real numbers (0.92 m wheels, 1.435 m gauge, UIC coupler height). No third-party
  art.

- **Schema v2**, one document holding variants and consists. The v1 → v2 migration
  is tested against a **literal** phase-2 document, not one this code produced. A
  document from the future is handed back untouched and never written over —
  guessing at a newer format is how an old kit eats a newer project.

### Fixed

- **`Render All Variants` left the last variant applied.** An artist who rendered a
  family found their scene painted in whichever livery came last, indistinguishable
  from one they had painted themselves. `SceneRestore` now restores the material
  slots, selection and active object whether the run finished, raised or was
  cancelled — and **reports its own failures** as visible warnings.
- **`addon/ui.py` said a lone `Constraint[Prev]=none` makes a vehicle "run
  alone".** It means **only at the head**. `core/datgen.py` had it right in the same
  repo, so the two contradicted each other and the wrong one was the tooltip. The
  shipped Civia settles it: `cab_a` has `none` *and* a follower, and leads five cars.
- **`core/datgen.py` described `any` as "anything at all"** — omitting that it
  forbids the head.
- The translation test demanded a translation for `""` (what `text=""` on an
  icon-only button produces). An empty label is the absence of a word.

### Not done

- **No temporary variant preview**, and that is a decision. Applying a variant
  rewrites material slots; Blender has no other way to assign a material, so there
  is no honest "temporary" preview. Rather than simulate one, the panel says which
  variant is on and offers one button to undo it.
- **Blender 4.x: NOT TESTED.** Only 5.1.2 is on this machine.
- **Linux and macOS: NOT TESTED.**

## 0.9.0

0.8 got you a first object. This is about the second, the fifth, and shipping them.

### The research that shaped it

**There are no liveries in base Simutrans.** Not "unimplemented here" — absent
from the engine. `grep -rlnw livery src/` returns nothing; the only occurrence of
the string is inside the word *delivery*. Liveries are a Simutrans **Extended**
feature. **There is no day/night variant either** — the engine does it itself
(`simview.cc` `hours2night[]`), from reserved colours in the one sprite you already
rendered. And **a vehicle has no season**: its widest image key is
`freightimage[%d][%s]`, cargo and nothing else.

So "variant" means two different things, and the tool keeps them apart:

- **Axis variants** — indexed inside one object, by the key the writer builds.
  Phase 1 already makes their collections.
- **Sibling objects** — a livery, a family member. Separate `name=`, separate
  `.dat`. The engine has no idea they are related.

Full derivation, per writer, in [docs/variants-in-simutrans.md](docs/variants-in-simutrans.md).

### Added

- **Variant Manager.** One base, N siblings, each a set of *overrides* — geometry
  is never duplicated. Asking for a livery axis, a night axis, or a season on a
  catenary is an **error that names the reason**. `AXES` is checked against
  `core/dat_schema.json`, which is extracted from the engine's writers.

  A variant's **key is not its name**: a name changes, and keying by name would
  make a rename silently abandon the variant's overrides.

- **Publication Package.** `plan()` before `write()`, so you see every file and
  what is wrong with it before a byte is written. Every file is marked
  **GENERATED or AUTHORED** — a maintainer needs to know which is output and which
  is somebody's work. **Byte-reproducible**: fixed timestamps, sorted entries. No
  licence is an **error**. Nothing is uploaded, ever.

- **Component Library.** A component is a named collection in a `.blend` plus a
  six-line sidecar. **No licence, no insert** — a library copies people's work into
  people's projects, and an unlicensed component in somebody's pakset has no answer
  to "may we ship this?". Absolute paths are refused, not normalised. We ship no
  third-party art; the example component is modelled by the tests, in code.

- **Sprite Preview** — and it *is* the final render. `render_directions` is
  `prepare_directions()` plus a loop of `render_one_step()`; the preview calls those
  same two functions for one heading. `blender_phase2.py` renders both and demands
  the PNGs be **byte-identical**. Staleness is reported conservatively: a preview
  believed current, and not, is worse than none.

### Fixed

Nothing in existing code — phase 2 adds, it does not repair. Two bugs were found
and fixed **in phase 2's own new modules**, both by their own tests:

- `variants.new_key` **reused dead keys** — delete `v00000000`, add a variant, get
  `v00000000` back, and any stale reference silently means someone else's variant.
  Its docstring claimed keys are never reused while the code reused them.
- `variants.load` **raised** on `{"variants": 3}` while promising "never raises on
  rubbish".

### Changed

- Three collapsible sub-panels — Variants, Components, Publish — closed by default.
  Phase 1's flow is untouched: a first object needs none of this.

### Not done

- **Consist Manager** — deferred. It is about `Constraint[Prev]`/`[Next]` across
  several `.dat` files, which is a different problem from variants of one, and the
  five-car Civia already works without it.
- **Batch Project Build** — `tools/run_tests.py` already renders, compiles and
  loads every object in the repo. A second batch runner would be a second thing to
  keep true.

## 0.8.0

The kit could take a finished model anywhere. It could not help you start one.

### Added

- **Create Template.** The panel now makes the scene instead of describing it.
  Every module in `core/` *reads* a finished scene — `render_way` looks for
  `way_curve`, `has_tunnel_model` looks for `tunnel_portal`,
  `collection_variant_setup` looks for `season_1` — and nothing anywhere *wrote*
  them. The artist typed those names by hand from three lines of prose in the
  panel, and a typo was not an error: it was a piece that silently never rendered.
  `core/templates.py` is the inverse of the readers.

  The names are **derived, never re-typed**. `way_curve` is not spelled out in the
  new module; it is the prefix plus a name from `ways.PIECE_NAMES`, the same tuple
  `render_way` iterates. The bridge collections come from
  `bridges.GROUP_COLLECTION`, the dict the bridge renderer looks them up in. A
  template that agrees with the renderer today and drifts tomorrow would be worse
  than no template — it would name a collection nothing reads, with a tool's
  authority behind it.

- **Guides**: a tile at ground level, the `+X` nose arrow, the declared length
  drawn as a box, a building's footprint and its `−Y` façade. They are Blender
  **empties**, which is load-bearing rather than incidental — see *Fixed* below.

- **Place Reference.** A photo where the model goes, scaled from the real metres
  you type. Metres → tiles → Blender units is where an artist who has not read the
  pakset docs goes wrong, and it does not announce itself: a bus modelled 20% large
  is just a slightly wrong bus. Nothing is downloaded. It reuses Blender's own
  reference-image mechanism, so there is no second render path.

- **Validate.** Everything the kit already refused, it refused *during or after*
  the render: `warn_if_clipped` reads the finished PNGs, `schema.lint` reads the
  finished `.dat`, Check Colours needs a sheet on disk. And the two mistakes that
  cost most survive the render perfectly — a model facing the wrong way, or built
  three units above the ground, yields a clean sheet, a `.dat` that lints, and a
  vehicle that flies. `core/scenecheck.py` is pure, so every rule is tested from a
  literal without Blender in the loop.

  `ERROR` blocks, `WARNING` does not, and the bar for `ERROR` is deliberately high:
  an artist whose correct scene is refused turns the check off, and then it protects
  nobody. A wheel rim 5 mm below `z=0` is ordinary art and is not reported.

  The rule worth the module on its own is `length-mismatch`. `length` does not
  scale the sprite — it is what the engine trails the *next* car by
  (`simconvoi.cc:428`). Declare 8, model 16, and every sprite draws full size and
  overlaps its neighbour by half a tile. Nowhere in Blender is that visible; it
  appears in a depot.

### Fixed

- **`has_slope_model` and `has_wayobj_slope_model` asked only whether the
  collection EXISTED**, while their five siblings — `has_tunnel_model`,
  `has_bridge_model`, `has_front_parts`, `_has_collection` — all require
  `and col.objects`. Indistinguishable from the truth while the only way to have a
  `way_slope` was to make one by hand and fill it. The template lists `way_slope`
  for every way, so the **empty collection becomes the common case**, and answering
  yes to it would send `render_way_slopes` off to photograph nothing: blank slope
  images in the `.dat`, and the way invisible on every hill. Silently — which is
  the exact failure the slope image exists to prevent, arrived at from the other
  side. Found by a test written for the template, not by reading the code.

### Changed

- The panel's first box is **Start**, not Rig. Its first button used to be *Build
  Rig* — a camera and a sun, which is the *second* thing an artist needs. There was
  no first thing.
- The five collection prefixes live in `core/templates.py`; `addon/rig.py` imports
  them. One spelling, not two that happen to match. `season_`, `phase_` and
  `state_` had no home at all — they were string literals in `addon/ui.py`, bound
  to the renderer only by a docstring and a line of prose in the panel.

### Not done

- **A component library** (wheels, bogies, pantographs) and a **variant manager**
  were considered and deferred. Neither is blocked by anything; both are worth more
  once an artist can reliably produce a *first* object, which is what this release
  is about.
- The vehicle template makes **no collections**, on purpose. `render_directions`
  photographs whatever is in the scene, so a `Body` / `Bogie_Front` tree would be
  convention dressed as mechanism — and a `Lights_Night` collection would be an
  outright lie, because night lights come from *materials*, which the Materials box
  already does.

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
