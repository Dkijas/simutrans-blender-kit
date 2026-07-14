# Renfe Civia S/465 for pak128

A five-car Cercanías unit, built with the Simutrans Blender Kit, in this repository.

    CiviaS465_CabA   →  CiviaS465_Int1  →  CiviaS465_IntPanto  →  CiviaS465_Int3  →  CiviaS465_CabB

The couplings form a closed chain, so **one click on the cab car in the depot builds
the whole five-car unit, in order**: each car has exactly one possible successor, and
the depot follows the chain (`tool/simtool.cc`, the append tool). Nothing else can be
assembled from these five objects.

## Versions used

* Blender 5.1 (`--background`, no GUI needed)
* Simutrans 124.5.1 nightly, r12077 — engine, `makeobj`, and the headless build
* pak128 2.10.1
* The add-on is the one in this repo, installed from `build/simutrans_blender_kit.zip`

## How to rebuild the train

    python tools/build_addon_zip.py                     # if you changed the add-on
    blender --background --factory-startup \
            --python assets/civia_465/blender/build.py -- all

That installs the add-on, models the five cars, and then presses **the add-on's own
buttons** — `simutrans.build_rig`, `simutrans.render_sheet`, `simutrans.compile_pak`.
Nothing downstream of the geometry is done by hand. `-- cab_a` builds only the cab car,
without couplings, which is how the prototype was validated.

Outputs land where the brief asks: `renders/` `sprites/` `dat/` `pak/` `textures/`
`blender/` `reports/`, and the `.pak` files are also installed into
`build/sim-userdir128/addons/pak128/`, which is a TEST addons directory — not a real
installation.

## How to change the livery

Everything visible is painted in code, in `blender/civia465.py`:

* `livery_texture()` — bodywork, window band, doors, stripes, panel joints, grime.
  The colours are the named constants at the top of the file.
* `paint_decals()` — logos and lettering, on their own pass.
  `livery_texture(decals=False)` leaves them off entirely.
* `build_roof()` / `build_cab()` / `build_underframe()` — the geometry.

Then re-run the build command. The textures are also written to `textures/` as PNGs if
you would rather paint over them.

## Lint, compile, install

    python tools/lint_dat.py assets/civia_465/dat/      # 5 files, 0 errors, 0 warnings
    python assets/civia_465/tests/test_civia465.py      # 204 content checks
    python tools/run_tests.py civia game-civia          # content + the running game

`makeobj` is called by the add-on's `Compile .pak` operator; the full log is in
`reports/makeobj.log` (five vehicles packed, exit 0 each).

## Known limitations — the honest list

* **The rear cab car cannot switch its lights.** A vehicle in Simutrans has no night
  image at all: night lighting is purely the day→night colour swap in
  `display/simgraph16.cc`. So a cab shows the same lamps whichever end of the train it
  is on. Each cab therefore carries **both** white headlights and red tail lights on
  the same front — which is what a real cab has, and what the reference photograph
  shows. There is no way to do better without changing the engine, and I did not.
* **All five cars are `length=8`.** The real modules are 22.4 / 17.75 / 20.75 / 14.75 m
  and would give different lengths — which opens the joints, because the engine trails
  each car by the length of the one in front while the art is centred. Equal lengths
  close them for free. The other way — real lengths, art drawn off-centre by
  `core/convoy.py`'s offsets — is what pak128's own artists do, and I did not take it.
  See `reports/TODO_BALANCE.md`, including the correction: it is **not** true that
  every pak128 rail vehicle is length 8 (425 of 505 are), and I said so before I
  checked.
* **Bogie positions are not measured.** The works drawing is not dimensioned.
* **The lettering is a mark, not text.** At 128 px the `renfe` wordmark is two pixels
  tall.
* **Prices are provisional.** `cost` and `runningcost` are guesses and are listed as
  such in `reports/TODO_BALANCE.md`. Everything else comes from the sources or from the
  engine's own source code.

## What had to be fixed along the way

Four real defects, all found by looking at the result rather than at the code:

1. The roof equipment was so tall the car read as a double-decker.
2. The cab car had **no rear end at all** — the bare white end of the shell faced the
   camera in the `w` and `n` headings. The contact sheet caught it.
3. Every car took its **width and height from its own length**, so the short modules
   came out narrower and lower: a train thinner in the middle than at the ends.
4. The tail cab faced **forwards**. Simutrans draws every car of a convoy with the
   image for the direction of travel, so the rear driving car has to be modelled
   turned around — which is exactly why pak128 ships `BR-373_FrontCar` *and*
   `BR-373_BackCar`.

And the gaps between cars, which is the length story above.
