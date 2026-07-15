# Simutrans Blender Kit

[![tests](https://github.com/Dkijas/simutrans-blender-kit/actions/workflows/tests.yml/badge.svg)](https://github.com/Dkijas/simutrans-blender-kit/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Latest release](https://img.shields.io/github/v/release/Dkijas/simutrans-blender-kit)](https://github.com/Dkijas/simutrans-blender-kit/releases/latest)

A modern **Blender 4.x/5.x** add-on that takes a 3D model and produces everything
Simutrans needs: the directional sprites, the sprite sheet, and a compilable
`.dat` — with the reserved colours preserved byte-for-byte. With makeobj configured,
it goes all the way to an installed `.pak` without leaving Blender.

## What it makes

The panel builds **eight object types**, each grounded in the engine's own writer
and verified in a running game:

| Object | What it emits |
|---|---|
| **Vehicle** | 4 or 8 directional sprites, plus **cargo (freight) variants** — a different sprite empty vs. loaded with a good |
| **Building** | footprint × height × layout × phase × season, and **stations, depots and extensions** |
| **Way** | the 16 ribi combinations from 6 models, plus slope images |
| **Catenary** (way object) | overhead line in two layers (`backimage`/`frontimage`), plus slopes |
| **Sign / Signal** | four directions, signal states (state 0 = red) |
| **Tunnel** | a portal, four directions, two layers |
| **Bridge** | span, ramps and pillars, two layers, with length/height limits |
| **Factory** | a building plus its economics — the goods it makes or consumes |

Around them: a **`.dat` linter**, **reserved-colour** preservation, **pakset
profiles** measured from the real pakset, **makeobj** compilation and `.pak`
install, an **English/Spanish** panel, and an automated suite that renders,
compiles and loads every one through Blender, makeobj and a headless Simutrans.

## Why

The Simutrans 3D art pipeline has been **frozen on Blender 2.79 / Blender Internal
since 2020**. The pakset maintainer's public position is still "use 2.79"
([forum 19475](https://forum.simutrans.com/index.php?topic=19475.0)); the forum's
3D-modelling board has had no new topic since 2020; a GitHub search for
"simutrans blender" returns **zero** repositories. Meanwhile pak64 ships **no
vehicle template at all**.

This kit is greenfield and aimed at **new artists** and at **pak64/pak128**, which
have no reference rig to be compatible with — sidestepping the reason the old
rigs were never ported (pak128.Britain's thousands of `.blend`s use
Blender-Internal materials and would need converting, which is a separate,
much larger problem).

## What makes it correct

Everything is **derived from the engine source**, not from tutorials.

| Fact | Value | Source |
|---|---|---|
| Projection | 2:1 dimetric — tile is `S` wide, `S/2` tall | `display/viewport.cc` `get_screen_coord()` |
| Camera | Orthographic, **elevation exactly 30°** (Blender `rot_x = 60°`) | derived: `sin(elev) = 1/2` |
| `ortho_scale` | `tile_world × √2` | derived |
| Direction keys | `s w sw se n e ne nw` | `descriptor/writer/vehicle_writer.cc:179` |
| 4 vs 8 images | 4 is legal; engine **reuses** (does not mirror) the opposite heading | `descriptor/vehicle_desc.h` |
| `length` unit | 1/16 of a tile | `simconst.h` `OBJECT_OFFSET_STEPS` |
| Player colours | blue `36,75,103…176,210,255`; gold `123,88,3…255,249,13` | `documentation/simutrans-palette.pal` |
| Transparency | `231,255,255` | makeobj |

The camera is not "roughly isometric": `tests/test_core.py` **proves** that
projecting through it gives the same pixels as the engine's own
`get_screen_coord()`, for every tile size, to 1e-9.

Three consequences of that rigour worth calling out:

* The German wiki's `ortho_scale = 2.800` is **~1% wrong** — the exact value is
  `2√2 = 2.8284`. Sprites rendered with 2.800 come out ~1% too large.
* **Special colours cannot survive a normal render.** Blender's default AgX view
  transform tone-maps every pixel, and Blender dithers when writing 8-bit — so a
  player-colour blue painted as `(96,132,167)` lands in the PNG as something
  else, and the engine (which matches reserved colours *exactly*) then refuses to
  recolour it. The kit forces `view_transform = Standard`, disables dithering, and
  renders special colours as shadeless emission with an **sRGB→linear**
  pre-correction. This is verified end-to-end.
* **A `.dat` has no end-of-line comments.** `tabfile_t::read_line()` skips a line
  only when it *starts* with `#` (or a space) — it never strips a `#` that follows
  a value. So `freight=None   # a note` really does set freight to the string
  `"None   # a note"`, and the pakset loader then dies with
  `Cannot resolve 'GOOD-None   # a note'`. Numeric keys mask the bug because
  `atoi()` stops at the space, which is presumably why the convention survives in
  hand-written `.dat`s. Every comment the kit emits sits on its own line.

## Install

Download **`simutrans_blender_kit.zip`** from the
[latest release](https://github.com/Dkijas/simutrans-blender-kit/releases/latest),
then in Blender: *Preferences → Add-ons → Install from Disk* → pick the zip. Press
**N** in the 3D view and pick the **Simutrans** tab.

To build the zip from source instead:

```
python tools/build_addon_zip.py      # writes build/simutrans_blender_kit.zip
```

Model your vehicle **standing on `z = 0`, centred on the world origin, nose along
+X**, then: *Build Rig* → *Render Sheet* → *Check Colours* → *Compile .pak*.

*Compile .pak* needs `makeobj`, which is not shipped with anything — build it once
from the Simutrans source:

```
cmake --build <builddir> --target makeobj      # it is EXCLUDE_FROM_ALL
```

Point the panel at the resulting `makeobj.exe`, optionally give it a pakset's
`addons/` folder to install into, and the model goes from Blender to a vehicle
the game sells without leaving Blender.

## Languages

The panel follows the language already set in *Preferences → Interface →
Translation* — there is no separate setting to hunt for. **English and Spanish**
ship today.

Adding one is `addon/translations.py`: copy the `es` block, key it by Blender's
locale code (`de_DE`, `fr_FR`, `ja_JP`, …), translate the values. The test suite
then holds you to it — a language that misses a string, invents one the panel
never shows, or **drops a `%d` from a format string** fails the build. That last
one is the reason the check exists: a translation that loses its placeholder
crashes at runtime, and only for the users who speak that language.

The `waytype` and `engine_type` values (`track`, `road`, `diesel`, …) are
deliberately *not* translated: they are not prose, they are the literal keywords
written into the `.dat` and read by makeobj.

## Layout

```
__init__.py      the add-on entry point (bl_info, register)
core/            pure Python, stdlib only — runs inside Blender or standalone
  projection.py    the exact camera geometry, and the alignment (+ derivations)
  directions.py    the engine's direction codes and fallback rules
  paksets.py       pak64/128/192/256 profiles, measured from the real pakset
  colors.py        reserved colours + a validator for accidental hits
  night.py         the three night-light paths, per colour class
  sheet.py         PNG read/write (zlib only; reads palettes) + sheet assembly
  datgen.py        vehicle .dat, incl. freight (cargo) variants
  buildings.py     footprint/height/layout/phase/season + stations & depots
  ways.py          the six models → sixteen ribi images, and slopes
  roadsigns.py     sign/signal directions and states
  tunnels.py       portal images, four directions, two layers
  bridges.py       span / start / ramp / pillar image groups
  factories.py     a building plus its economics (goods in/out, mapcolor)
  convoy.py        car length in tiles, for coupled units
  schema.py        the .dat linter (keys read from the engine's writers)
addon/
  rig.py           Blender: build rig, render N directions/pieces, sheet + .dat
  ui.py            the Simutrans sidebar tab
  translations.py  the panel's strings, per language (plain data, no bpy)
examples/
  demo_loco.py     a real, installable vehicle from a Blender model
  demo_house.py    a building the game plants on the map
  demo_all.py      one of every object type
  civia.py         a five-car pak128 unit (Civia S/465)
  cercanias.py     a commuter set
tools/
  build_addon_zip.py
  lint_dat.py          the linter, standalone
  measure_pakset.py    reads a real pakset's tile_height / height factor
  extract_dat_schema.py  re-derives the linter's key list from the engine
  run_tests.py         renders, compiles and runs the whole suite
tests/
  test_core.py         1,145 checks, no Blender needed
  test_pakset_profile.py  profiles vs. the real pakset's simuconf.tab
  blender_e2e.py       full pipeline inside Blender (model → sheet → .dat)
  blender_alignment.py the tile quad lands at 3/4; opposite headings match
  blender_addon.py     installs the zip and drives the panel's own buttons
  blender_{building,way,freight,tunnel,bridge,infra,panel,footprint}.py
```

## Buildings

A vehicle is one sprite per heading. A building is a **grid**, and the engine
addresses it like this:

```
BackImage[layout][y][x][height][phase][season]
```

so a house taller than one cell is cut into **height slices**. The stacking step
comes from the engine (`obj/gebaeude.cc`: `ypos -= raster_width`) and is a **full
`tile_px`** — not `tile_px/2`, which is the tempting mistake, because that is how
tall the ground diamond is.

The kit renders the whole building **once**, into a canvas big enough for the
footprint and the height, and then slices it. Rendering each cell with its own
camera would be the obvious approach and it would be wrong: the slices have to
line up to the pixel, and the only way to guarantee that is to cut them out of
the same image. Empty slices above the roof are dropped, and the ones that remain
are contiguous from `h=0` — the engine stops at the first missing height, so a
hole silently decapitates the building.

`examples/demo_house.py` produces one; the game then plants it:

```
BKITHOUSE_OK: BKit_House is standing at (2,2) size=1x1 capacity=64
```

`capacity=64` is not a coincidence — the writer does `level = level-1` and then
defaults capacity to `level*32`, so `level=3` gives exactly 64.

Getting that verdict took a detour worth writing down: the obvious check, *"is it
in the building list?"*, returns an **empty list even for pak64's own houses**.
City buildings are not in the scripted catalogue at all — `hausbauer_t::get_list()`
returns `NULL` for `city_res` (`builder/hausbauer.cc:1006`); they live in a
separate `get_citybuilding_list()` that the API never exposes. So the kit does the
stronger thing instead and **builds the house on the map** with the engine's own
tool.

### Which way a layout turns

A layout is the building rotated to face the road, and the engine is the one that
decides which. `world/simcity.cc` holds the table:

```c
static int  const building_layout[] = { …, 0, 1, 4, 2, … };
static koord const neighbors[]      = { (0,1), (1,0), (0,-1), (-1,0) };
```

Read off the single-road cases — `building_layout[1<<i] == i` — and it says: a road
at `neighbors[L]` gives layout `L`. In the *engine's* grid that is south, east,
north, west; in **Blender**, where north is +Y (see [The engine's world is
left-handed](#the-engines-world-is-left-handed)), it is −Y, +X, +Y, −X — a step of
**plus 90°** each time.

**Model convention: the façade — the side that should face the road — points along
−Y, which is the side Blender's own Front view looks at.**

That plus sign cost us. It used to be minus, from a real measurement against a
shipped pak128 house (`cityhouses/res/res_00_08`, `dims=1,1,4`), tracking its
chimney across the four layouts:

| layout | measured | −90°·L | +90°·L |
|---|---|---|---|
| 1 | −7.33 | **−7.43** | +7.43 |
| 3 | +8.69 | **+7.43** | −7.43 |
| | residual | **1.6 px** | 21.9 px |

The measurement was right. The *frame it was expressed in* was the engine's, which
is left-handed — and conjugating a rotation by a reflection reverses its sense, so
the engine's −90° per layout is Blender's +90°. Two correct steps composed into a
wrong answer, and every house would have stood with its back to the street. It is
now checked in pixels, by `tests/blender_footprint.py`, which puts a post on the
façade and demands it land where `neighbors[L]` says.

A layout also turns the building about **the centre of its footprint**, not about
its corner tile — the engine anchors it at (0,0) and grows it into +x/+y. Turn a
2×1 about its corner and it swings off its own plot, and the slicer then cuts the
cells out of the wrong part of the render. A 1×1 building's centre *is* its corner,
which is exactly why this hid until the first two-tile house.

### The engine's world is left-handed

The single most load-bearing fact in the kit, and the one that is easiest to get
almost right.

The engine's axes are x = east, y = **south**, z = up. Take the cross product:
east × south = up. In any right-handed frame it is east × *north* that gives up. So
the engine's world is **left-handed** — and Blender's is not.

No rotation carries one onto the other. Only a reflection does. Model a tile with
"+X is east, +Y is south" and there is **no camera azimuth** that reproduces
`viewport_t::get_screen_coord`. We measured all four, by putting a marker on each
axis and finding it again in the pixels, and none of them fit. Three of them fit
*halfway* — they get two of the four compass points right — which is precisely how
you ship a pakset whose curves connect backwards.

The fix is not a hack. It is a choice of labels:

```
IN BLENDER:   +X = EAST      +Y = NORTH      −Y = south      −X = west
```

Blender's (east, north, up) *is* right-handed, so the two frames now agree, and the
engine's tile index `y` — which grows southward — simply runs along Blender's −Y.
Nothing about the artwork is mirrored; only the name we give an axis. It is also
the convention an artist would guess: north is up the map.

With those labels the camera that reproduces the engine exactly is **azimuth 45°**
(`projection.WORLD_AZIMUTH_DEG`).

And here is the check that makes it trustworthy. A vehicle is modelled nose along
+X, and `directions.BASE_AZIMUTH_DEG` — the azimuth at which that nose must read as
*heading south* — was measured, independently and long before any of this, against
a shipped pak128 bus: **135**. Now derive it instead. South is −Y, so the nose turns
−90°, so the camera turns +90°:

```
45 + 90 = 135
```

It falls out. Two separate roads to the same number, one from the engine's source
and one from somebody else's art.

### Seasons — and the third image that is never drawn

`obj/gebaeude.cc` picks a building's season image through one table:

```c
static uint8 effective_season[][5] = {
    {0,0,0,0,0},   // 1 image
    {0,0,0,0,1},   // 2 images
    {0,0,0,0,1},   // 3 images   <-- a copy of the row above
    {0,1,2,3,2},   // 4 images
    {0,1,2,3,4},   // 5 images
};
```

The column is the world's season — `simworld.cc` maps months with
`month_to_season[12] = {2,2,2, 3,3, 0,0,0,0, 1,1, 2}` and the comment *"summer
always zero"*, so **0=summer, 1=autumn, 2=winter, 3=spring** — and column 4 is
**snow** (above the snowline, or arctic).

Two things fall out that no tutorial mentions:

* **With two images the second one is the SNOW image, not "winter".** It only
  appears above the snowline. In a temperate December the engine still draws
  image 0.
* **With three images the third is never drawn at all.** The row for 3 is a copy
  of the row for 2. An artist can spend a day painting a third season and the
  game will not show it once — and makeobj says nothing.

So the counts worth using are **1, 2, 4 and 5**, and the linter warns about 3.

`render_building(seasons=2, season_setup=...)` calls back before each season so
the model can put its snow on; asking for more than one season without a callback
is an error, because otherwise every season renders identically and the whole
pass is a no-op nobody notices.

### Animation

`phases` are cycled every `animation_time` milliseconds, and — like the height
slices — they must be contiguous from 0, because the engine stops at the first one
it cannot find. `render_building(phases=2, phase_setup=…)` calls back before each
frame.

One detail worth knowing: the engine starts each building on a **random** phase
(`obj/gebaeude.cc`: `anim_frame = sim_async_rand(phases)`), so a street of
identical houses does not blink in unison. Nothing to do about it — just don't
expect frame 0 to be the one on screen.

Buildings are now complete: **footprint × height × layout × phase × season**, all
keyed the way the engine indexes them, `BackImage[l][y][x][h][phase][season]`.

### Stations, depots and extensions

A stop, a depot or an extension is a building with a `type` (`building_writer.cc`
reads it from the `type=` key), a `waytype`, and — because the player places it —
an **icon**. That last part is not optional: `builder/hausbauer.cc` gives a
player-built building with no cursor image a `NULL` builder, exactly like the way
and the tunnel, so a station without an icon loads perfectly and **cannot be
built**. The kit emits the icon for these types and lets you pick the kind and the
goods it accepts (passengers, mail, freight). Verified: the generated stop turns up
in the engine's own station-builder list.

## Ways — six models, sixteen images

A way is not one sprite. The engine picks a different image depending on which
neighbours the tile connects to, and it addresses that image by a four-bit mask
called the **ribi** (`dataobj/ribi.h`):

```
1 = North      2 = East      4 = South      8 = West
```

`way_desc.h` then does, with no indirection whatsoever:

```c
get_image_id(ribi) → get_child<image_list_t>(n)->get_image_id(ribi)
```

**The image list is indexed by the bitmask itself.** Sixteen entries, one per
combination.

Now the useful part. The camera never moves, but the way can be *turned* on the
tile — and because the four bits are in compass order, a quarter-turn is just a
rotate-left on the mask. So each modelled piece sweeps out a whole orbit of ribis:

| piece | base ribi | turns | covers |
|---|---|---|---|
| `none` | 0 `-` | 1 | `-` |
| `end` | 1 `n` | 4 | n e s w |
| `straight` | 5 `ns` | 2 | ns ew |
| `curve` | 3 `ne` | 4 | ne se sw nw |
| `tee` | 7 `nse` | 4 | nse sew nsw new |
| `cross` | 15 `nsew` | 1 | nsew |
| | | **16** | every ribi, exactly once |

**Six models, sixteen images, no gaps and no duplicates.** That is not a happy
accident — it is the orbit decomposition of the rotate-left action on four bits.

Model the six shapes into collections named `way_none`, `way_end`, `way_straight`,
`way_curve`, `way_tee`, `way_cross`, and `render_way()` does the rest.

A missing piece is not an error: the writer stores an empty image and the engine
draws nothing. So a road with no `cross` is **invisible at every four-way
junction**, and nothing warns you. `ways.missing()` will.

`tests/blender_way.py` does not look at the sixteen images and nod. For each one it
samples the four tile-edge midpoints — whose pixel positions follow from the
engine's own projection — and demands the asphalt reach exactly the edges its ribi
names, and no others. The first version of the module failed all twelve asymmetric
images with a clean reflection (n↔w, e↔s), which is what sent us to find the
[left-handed frame](#the-engines-world-is-left-handed).

### No icon, no object

`builder/wegbauer.cc`, when the pakset loads:

```c
if( desc->get_cursor()->get_image_id(1) != IMG_EMPTY ) {
    tool_build_way_t *tool = new tool_build_way_t();   // …and register it
}
else {
    desc->set_builder( NULL );
}
```

Image 1 of the cursor skin is the **icon**. Ship a way without one and the engine
loads it perfectly, lists it nowhere, gives it no toolbar button, and hands the
scripting API a way with no builder — so it **cannot be built at all**. makeobj does
not warn. The pakset does not warn. It is simply not in the game.

That same line appears, word for word, in `obj/wayobj.cc`, `obj/roadsign.cc`,
`builder/brueckenbauer.cc`, `builder/tunnelbauer.cc` and `builder/hausbauer.cc`: it
is the rule for **everything the player builds**. The linter now checks it.

We found it the only way anyone ever finds it — by laying the road in a running
game and being told there was no such road.

## Catenary and signals

Both ride on the ribi machinery the ways already proved, so the six models carry
straight over. What is new in each is one thing that ships backwards very easily.

### The catenary has two layers

A wayobj needs **`backimage[ribi]` and `frontimage[ribi]`** — drawn before and after
the vehicles. The masts and the far wire belong behind the train; the contact wire
that crosses **over** it belongs in front. Put everything in the back list and the
`.pak` compiles, the game runs, the catenary appears — and the train drives straight
over its own overhead line. Nothing warns you, because nothing is *wrong*: the
images are simply in the wrong list.

The engine cannot make that split for you. It is a modelling decision about which
parts of the mesh are nearer the camera than a vehicle in the middle of the tile.
So the artist makes it, by putting the front parts in a `wayobj_<piece>_front`
collection alongside the `wayobj_<piece>` one.

And the type is spelled **`obj=way-object`** — with a hyphen. The class is
`way_obj_writer_t`, the file is `way_obj_writer.cc`, the header says `way_obj`;
`get_type_name()` returns `way-object`. Every name around it says otherwise. We
guessed wrong, and the linter caught it, because the linter reads
`get_type_name()` rather than the filenames.

### The signal's state 0 is red

`roadsign_writer.cc` reads `image[<direction>][<state>]`, and `obj/signal.cc`
flattens them:

```c
desc->get_image_id( 3 + state*4 )   // east
desc->get_image_id( 0 + state*4 )   // north
desc->get_image_id( 2 + state*4 )   // west
desc->get_image_id( 1 + state*4 )   // south
```

So the index is `direction + state*4`, with **0 = n, 1 = s, 2 = w, 3 = e**. That is
`general_sign_directions[]` — and note it is *not* compass order. "Fixing" it into
n, e, s, w points every sign the wrong way.

And `obj/roadsign.h`: **`STATE_RED = 0`**. Swap the aspects and the signal shows
green for danger. That is not a rendering bug, it is a signalling bug, and the
trains will act on it — which is why `render_roadsign(states=2)` *demands* a
`state_setup` callback and the test checks, pixel by pixel, that state 0 is red in
all four directions.

Verified in a running game (`bkitinfra`): lay a rail, hang the wire, then ask the
way itself `is_electrified()` — the very call an electric locomotive makes before
it will move. If it says false, the catenary is decoration.

## Tunnels, bridges and factories

Three more object types, each modelled the way its engine writer reads it and each
checked buildable (or loadable) in a running game.

* **Tunnels** are a portal in four directions and two layers — a back part behind
  the vehicle and a front part over it — plus the mandatory build icon (same rule
  as the way and the station: no icon, no builder). Model the portal once, and the
  rig turns it.
* **Bridges** carry the four image groups the engine reads — `image` (the span),
  `start`, `ramp` and `pillar`, each with an optional double-height `…2` set
  (`bridge_writer.cc`) — plus the length, height and pillar-distance limits. Model
  `bridge_span`, `bridge_start`, `bridge_ramp`, `bridge_pillar` and it assembles
  them.
* **Factories** are a building *plus* its economics in one `obj=factory`: the goods
  it makes or consumes (each a cross-reference that must resolve when the game
  loads — makeobj compiles it unresolved), the productivity, and a **minimap
  colour**, which is not optional — `factory_writer.cc` calls `dbg->fatal(...)`
  without it. The sprites are the ordinary building render; the factory node simply
  wraps the building node the writer already knows how to emit.

One caveat kept honestly: the exact **portal/piece-on-which-hill** mapping for
tunnels and bridges is derived from the engine's slope tables. The pieces are
verified buildable; which one lands on which slope is the reflection you confirm by
eye in a windowed game, not from a headless run.

## The .dat linter (no Blender needed)

```
python tools/lint_dat.py myvehicle.dat
python tools/lint_dat.py pak128/vehicles/       # recurses
python tools/lint_dat.py --json vehicles/       # machine-readable, for CI/editors
```

Every finding carries a stable code (`no-icon`, `dup-key`, `bad-int`, …), and a
line `# bkit: ignore=no-icon, dup-key` anywhere in a `.dat` silences those codes
for that file — the escape valve for a finding you have read and accept.

There is no schema document for `.dat` files; the authority is the C++ that reads
them. So we don't hand-maintain a key list — `tools/extract_dat_schema.py` reads
`src/simutrans/descriptor/writer/*.cc` and pulls out **34 top-level `obj=` types
and 636 keys**, including the image keys that are built at runtime
(`sprintf(buf, "emptyimage[%s]", dir)`). A test re-extracts and **fails if our copy
has drifted from the engine**, because a stale linter is worse than none: it calls
brand-new valid keys "unknown".

It exists because makeobj will happily compile a `.dat` the game then chokes on,
and the format has two **completely silent** failure modes:

* **An end-of-line comment is not a comment.** `tabfile_t::read_line()` drops a
  line only when it *starts* with `#`. So `freight=None  # a note` sets freight to
  `"None  # a note"` and the pakset loader dies with `Cannot resolve 'GOOD-None  #
  a note'`. Numeric keys hide it — `atoi()` stops at the space. This one cost us a
  working game.
* **An indented line is not a key.** `read_line()` also drops any line starting
  with a space. Line your keys up prettily and the engine never sees them; your
  locomotive quietly has no engine.

It also catches typos, and — because it knows every type's keys — tells you when a
key is real but on the wrong object: *"obj=vehicle does not read 'climates' — it
belongs to obj=building"*.

On pak128's own shipped `.dat` files it reports **77 findings and zero false
positives** — and that is the bar, because a linter that cries wolf on working art
is the one people turn off. The 77 are real: 49 duplicate keys (a repeated key is
silently dropped by the engine, so the second line is dead), 25 keys the engine
does not read, and 3 unknown `obj=` types. Every one is a thing the pakset gets
away with, not a thing the linter invented. (An earlier version of this README
claimed "zero findings", which was wrong; the achievement is zero *false* ones.)

## Running the tests

```
python tools/run_tests.py            # core + Blender + the game, one verdict
python tools/run_tests.py --list
```

The game suites need a headless Simutrans, built **once**, out of tree:

```
cmake -S <simutrans> -B build/sim-headless -DSIMUTRANS_BACKEND=none
cmake --build build/sim-headless --target simutrans
```

`SIMUTRANS_BACKEND=none` compiles to `COLOUR_DEPTH=0` and a null renderer — no
window, no SDL. The whole suite renders every object through Blender, compiles the
`.pak` files the game suites load, and runs the headless engine on each — a few
minutes end to end. The fast inner loop is `python tools/run_tests.py core`, which
is the Blender-free half and takes under a second.

### The runner refuses to lie

Verifying the game side by hand meant: launch the windowed game, sleep 20
seconds, grep a log, `taskkill /IM simutrans.exe`. Simutrans' own runner
(`tools/run-automated-tests.sh`) does much the same, and is Linux-only besides.
Every step there is a false green waiting to happen — a sleep that is too short,
a grep that reads a stale log, a kill-by-name that shoots down the player's own
game.

This runner reads the engine's stdout as it arrives, stops at the first verdict,
kills by **PID**, and watches for the engine's own distress markers (a script
that fails to compile, an unhandled Squirrel error) so a broken test fails in a
fraction of a second instead of sitting out its timeout.

Most importantly, **a run that produces no verdict is a FAILURE**, and a suite
that cannot run is reported as `SKIP` and still turns the build red. All three
were checked adversarially: a scenario that does not exist, a scenario whose
script throws, and a scenario that runs perfectly but never prints its sentinel.
All three go red.

## Status

The full suite is **35 suites, all green** (`python tools/run_tests.py`), from the
Blender-free core checks through the Blender renders to the headless game, including
scenarios on a real **pak128**.

* `core` — **1,145 checks pass** (`python tests/test_core.py`).
* Blender pipeline — **end-to-end green on Blender 5.1**
  (`blender --background --python tests/blender_e2e.py` → `E2E_OK`):
  renders 8 × 128×128 RGBA, assembles a 4×2 sheet, writes a compilable `.dat`,
  and the validator confirms the player-colour stripe survived the render
  **exactly** (`#6084A7`).
* Alignment and lighting — `blender_alignment.py` → `ALIGN_OK`.
* The add-on — `blender_addon.py` → `ADDON_OK`: builds the zip, installs it into
  Blender, enables it, and drives the panel's own buttons.
* Every object type — vehicle (with freight variants), building, station/depot,
  way, catenary, signal, tunnel, bridge and factory — is rendered, compiled and
  then **loaded or built in the headless game**, each with its own scenario.
* `profile` — the pakset profiles are checked against the real pakset's own
  `config/simuconf.tab`, and skip cleanly when no pakset is mounted.
* **The loop is closed** — the output is a vehicle the game buys and drives, and
  two real multi-car pak128 units (a Civia S/465 and a Madrid Metro 9000) assemble
  and run under pak128 catenary.

### Closing the loop: model → `.pak` → in the depot

```
blender --background --python examples/demo_loco.py -- pak64
makeobj pak bkitloco.pak bkitloco.dat
```

`makeobj` compiles it with no warnings. Dropping the `.pak` into
`<userdir>/addons/pak/` and starting the game with `-addons` loads it with no
errors — but *loading* is not the same as being *buyable*, so the kit asks the
engine's own catalogue (the very list the depot dialog is built from):

```
BKITCHECK: rail vehicles available = 149
BKITCHECK_OK: BKit_Switcher topspeed=90 power_raw=38400
```

149 = pak64's 148 rail vehicles **+ ours**. The numbers round-trip exactly:
`topspeed` is the `speed=90` we asked for, and `power_raw` is the engine's
`power × gear` = 600 kW × 64. That end-of-line-comment bug above is precisely
what this step caught — the `.pak` compiled cleanly and still killed the game.

And being buyable is still not the same as being *aligned*, so a second scenario
lays a track, builds a depot, buys the loco and runs it:

```
BKITDEMO_OK: BKit_Switcher is running between (4,2) and (4,13)
BKITDEMO: track = steel_sleeper_track, depot = TrainDepot
```

### Base azimuth — measured, not guessed

The one thing the engine source does *not* pin down is which camera angle is the
heading called `s`. Rather than guess, we measured it against a vehicle that
actually ships in pak128 (`vehicles/road-psg+mail/aec_aclo_regent_iii`, by Zeno):
reading its `.dat` against its sheet gives three hard constraints —

* `nw`, `se` are **end-on** views,
* `ne`, `sw` are **broadside** views,
* `n`, `s`, `e`, `w` are **three-quarter** views.

(End-on is not a mistake: a vehicle running along a world diagonal travels
straight up/down the screen — i.e. along the camera axis.)

With the camera at azimuth `az`, the model's nose (+X) lands on screen at
`(cos az, −0.5 sin az)`, so end-on is where that vector is shortest and broadside
where it is longest. Solving gives **`BASE_AZIMUTH_DEG = 135`**, and the real
bus's nose sitting at the lower-left of its `S` frame settles the remaining
180° flip.

Our first value, 45°, was **wrong by exactly 90°** — it would have put every
diagonal heading's vehicle facing the wrong way. `test_base_azimuth_matches_real_pakset_art`
now locks the convention in, and the rendered sheet reproduces the real bus's
end-on/broadside/three-quarter pattern cell for cell.

**Model convention: the vehicle's nose points along +X.**

### Alignment — the ground is at 3/4, not at the centre

The cell is `tile_px` square, but the tile is *not* in the middle of it. Measured
from pak128's own tile cursor (`landscape/grounds/marker.png`; slope 0 is drawn
from `marker.0.0` + `marker.3.0`, which together are exactly the flat diamond):

```
flat tile in the 128px cell:  x 2..125   y 65..126   centre (63.5, 95.5)
```

So the tile centre sits at **(1/2, 3/4)** of the cell — the diamond fills the
bottom half and the top half is the headroom a vehicle grows up into. pak128's
rail template (`devdocs/rail-template.png`) independently agrees.

The kit therefore aims the camera not at the model but at a point lifted
`tile_world × √6/6` above the tile centre, which pushes the ground down by
exactly `tile_px/4`. `tests/blender_alignment.py` renders an actual tile-sized
quad through the rig and measures where it lands: **centre (63.5, 95.5)** — the
same half-pixel as the shipped art.

**Model convention: the model stands on `z = 0`, centred on the world origin,
nose along +X.** Then it comes out sitting on the rail, with no fiddling.

### The sun turns with the camera — the engine says so

Our rig keeps the model still and orbits the camera, which only reproduces the
game if the sun orbits too. Leave the sun pinned to the world and it ends up
pinned to the *vehicle's body* instead of to the screen.

The proof is the engine's own fallback rule: a vehicle may ship just 4 images,
and the engine then **reuses** `image[dir-4]` for the opposite heading — it does
not even mirror it (`vehicle_desc.h`). Reuse is only correct if a symmetric
vehicle looks identical heading north and heading south, which is only true when
the light is fixed relative to the *screen*. `blender_alignment.py` renders a
plain box and demands all four opposite pairs come out **pixel-for-pixel equal**;
with a world-pinned sun they do not.

The sun leads the camera by 45°: the docs put it "south, bottom-left of screen",
the bottom-left corner of the diamond is world +Y (azimuth 180), and the base
camera is at azimuth 135.

### Not yet done

Buildings, freight (cargo) variants, ways, catenary, signals, tunnels, bridges,
stations/depots and factories have all landed since this section first listed them
as pending. What is still open:

* **Livery variants** are a Simutrans *Extended* feature, not base Simutrans, so
  they are out of scope here; freight (cargo) variants are the base-game equivalent
  and are implemented.
* **pak192 and pak256 profiles** carry the engine defaults — those paksets are not
  mounted here to measure. The `profile` test will measure them the day they are.
* **Per-slope orientation** of tunnels and bridges is derived, not yet eye-checked
  in a windowed game (see above).

**Not a gap — a property of the engine: long vehicles are convoys, not big
sprites.** A single vehicle draws **one image per heading** (`vehicle.cc`
`get_image_id(dir, freight)`), and that image is capped at **one `img_size` cell**
— `image_writer.cc` reads every `image=file.row.col` as exactly one
`img_size × img_size` square (`row *= img_size; col *= img_size`), 128×128 for
pak128. There is no way for one sprite to span more tiles. A vehicle physically
longer than a tile is therefore built the way the engine intends: as a **convoy of
coupled one-tile cars**, each its own `.pak`, each with its own `length`. The kit
already does this — the two example units (a five-car Civia and a six-car Metro)
are assembled and run that way. The `length` field (in `1/16` of a tile) sets a
vehicle's spacing and coupling, not its image size.

## License

The code is **MIT** — reuse it however you like, in anything.

Matching Simutrans' own Artistic 1.0 looked like the obvious choice and was the
wrong one: `addon/` imports `bpy`, which makes it a derivative work of Blender
and obliges it to be GPL-compatible. Artistic 1.0 is not. MIT is, and it is more
permissive besides.

The two example trains are 3D models of real vehicles (a Renfe Civia 465 and a
Madrid Metro serie 9000) by victor_18993. The **original modelling work** is
**CC BY 4.0**; the licence covers our geometry and textures only, not the operators'
trademarks or designs, which the models merely depict. Each folder has its own
`LICENSE.md`, and both points are set out in [LICENSING.md](LICENSING.md).
