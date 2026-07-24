# Metro de Madrid Serie 2000A (1985) — pak128

The narrow-gauge one. Two cars, both with a cab, and the first unit in this
collection whose geometry is not the 7000's.

    python tools/run_tests.py asset-metro2000a metro2000a

## What it is

| | |
|---|---|
| Formation | **Mc-Rc** — a married M+R pair. Both cars have a cab. |
| In service | 1985. Still working Line 1 in 2026. |
| Speed | 65 km/h |
| Power | 594 kW, all of it in the M |
| Length | 14.72 m per car → **`length=7`**, not pak128's usual 8 |
| Cross-section | 2.30 × 3.34 m — *gálibo estrecho* |
| Doors | 3 double, per side |
| Livery | white and red, the 1980s scheme |
| Buildable as | 2, 4 or 6 cars — the pair repeats |

## Why this train exists, and it is not "another livery"

The 7000 and the 9000 in this repository are the same geometry. Not similar: **578
of `metro7k.py`'s 654 lines are byte-identical to `metro9k.py`'s**, every geometry
function among them, and the only difference in the rendered output is a red stripe
on the doors. Their sourced car lengths — 17.09 m against 18.425 m — reach a
`print()` and no pixel, because `REFERENCE_METRES` is assigned in both files and
read in neither.

This asset is the one that had to make the geometry mean something. Every
difference below is a fact from a source, not a styling choice:

- **Half a metre narrower** and 31 cm lower. You cannot repaint that.
- **`length=7`.** The first vehicle here that is not 8, and the reason is
  arithmetic: 14.72 m ÷ 2.11 m per carunit (the scale the 7000 already fixes at
  16.88 m = length 8) = 6.98. Safe because *every car of this unit* is 7, which is
  what closes the joints — `core.convoy.joint_gaps([7]*6)` returns all zeros.
- **Both cars have a cab.** In a six-car train that puts cabs in the *middle*,
  facing each other. The 7000 is one continuous *boa*. At 128 px this is the
  difference you actually see.
- **A flat, chamfered nose**, not the Pininfarina wedge. The CRTM's own text
  defines the *Serie B* by contrast with it: the B "se diferencia de la primera
  serie por la luna frontal que le da un aspecto de **burbuja**". The bubble is the
  other train.
- **Punched windows in pairs**, not a glazed ribbon. Take the red off both trains
  and the ribbon is what still says "modern".
- **Three doors**, not four.

## `REFERENCE_METRES` is load-bearing here

`Body.__init__` computes the cross-section from `spec.json`:

```python
self.width  = self.WIDTH_TW_PER_M  * SPEC.value("width_m")  * TW
self.height = self.HEIGHT_TW_PER_M * SPEC.value("height_m") * TW
```

The two factors are the only thing inherited from the 7000, and they are *two*
because 0.198/2.808 and 0.187/3.65 disagree by 38%: they were never a scale, they
were set by eye against pak128's catenary, one axis at a time. This asset fixes
that the metres are **read**; it does not pretend the pakset is dimensionally
honest, because it is not.

`build.py` proves it with a **mutation**, not an assertion: it doubles the spec's
width, rebuilds the `Body`, and insists the width doubled. Asserting
`width == FACTOR * spec.width * TW` would be tautological — it computes the
expectation exactly the way `Body` does, so it would pass against a hardcoded
constant that happened to agree.

## Where the numbers come from

Two sources, and for once neither is a photograph of a train in a tunnel:

- **[CRTM, *Breve historia de los Trenes de Metro de Madrid*](https://www.crtm.es/media/161812/metro_historico_historia_trenes.pdf)**
  — a scale side elevation of **M-2004** in the red-white scheme, drawn by Miguel
  Ángel Delgado with technical commentary by an engineer of Metro's Material Móvil
  department. The door centres, the stripe heights, the nose shape and the colours
  are measured off it at 1200 dpi.
- **[Vía Libre, April 2001, ficha of the Serie 2000](https://vialibre-ffe.com/pdf/11419_pdf_02.pdf)**
  — the technical table: 594 kW, 29 440 mm, 600 V, 65 km/h, 24 seated + 111
  standing, the axle arrangement.

**16 facts `measured`, 4 `reference`, 2 `engine`, 4 `derived`, and 2 `provisional`.**
The two guesses are `cost` and `runningcost`. That makes this the best-sourced unit
in the collection — the 7000 guesses its weight too, and the 9000 guesses its
weight, both prices, and nothing says how heavy either train is.

### The weight, which is sourced but not to the right fact

The ficha publishes **"peso en servicio"** — 26 200 kg (M) and 19 452 kg (R).
Simutrans's `weight=` is the **empty** vehicle; the engine adds payload mass on top.
No source publishes the tare for *any* Metro de Madrid series, so this is the
closest published fact, **not the right one**. If "en servicio" includes a passenger
allowance then this train is heavy and its acceleration is wrong.

It is in `spec.json` as `measured` with that written into its `note`, rather than as
a guess, because the number really does come from a source — what is uncertain is
the *interpretation*, and hiding that under `provisional` would lose the citation
without gaining honesty.

### The one weak spot: width and height

The Vía Libre ficha **does not publish them**. The only source is Wikipedia, which
this project has already caught in four errors on this very series. They are named
in `spec.json` rather than buried, because they are the numbers the whole model
turns on. **Confirm them against a works drawing before treating them as gospel.**

They are *not* measured off the CRTM elevation, deliberately. It is a paint-scheme
drawing: nothing on it is dimensioned, and measuring an illustration and calling the
result a measurement is precisely the move `tools/spec.py` exists to refuse.

## The couplings branch, and one thing the engine cannot say

    M   prev: none, R      next: R
    R   prev: M            next: none, M

Every entry does work. `none` on M's prev is what lets it lead
(`vehicle_desc.h:218`: `leader_count==1` with `get_leader(0)==NULL` matches only
`prev_veh==NULL`). `R` on M's prev is what lets a second pair follow a first.

This permits 2, 4, 6 — **and also 8, 10, 12**. Simutrans Standard has no way to cap
a convoy from the `.dat`: `get_max_convoi_length()` (`depot.cc:638`) counts
*vehicles* and is a global setting of the game, not a property of a vehicle.
Checked, not assumed.

That is a real over-permission and it is deliberate. The alternative is a hard-wired
six-car chain that cannot be bought as a pair — and a two-car 2000A is the more
common prototype, not a corner case. It is stated in the forum post rather than
papered over.

## Building the distributable pak

**List the files, never hand makeobj a directory**, or it writes a 69-byte empty pak
and says nothing:

    cd assets/metro2000a/pak
    makeobj MERGE MadridMetroS2000A.pak s2ka_mot.pak s2ka_rem.pak

Order is formation order. Verify it is not the empty pak:

    makeobj LIST MadridMetroS2000A.pak     # must name both vehicles

## What is NOT tested

**Nothing has been run in the game.** There is no headless Simutrans and no pak128
testbed on the machine this was built on, so there is no `game-metro2000a` suite and
no in-game screenshot. What that leaves unverified is real and specific:

1. **Whether a narrow-gauge body looks right against pak128's catenary.** The 7000's
   cross-section was tuned by standing it next to pak128's own 620 railcar and
   watching where the contact wire falls. This train is lower. Its pantograph is
   built to reach the same absolute height (`WIRE_TW`) on the reasoning that a real
   pantograph extends until it touches — but nobody has seen it touch.
2. **Whether the cabs really meet in the middle of a six-car train.** `MOT` and `REM`
   use the same `reversed` convention as the 7000's `cab_a`/`cab_b`, which is
   published and works, and the joint maths says every gap is zero. But a convention
   that is right for a six-car set with two cabs is not *proven* right for three
   repeated pairs with six, and I have not watched one run.
3. **Whether length 7 sits well beside pak128's length-8 stock** in a station.

The build is green, the `.dat`s lint clean against the engine's own schema, the
`.pak`s compile and `makeobj LIST` finds both vehicles inside the merged one. That is
all true and it is not a screenshot.
