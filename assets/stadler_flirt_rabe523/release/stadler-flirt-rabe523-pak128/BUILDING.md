# BUILDING — Stadler FLIRT RABe 523 (SBB) for pak128

The whole add-on regenerates from a clean checkout **through the Simutrans Blender
Kit**, not around it. Everything downstream of the geometry (rig, 8-direction
render, sprite sheet, `.dat`, reserved-colour validation, makeobj, install) is the
kit's own code, driven by `assets/stadler_flirt_rabe523/blender/build.py`.

## Versions used for v0.1.0

- **Blender 5.1.2** (the kit supports Blender 4.x/5.x).
- **Simutrans Blender Kit** at commit `769fc0b`.
- **makeobj** 60.12 (Simutrans 124.5.1 nightly), from a Simutrans source build:
  `simutrans/build/src/makeobj/makeobj.exe`.
- **pak128** (compiled testbed pakset).
- Platform: Windows 11, MSYS2/MINGW64 toolchain.

## Enable the add-on / open the project

The build script installs and enables the add-on itself, so nothing is needed by
hand. To open a car interactively instead:

1. In Blender, install `build/simutrans_blender_kit.zip` (Edit → Preferences →
   Add-ons → Install) and enable **Simutrans Blender Kit**.
2. Open `blender/cab_a.blend` (or `int_b` / `int_c` / `cab_d`).
3. The Simutrans panel (N-sidebar) drives Build Rig → Render Sheet → Compile .pak.

## Regenerate the sprites and `.pak`

From the kit root:

```
# one car (prototype, no couplings):
blender --background --factory-startup \
        --python assets/stadler_flirt_rabe523/blender/build.py -- cab_a

# the whole four-car unit, with the coupling chain:
blender --background --factory-startup \
        --python assets/stadler_flirt_rabe523/blender/build.py -- all
```

This prints `FLIRT_OK`, writes the sheets + `.dat` to `assets/stadler_flirt_rabe523/
sprites/`, runs the reserved-colour report, compiles each car with makeobj, and
installs the `.pak` into `build/sim-userdir128/addons/pak128/`.

## Combine into the single release `.pak`

```
cd assets/stadler_flirt_rabe523/sprites
makeobj pak SBB_FLIRT_RABe523.pak cab_a.dat int_b.dat int_c.dat cab_d.dat
```

## Configurable paths

The build script finds makeobj via `tools/toolchain.py`, overridable with the
`SIMUTRANS_MAKEOBJ` environment variable. Blender is found on `PATH` or via
`SIMUTRANS_BLENDER`. No absolute personal path is written into any shipped file
(the `.dat` `copyright=` is the author credit, `victor_18993`, not a path).

## Known issues / limitations

- Cost and running cost are **provisional** placeholders (see `TESTING.md`).
- The nose is a stylised 128 px approximation of the FLIRT bulb front, not a
  panel-exact model.
- Two full units cannot be coupled into a double unit **by design**: the coupling
  chain ends at the tail cab (`Constraint[Next]=none`), which is what makes an
  invalid consist impossible.
