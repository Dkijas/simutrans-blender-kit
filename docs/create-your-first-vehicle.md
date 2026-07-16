# Create your first vehicle

No Simutrans experience assumed. At the end of it the game sells your train and
drives it.

You need Blender 4.2 or newer, and the add-on installed — *Preferences → Add-ons →
Install from Disk*, pick `simutrans_blender_kit.zip`, then press **N** in the 3D
view and choose the **Simutrans** tab.

Nine steps. The first eight happen without leaving Blender.

---

## 1. Create the template

In the **Start** box, pick your pakset (**pak128** unless you know otherwise) and
leave **Object** on *Vehicle*. Press **Create Template**.

You get a collection called `SIMUTRANS_GUIDES` holding three things:

| Guide | What it tells you |
|---|---|
| `SIMUTRANS_tile` | one tile, at ground level. Your model stands **on** this |
| `SIMUTRANS_nose_+X` | the nose points **+X**. Everything depends on this |
| `SIMUTRANS_length` | how long you *said* the vehicle is. Fill it |

They are **empties**. They never render, and they are not part of your model — the
kit measures your work without them getting in the way. You can hide the whole
collection with one click when they are in the way of *you*.

A vehicle needs no collections at all: the renderer photographs whatever is in the
scene, so organise your body and bogies however you like. **The guides are the
template.** What people get wrong on a vehicle is the direction, the origin and the
length — not the outliner.

Then press **Build Rig**, which adds the camera and the sun. Do not move them.

## 2. Load your references

Optional, and worth it if you are modelling something real.

Open **Reference photos**, pick an image from your disk, say which view it is
(*Side*, *Front* or *Top*), and type the **real size in metres** — length, width,
height, from the vehicle's spec sheet.

Press **Place Reference**. The photo lands where the model goes, at the right size.

That last part is the point. Turning metres into Blender units is where people who
have not read the pakset documentation go wrong, and nothing tells them: a bus
modelled 20% too large is just a slightly wrong bus, all the way into the game.
Type the real numbers and the scaling is done for you.

**Metres per tile** is a default, not a law. The engine has no metres at all —
nothing in its source fixes one. 40 is roughly what pak128 does. Change it if your
pakset disagrees.

## 3. Model

Three rules, and the guides show all three:

* **stand on `z = 0`** — the model sits on the tile, it does not hover over it;
* **centre it on the world origin**;
* **point the nose along `+X`**.

Get those right and the sprite comes out sitting on the rail with no fiddling.
Get them wrong and everything still renders — a clean sheet, a valid `.dat`, a
`.pak` that compiles, and a train that flies or faces backwards. That is why
step 6 exists.

Fill the length guide. Not because the sprite gets scaled — it does not — but
because `length` is what the engine uses to space the **next** car. A model that
does not match its declared length opens a gap in the train, and you will not see
it until the unit is coupled in a depot.

## 4. Assign the materials

In the **Materials** box, pick one, select your objects and press **Apply to
selected**.

These are not ordinary colours. Simutrans **reserves** particular RGB values and
repaints them in the game:

| Material | What the game does with it |
|---|---|
| **Player colour** | repainted in each company's colours |
| **Window (warm)** | dark by day, lit yellow at night |
| **Headlight** | white by day, yellow after dark |
| **Red lamp** | a tail light, day and night |
| **Plain paint** | an ordinary colour. Nothing special happens |

A reserved colour must survive the render **exactly** — the engine matches the
value, not something near it. The kit handles that (it forces the right view
transform, disables dithering, and pre-corrects the colour), but only for
materials made by this button. Paint a player-colour blue by hand and it will
arrive at the game as an ordinary blue, and the game will simply not recolour it.

## 5. Fill in the numbers

Open **Object (.dat)**. Give it at least a **Name** and an **Author**.

The ones that matter for a first train:

* **Waytype** `track`, **Engine** `electric` or `diesel`
* **Speed** in km/h, **Power** in kW (`0` makes it an unpowered wagon)
* **Weight** in tonnes, **Length** in 1/16 of a tile (`8` is half a tile)
* **Freight** `Passagiere` for passengers, **Payload** how many

Leave the rest at their defaults until you have a reason.

## 6. Validate

Press **Validate**, in the **Output** box. This is the cheap step, and it is the
one that tells you whether rendering is worth it.

It reports three kinds of thing:

* **ERROR** — the render cannot produce a correct object. Fix it.
* **WARNING** — it will render, and it is probably not what you meant.
* **INFORMATION** — a measurement. Not a judgement.

A warning does not stop you, and it is not a criticism of your art. If it says
your model is 1.4 tiles long, that is a fact you may have chosen.

The one to read carefully is **length-mismatch**: you declared one length and
modelled another. There is nowhere in Blender that mistake is visible.

## 7. Render

Set **Output** to a folder. If you use the default `//simutrans` you must save the
`.blend` first — `//` means "next to the .blend", and until you save there is no
`.blend` to be next to. Validate will tell you this.

Press **Render Sheet**. It renders the eight headings, assembles the sprite sheet
and writes the `.dat`.

Then press **Check Colours** — it scans the finished sheet and tells you which
reserved colours actually survived. And **Night Preview**, which shows the sheet as
the game draws it after dark. If it says *nothing lights up*, no pixel carries a
light colour, and your train runs dark all night. Better to know now.

Changed your mind about the power or the cost? Press **Write .dat**, not Render
Sheet. It rewrites the `.dat` from the render you already paid for.

## 8. Compile

You need **makeobj**, which ships with nothing. Build it once from the Simutrans
source:

```
cmake --build <builddir> --target makeobj
```

Point the panel at it, press **Compile .pak**.

## 9. Install

Give the panel an **Install to** folder — normally a pakset's `addons/` — and
*Compile .pak* copies it there. Start the game with `-addons`.

Your train is in the depot list.

---

## When it goes wrong

| What you see | What it is |
|---|---|
| The train faces backwards on the diagonals | the nose is not along `+X` |
| It floats, or is buried | the model is not on `z = 0` |
| The train has gaps between cars | the model does not match its declared `length` |
| Company colours do nothing | the blue is not the exact reserved value — use the Materials button |
| Nothing lights up at night | no pixel carries a light colour |
| The `.pak` compiles and the game refuses to start | almost always an end-of-line comment in a hand-edited `.dat`. `#` is only a comment at the **start** of a line |

The first three are caught by **Validate**, before you render. The fourth by
**Check Colours** and the fifth by **Night Preview**, after. The last one the kit
never writes — but if you hand-edit the `.dat`, `python tools/lint_dat.py yours.dat`
will find it.

## Where to go next

* A vehicle longer than a tile is **not one big sprite** — one image is capped at
  one tile. It is a **convoy of coupled cars**, each its own `.pak` with its own
  `length`. See `assets/civia_465/` for a real five-car unit.
* `Object` in the Start box has seven more entries: buildings, ways, catenary,
  signals, tunnels, bridges and factories. Each has its own template, and each one
  makes the collections it needs — press **Create Template** and read the panel.
* The [README](../README.md) explains *why* each convention is what it is, and
  every one of them is traced to a line of the engine's own source.
