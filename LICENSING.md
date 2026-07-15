# Licensing

## The code: MIT

Everything under `core/`, `addon/`, `tools/`, `tests/` and `examples/` is MIT.
Take it, change it, ship it in something closed, sell it. No attribution burden
beyond keeping the notice.

### Why MIT and not GPL, given that this is a Blender add-on

`addon/` imports `bpy`, and the Blender Foundation treats code that does so as a
derivative work of Blender, which is GPL. That constrains what this project may
be distributed under: the licence has to be **GPL-compatible**.

It does not force the licence to *be* the GPL. MIT is GPL-compatible in the
direction that matters — MIT code can be combined into a GPL work — so an MIT
add-on satisfies the constraint while leaving users free to reuse the code
anywhere, which is the point. The combined thing you run inside Blender is
effectively GPL; the source you take from this repository is MIT.

Two things worth knowing rather than discovering later:

* This is the common reading and there are MIT-licensed Blender add-ons in the
  wild. It is not a court ruling, and nobody here is a lawyer. If you would
  rather have no ambiguity at all, the fix is one line: `addon/` becomes
  GPL-2.0-or-later and everything else stays MIT.

* **`core/` and `tools/` do not import `bpy` at all.** The projection maths, the
  night-lighting arithmetic, the `.dat` schema and the linter — a little over
  half the codebase — are plain Python with no Blender dependency, so the
  question above does not touch them. They are MIT, unambiguously, and they are
  the parts most worth reusing.

`makeobj` is invoked as a subprocess, not linked, so it imposes nothing.

## The example assets: CC BY 4.0, with a trademark note

`assets/civia_465/` and `assets/metro9k/` are 3D models of a **Renfe Civia 465**
and a **Madrid Metro serie 9000**, modelled by **victor_18993**.

The **original work** — the geometry, the textures, and the `.blend` files — is
licensed **CC BY 4.0** (Creative Commons Attribution 4.0 International,
<https://creativecommons.org/licenses/by/4.0/>). You may use, modify and
redistribute it, including commercially, as long as you credit the modeller. Each
of the two folders carries its own `LICENSE.md` with the exact attribution line.

**What the licence does not cover.** These models wear the names, liveries and
shapes of two real operators' trains. A licence grants rights to *our* work; it
cannot grant rights to third-party trademarks or industrial designs. "Renfe",
"Civia", "Metro de Madrid", "serie 9000", and the operators' liveries and marks,
belong to their respective owners and appear here only to depict the real vehicles.
**The CC BY 4.0 grant applies solely to the original 3D modelling work; it makes no
claim over, and grants no rights in, those trademarks or designs.** If you reuse
the models, that third-party layer travels with them and is your responsibility.

`assets/_template/` is ours, invented, and carries no such baggage; it is MIT with
the rest of the repository.

The reference photographs the models were built from are **not in this
repository** (see `.gitignore`). They are third-party photographs; we do not own
them and cannot relicense them.

## What this means if you contribute a pakset object

The kit writes `copyright=` into every `.dat` it generates. Today it writes the
name of the *tool*, which is wrong — the art is yours and should say so. That is
tracked and will change.
