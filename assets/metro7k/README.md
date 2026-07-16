# Madrid Metro serie 7000 — pak128 example asset

**Author:** victor_18993
**Licence:** CC BY 4.0 for the original 3D work — see `LICENSE.md`. The licence
covers our modelling, not Metro de Madrid's marks or AnsaldoBreda/Pininfarina's
industrial design, which the model merely depicts.

A six-car Madrid Metro serie 7000 for pak128. It is the 9000's older sibling and
shares its carbody, so the two assets are near-twins by design, not by laziness:
the documented exterior difference is the **red upper door band**, which the 9000
recoloured blue. It is painted in code, so it lands on all six cars.

## Composition

    CabA → R1 → M1 → M2 → R2 → CabB          (Mc-R-M-M-R-Mc)

Each car has exactly one possible predecessor and one possible successor, so one
click on the cab car in a depot assembles the whole unit. No car can be bought
alone: only `CabA` may lead, only `CabB` may trail, and neither may do both.

| car | role | power | weight | seats |
|---|---|---|---|---|
| CabA / CabB | Mc (cab, motored, pantograph) | 792 kW | 37 t | 28 |
| R1 / R2 | R (trailer) | 0 | 28 t | 31 |
| M1 / M2 | M (motored) | 792 kW | 35 t | 30 |
| **unit** | | **3168 kW** | **200 t** | **178** |

## What is measured, and what is not

Every figure in `spec.json` carries its `kind` and its source, and `tools/spec.py`
refuses a number whose source is missing or is a word like "guess" or "chatgpt".
The per-car table above is in there too, not in the Python: `car_totals` names the
fact each column must add up to, and a split that does not sum to its sourced total
refuses to load. That check exists because the 9000 shipped one that summed to 186
against a measured 178 back when these numbers were typed in the module.

**Measured** (es.wikipedia.org "Series 7000 y 9000"; vialibre-ffe.com's 7000 ficha):
speed 110 km/h, cab car 17.09 m, intermediates 16.88 m, width 2.8 m, height
3.65 m, floor 1.125 m, 4 doors/side of 1.3 m, 1500 Vcc, capacity 1260, in service
2002, 30 units built.

**Derived** (formula recorded): power 3168 kW = 198 kW × 16; length 8 carunits.

**Provisional — guesses, and they say so:**
- `weight_total_t` = 200 t. Nobody publishes the mass.
- `cost`, `runningcost` — balance figures, set slightly below the 9000.
- `payload_seated` = 178. The 7000's seated/standing split is not published on
  its own; 178 is the family figure. The `.dat` payload carries the **seated**
  number only, which is why the game shows 178 and not 1260.

**Contested and recorded as such:** the motor count. Wikipedia says "198 kW × 8 or
16"; vialibre-ffe's ficha says "total 8 motores". We use 16 (3168 kW) to match the
9000, and `spec.json` records the disagreement.

**Assumed, and NOT confirmed — read this before trusting the model:**
- the **blue nose**, and
- the **pantograph position** (placed on the cab cars, as on the 9000).

The sources name only the doors and the interior roof as the differences between
the two series, so the rest is *taken* to be shared. Nobody has checked either
against a photograph of a 7000. **There is no 7000 reference photograph in this
repository** — unlike `assets/metro9k/references/`, this folder has none. The
livery layout was read off photographs seen elsewhere and not kept. Until someone
puts a 7000 photo next to this model, treat the front colour and the pantograph as
open questions.

## Building it

    blender --background --factory-startup --python assets/metro7k/blender/build.py -- all

That is the whole thing: it builds the add-on zip from source, installs it, drives
the add-on's own panel operators (rig → sheet → makeobj), and writes `dat/`,
`pak/`, `sprites/` and `textures/`. Build one car instead of six with `-- cab_a`
(the prototype runs without couplings on purpose — a constraint pointing at a car
that does not exist yet is a dangling reference).

Prints `METRO7K_OK`, or `METRO7K_FAILED: <checks>` and exits 1. The checks are not
decoration: they fail the build on accidental reserved colours, on windows or
lamps that are not the engine's exact light colours, and on a per-car split that
does not sum to the sourced total.

Merge the six into one distributable pak — **list the files, never hand makeobj a
directory**, or it writes a 69-byte empty pak and says nothing:

    cd assets/metro7k/pak
    makeobj MERGE MadridMetroS7000.pak s7k_cab_a.pak s7k_rem_a.pak s7k_mot_a.pak \
                                       s7k_mot_b.pak s7k_rem_b.pak s7k_cab_b.pak

## Tests

The build's own checks run on every build (above). Beyond that, this asset is
**not yet wired into `tools/run_tests.py`** — there is no `asset-metro7k` suite
and no pak128 scenario of its own, unlike `civia_465` and `metro9k`. That is a
known gap, not a claim of coverage.

The 7000 has been run in a real game: a six-car unit worked a metro line through a
bored tunnel, calling at two subway platforms and reversing, electrified
throughout. That test lives in the pak128 testbed scenario `metro7kline`, outside
this repository.

## Known limitations

- No reference photograph here; nose colour and pantograph unconfirmed (above).
- The per-car splits of power, weight and payload are *our* arithmetic over the
  sourced totals — AnsaldoBreda publishes no per-car breakdown of anything. They
  live in `spec.json`'s `cars` array, and `car_totals` makes each column add up to
  the fact it names or the spec refuses to load, so a wrong split cannot build.
  What the check cannot tell you is whether the split is the *right* one: it only
  knows it sums correctly.
- `reports/` and `renders/` are empty: `build.py` creates them and never writes
  them. Inherited from the asset this one was copied from.
- The `.blend` files are outputs, not inputs — the geometry is procedural and
  every build overwrites them.
