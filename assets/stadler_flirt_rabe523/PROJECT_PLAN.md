# PROJECT_PLAN — Stadler FLIRT RABe 523 (SBB) for pak128

Four-car electric multiple unit for pak128, built **through the Simutrans Blender
Kit** (no bespoke pipeline). Base for this plan: kit `769fc0b`, Blender 5.1,
`simutrans/build/src/makeobj/makeobj.exe`, headless + windowed Simutrans present.

## 0. Existing-FLIRT check (mandated before starting)

Searched the installed pak128 (`dev/pak128`, compiled-only, 0 `.dat` sources) and the
kit's own `assets/` for `FLIRT`, `Stadler`, `RABe 521/522/523/524` — **none found**
by filename or content. No duplication. This is a **new** object, not a variant of an
existing one. (pak128 ships compiled `.pak` only, so cost/capacity comparison will be
done with `tools/measure_pakset.py` and in a running game, not by reading a sibling
`.dat`.)

## 1. Blender Kit files & operators used (the rule: use the kit)

Modelled on the kit's own `assets/civia_465/` (a 2004 low-floor EMU — the closest
existing template). Operators and functions, all already in the kit:

| Need | Kit entry point |
|---|---|
| Rig + camera + sun + pak128 profile | `bpy.ops.simutrans.build_rig()` → `addon/rig.py:build_rig` |
| 8 directions + sheet + `.dat` + lint | `bpy.ops.simutrans.render_sheet()` |
| Makeobj compile + install `.pak` | `bpy.ops.simutrans.compile_pak()` |
| Paint / livery / special-colour materials | `addon/rig.py:make_paint_material`, `make_livery_material`, `make_special_color_material`, `new_texture`, `paint_rect`, `commit_texture`, `textured_quad` |
| Engine light table (windows, lamps) | `core/colors.py` `WINDOW_DARK` / `HEADLIGHT` / `LAMP_RED`; `rig.declare_special` |
| Reserved-colour validator | `addon/rig.py:reserved_colour_report` (run before compile) |
| Flat contour (readability) | `core/sheet.py:add_outline_file` |
| Coupling / auto-consist | `.dat` `Constraint[Prev]/[Next]` single-successor chain (as in `civia_465/blender/build.py:couplings`) — depot auto-assembles from one click (`tool/simtool.cc` case 'a') |
| Pakset profile (tile px/world) | `core/paksets.py` `get("pak128")` |
| Cost/capacity balancing reference | `tools/measure_pakset.py` + running game |

**No FLIRT-specific code goes into `core/` or `addon/`.** All FLIRT logic lives under
`assets/stadler_flirt_rabe523/`. If a real gap appears in the common code, it will be
fixed generically (with its callers/tests checked) and reported separately.

## 2. Project structure

```
assets/stadler_flirt_rabe523/
  PROJECT_PLAN.md          this file
  BUILDING.md              how to regenerate from a clean checkout
  TESTING.md               exact versions + tests run + results
  spec.json                the numbers (typed: measured/derived/engine/provisional)
  blender/
    flirt.py               geometry + SBB livery + materials (the artist's part)
    build.py               drives the kit operators end-to-end (adapted from civia)
  renders/ sprites/ dat/ pak/ textures/ blender/  (generated)
  release/
    stadler-flirt-rabe523-pak128/   final package (.pak, .dat, sheets, .blend, docs)
    screenshots/                    real in-game captures
    FORUM_POST.txt / FORUM_POST_ES.txt
```

## 3. Cars & composition

Fixed four-car unit, assembled from **one depot click** on the cab car via a
single-successor Constraint chain:

| # | key | role | cab | panto | reversed |
|---|---|---|---|---|---|
| 1 | `cab_a`   | driving car A | yes | no | no |
| 2 | `int_b`   | intermediate B | no | no | no |
| 3 | `int_c`   | intermediate C (pantograph) | no | **yes** | no |
| 4 | `cab_d`   | driving car D | yes | no | **yes** (tail cab faces back) |

Internal names: `SBB_FLIRT_RABe523_A/B/C/D`. Visible consist name:
`Stadler FLIRT RABe 523 (SBB)`.

**Constraint chain** (`cab_a → int_b → int_c → cab_d`, each with exactly one
successor) prevents: an intermediate at the head, wrong order, closing without the
final cab, and foreign vehicles inside the unit. Reverse coupling of two full units
(`cab_d → cab_a`) is deferred to a test; only enabled if it assembles cleanly.

## 4. Dimensions

Cross-section is **absolute and identical on every car** (a FLIRT is one tube cut
into pieces — the civia lesson: deriving width/height from each car's length makes a
train thinner in the middle). Length in the `.dat` is **8 (1/16 tile) for every car**,
matching every rail vehicle pak128 ships — mixing lengths opens the joints
(`simconvoi.cc` trails each car by the length of the one in front while art sits
centred). Total sprite length = 4 × 8 = 32/16 = 2 tiles ≈ the real ~74 m at pak128's
~25 m/tile approximation.

- reference length total: **74.1 m** (4-car RABe 523)
- width: **2.88 m**, height: **4.15 m** (both used for the absolute cross-section,
  "fattened" for 128 px legibility and checked against the catenary in-game, as civia)
- bogies: standard placement (works drawing not dimensioned) — end motor bogies +
  shared/inner bogies as configuration allows.

## 5. Game data (initial, per brief §8 — typed in spec.json)

- `waytype=track`, `engine_type=electric`, `speed=160`
- power total **2000 kW**, split across the powered ends (cab cars carry the traction)
- weight total **~120 t**, capacity total **~180 pax** (in the 160–220 band)
- `intro_year=2004`, no retire date
- `cost` / `runningcost`: **provisional**, balanced against pak128's own 2004–2010
  EMUs before release (method noted above) — never invented silently.
- Engine colours (exact, unlit): window `WINDOW_DARK`, headlight `HEADLIGHT`, tail
  `LAMP_RED`, player colour on the skirt.

## 6. SBB livery (RABe 523)

White body; dark-grey lower band; **red doors**; red front around a large dark
windscreen; grey roof; discreet `SBB CFF FFS`. Painted in code with `paint_rect`
(no photographic textures). Reserved colours only where intended (windows, head/tail
lamps, player) and declared with `declare_special`; validator run before compile.

## 7. References consulted

- SBB official FLIRT page (EN/DE): service since 2004, 75–105 m, 160 km/h.
- vlaky.net FLIRT SBB four-car technical elevation — proportions, car length, bogie/
  door/window positions, roof equipment, articulation.
- spotlog / startbilder / bahnbilder photos — visual reference only (no textures).

## 8. Technical risks

1. **Art quality is not machine-verifiable.** A procedural 128 px mesh is a silhouette
   approximation; I can run the pipeline and validate colours/geometry mechanically,
   but "does it read as a FLIRT" needs a human eye — I will surface each render.
2. **Reversed tail cab** must be a turned-around separate object (engine draws every
   car with the convoy-direction image) — handled as civia's `turn_around()`.
3. **Real in-game screenshots** require the windowed build + pak128; night lights and
   directional lamps depend on the engine's day→night swap (a vehicle has no night
   image — cab shows both head and tail lamps by design).
4. **Cost balance** is provisional until compared to pak128 stock.
5. **makeobj not built by default** upstream now, but a built binary exists at
   `simutrans/build/src/makeobj/makeobj.exe`; BUILDING.md will record how to rebuild it.

## 9. Acceptance criteria (brief §18)

`.pak` compiles clean; unit is buyable and runs only on electrified track; one click
assembles exactly A-B-C-D with cabs at the ends and panto on C; invalid consists
impossible; 8 directions reviewed and aligned; colour validator passes; real in-game
screenshots exist; ZIP built; docs complete; no personal absolute paths inside
shipped files; a second clean build reproduces the `.pak`.

## 10. Build order

spec.json → flirt.py + build.py → prototype `cab_a` (render+dat+pak, colour report)
→ full 4-car with couplings → install → in-game tests → screenshots → release + ZIP
→ report. A reproducible log is kept at each step.
