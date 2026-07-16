# How Simutrans represents variants

Read before touching `core/variants.py`. Everything here is read off the engine's
own writers (`src/simutrans/descriptor/writer/*.cc`, engine 124.5.1) or off
`core/dat_schema.json`, which is extracted from them and held to them by
`tests/test_schema_drift.py`.

## The finding that shapes the design

**There are two completely different things people call a "variant", and the
engine only knows about one of them.**

### Axis variants — indexed inside one object

The engine addresses images by a key built with `sprintf`. Whatever indices that
key has ARE the variant axes, and there are no others. The widest image key each
writer builds:

| Writer | Widest image key | Axes, after the direction |
|---|---|---|
| `vehicle` | `freightimage[%d][%s]` | **cargo only** |
| `building` | `%simage[%d][%d][%d][%d][%d][%d]` | layout, y, x, height, **phase, season** |
| `way` | `%simageup%s[%d][%d]` | **season** |
| `way-object` | `backimage[%s]` | **none — ribi and nothing else** |
| `roadsign` | `image[%s][%i]` | **state (aspect)** |
| `tunnel` | `%simage[%s%s][%d]` | **season** |
| `bridge` | `backimage[ns][%d]` | **season** |

Reproduce it:

```
python -c "from core import schema; print(schema.OBJ_TYPES['vehicle']['patterns'])"
```

### Sibling objects — separate `.dat`, separate `name=`

Everything else. The engine has no idea two objects are related; they are two
entries in the catalogue that happen to share an artist and a mesh.

## Three consequences that the panel must not pretend away

**1. There are no liveries in base Simutrans.** Not "not implemented here" —
absent from the engine. The only occurrence of the string `livery` in the entire
source tree is inside the word *delivery* (`simfab.h:167`, a comment about
shipment size):

```
grep -rlnw "livery" src/          # no matches
```

Liveries are a Simutrans **Extended** feature. In base Simutrans a green loco and
a red loco are **two objects**, with two names, two `.dat` files and two `.pak`
files. `README.md` has said this since before this phase; the Variant Manager must
not contradict it by offering a livery axis that would silently do nothing.

**2. There is no day/night variant.** The engine does it itself. `simview.cc`
holds `hours2night[]` and calls `gfx->set_daynight_level(...)`; the swap is driven
by **reserved colours in the one sprite you already rendered**. There is nothing to
model twice, and a "night variant" would be a second sprite the engine never asks
for. This is what *Night Preview* has shown since 0.6 — the game's own swap applied
to the finished sheet, not a filter and not a second render.

**3. A vehicle has no season.** Its widest key is `freightimage[%d][%s]`. A winter
livery for a tram is a sibling object, not an axis. So is a catenary in the snow:
`way-object` has no second index at all.

## What that means for the tool

Two mechanisms, kept apart, because merging them would produce a tool that lies:

**Axis variants** are collections, and phase 1 already makes them
(`core/templates.py`: `season_1`, `phase_1`, `state_0`, `freight_0`). The Variant
Manager's job here is to say which axes *this* object actually has, and to refuse
the ones it does not — so an artist cannot ask for a seasonal catenary and get
silence.

**Sibling objects** are the real repetitive work, and nothing addressed them. A
five-car unit is five `.dat` files. A family of three liveries is three more. Today
that means editing the panel's fields by hand, once per object, and pressing Render
each time — with the numbers that must differ (`name`) sitting next to the numbers
that must not (`waytype`, `length`), and no record anywhere of which was which.

That is what `core/variants.py` models: one scene, N sibling objects, each a set of
**overrides** on the base, each with a **stable key** that survives renaming.

## Why the key is not the name

A variant's `name` is what the artist reads and what goes into the `.dat`. It will
change: `Loco_Green` becomes `RENFE_269_Green` the day they learn the class number.

The `key` is what the tool uses to know that this is still the same variant. It is
allocated once and never reused, so renaming is free and cannot orphan anything.
Keying variants by name would mean a rename silently creates a new variant and
abandons the old one's overrides — which is exactly the sort of quiet loss the
artist would only find much later.
