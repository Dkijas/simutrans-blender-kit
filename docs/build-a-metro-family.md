# Build a metro family

Three vehicles, two liveries, two formations, one package. No Simutrans experience
assumed — but read [Create your first vehicle](create-your-first-vehicle.md) first
if you have never taken one model all the way through.

What you end up with:

```
Metro series
├── Cab car          the ends
├── Motor car        the powered middle
├── Trailer car      the unpowered middle
├── Original livery
├── Renovated livery
├── 4-car formation
├── 6-car formation
├── An 8-direction preview
└── A package you can send someone
```

---

## 1. The three vehicles

A metro unit is **not one long sprite**. One image is capped at one tile, so a
six-car train is six separate objects, each with its own `.pak`. That is not a
limitation of the kit — it is how the engine draws trains.

So: three `.blend` files, one per car. For each one, in the **Start** box, pick
**pak128** and **Vehicle**, then press **Create Template** and **Build Rig**.

Model each car standing on `z = 0`, centred on the origin, **nose along +X**. The
guides show all three. Fill the length guide — declare `length=16` for a full-tile
car and model to it, or the train gaps.

Name them so you can tell them apart later: `Metro_CabA`, `Metro_Mot`,
`Metro_Trl`, `Metro_CabB`. Names go straight into the `.dat` and every rule below
refers to them, so no spaces and no `#`.

## 2. Add the components

Open **Components** and press **Refresh**. Five ship with the kit:

| Key | What it is |
|---|---|
| `wheelset` | two 0.92 m wheels on an axle, standard gauge |
| `bogie_2axle` | a short passenger bogie, 2.5 m wheelbase |
| `pantograph_single` | folded to ~4 m, where pak128's contact wire runs |
| `headlight_round` | a 0.25 m lamp facing +X |
| `coupler_centre` | a centre coupler at UIC height |

Type a key into **Component**, choose **Copy in**, press **Insert Component**.

Each lands at its own anchor, at the right size. A bogie arrives sitting on the
rail because its anchor says so — you do not do the arithmetic.

**Copy in / Link / Instance** are not the same thing:

* **Copy in** — a real copy. Yours forever, renders anywhere, including on the
  machine of whoever you send the project to.
* **Link** — the component's `.blend` stays the master. Fix it once, every project
  updates. But the file must still be there at render time, and it will not be for
  anyone you send this to.
* **Instance** — one mesh, many copies. Cheap for eight bogies.

Give the headlight's lens the **Headlight** material (in the **Materials** box) and
it lights up after dark. Do not paint it by hand: the engine matches the reserved
colour *exactly*, and a hand-picked near-miss is just paint.

## 3. Two liveries

There are **no liveries in Simutrans**. Not "unsupported here" — the concept does
not exist in the engine. A green car and a renovated car are **two objects**, with
two names and two `.dat` files.

That is exactly what **Variants** makes. Open it and you will see it say so.

For the original livery: type `Metro_Mot_Orig` into **Variant name**, put `Body`
(or whatever your body material is called) into **Repaint**, pick the colour, press
**Add Variant**. Then the same for `Metro_Mot_Renov` in the renovated colour.

Press **Show in viewport** to look at one. **This really repaints your scene** —
Blender has no other way to assign a material, so the kit does not pretend
otherwise. The panel turns red and tells you which variant is on, with a **Back to
base** button. *Render All Variants* puts the scene back on its own.

## 4. Two formations

Open **Consists**. This is where the work disappears.

A formation is not an engine object either — the engine has vehicles and pairwise
coupling rules. What you are describing is the train you *intend*, and the kit
turns it into those rules.

**The 4-car set.** Type `Metro_4car`, press **Add Consist**. Then, for each car:
type its name into **Vehicle**, pick where it **Goes**, press **Add Vehicle**.

| Vehicle | Goes |
|---|---|
| `Metro_CabA` | Front only |
| `Metro_Mot` | Anywhere |
| `Metro_Trl` | Anywhere |
| `Metro_CabB` | Back only |

**The 6-car set.** `Add Consist` again, named `Metro_6car`:
`CabA, Trl, Mot, Mot, Trl, CabB`.

**Middle only** is worth knowing about. It means the car may never be at either
end — not "anywhere", the opposite. Use it for a car with no cab and no coupler at
one end.

**At least / At most** make a section repeatable: `At least 2, At most 6` says
"between two and six of these", and the kit remembers that such a car must be
allowed to couple **to itself**. That one catches people out — forget it and your
"2 to 6 middle cars" builds exactly one.

## 5. Check the constraints

Press **Check Consists**. It refuses formations the game could never build: one
that nothing may lead, one where a car must be at the front in one set and never
at the front in another (it is one object — it cannot be both).

Then press **Show Constraints**. It prints what it worked out, and **writes
nothing**:

```
Metro_CabA: Prev=none Next=Metro_Mot, Metro_Trl
Metro_Mot:  Prev=Metro_CabA, Metro_Mot, Metro_Trl Next=Metro_Mot, Metro_Trl
```

Look at `Metro_Mot`. It accepts the cab **and** the trailer **and itself** —
because it sits behind the cab in the 4-car set, behind a trailer in the 6-car set,
and next to another motor car in the 6-car set. That union, across formations, per
vehicle, is what you would otherwise be doing by hand.

Miss one of those and the game does not complain. It just refuses to let you build
that train in the depot, and never says why.

Then, in each car's own `.blend`, press **Apply to this vehicle**. It fills the two
constraint fields for *that* object.

## 6. Preview all eight

Press **Preview All 8**. You get one labelled page with every heading on it.

This is not a preview of the render — it **is** the render, of eight headings, put
on one page afterwards. Same camera, same sun, same everything, because it calls
the same two functions the final render is made of. What you see is what the game
gets.

The order is `s w sw se n e ne nw` and it is not compass order. That is the order
the engine reads images in, and your sheet is laid out in it, so the page is
labelled rather than reordered.

Look for: a car that runs off its cell, a heading facing the wrong way, a window
that is not a reserved colour. If the panel says the preview is out of date, it is
— something moved since.

## 7. Render, compile, install

**Render All Variants** does every livery, each to its own sheet and `.dat`, and
puts your scene back the way it was.

Then **Compile .pak** (point it at `makeobj`), and give it your pakset's `addons/`
folder to install into.

Start the game with `-addons` and your metro is in the depot. Build the 4-car set;
the couplings will let you, and they will refuse the trains you did not describe.

## 8. Package it

Open **Publish**. Fill in **Version** and **Licence** — a licence is not optional,
and the panel says so in red until you type one. Without it nobody may legally ship
your work and most paksets will not take it.

Press **Build Package**. You get a zip with the `.dat` files, the sprites, your
licence and a manifest listing every file, its checksum, and whether it is
*generated* (rebuildable output) or *authored* (your work — the thing the licence
covers).

It refuses to build if something is missing, it leaves out `.blend1` backups and
caches and tells you it did, and **it uploads nothing**. It makes a file. Sending
it is your decision.

---

## When it goes wrong

| What you see | What it is |
|---|---|
| A car may not be at the front, and you meant it to | it is *middle only* somewhere — `any` means "never at an end" |
| The depot will not build your 6-car set | a vehicle is missing a neighbour: run **Show Constraints** and read the union |
| Your "2 to 6 coaches" builds exactly one | the coach cannot couple to itself: set **At most** above 1 |
| The train has gaps | a car's model does not match its declared `length` — **Validate** says so |
| The scene is painted the wrong colour after rendering | it should not be. That is a bug — *Render All Variants* restores it, and reports it if it cannot |
| Company colours do nothing | the blue is not the exact reserved value — use the Materials button |

## Where the rules come from

Nothing in this tutorial is convention. Every coupling rule is derived from
`can_follow` in the engine's own `vehicle_desc.h`, and
[docs/constraints-in-simutrans.md](constraints-in-simutrans.md) shows the table it
comes from — including why `any` means the opposite of what it sounds like.
