# Stadler FLIRT RABe 523 (SBB) — pak128 addon, v0.1.0

A four-car electric multiple unit for **pak128**, based visually on the SBB
RABe 523 (first-generation Stadler FLIRT). Built end-to-end with the
[Simutrans Blender Kit](https://github.com/Dkijas/simutrans-blender-kit): the 3D
model, eight-direction sprites, sprite sheets, `.dat` files and the compiled `.pak`
all come from the kit's own operators.

First test release — feedback welcome.

## Install

Copy `SBB_FLIRT_RABe523.pak` into your pak128 add-on folder:

- Windows: `Documents\Simutrans\addons\pak128\`
- Linux/macOS: `~/.simutrans/addons/pak128/` (or `~/simutrans/addons/pak128/`)

Then start Simutrans with pak128 and add-ons enabled. The unit appears in a rail
depot on electrified track from **2004**.

## The unit

Fixed four-car formation, assembled from a **single depot click** on the cab car
(a single-successor coupling chain walks the whole unit):

| # | internal name | role | power | weight | capacity |
|---|---|---|---:|---:|---:|
| 1 | `SBB_FLIRT_RABe523_A` | cab car A | 1000 kW | 34 t | 42 |
| 2 | `SBB_FLIRT_RABe523_B` | intermediate B | — | 26 t | 50 |
| 3 | `SBB_FLIRT_RABe523_C` | intermediate C (pantograph) | — | 26 t | 50 |
| 4 | `SBB_FLIRT_RABe523_D` | cab car D | 1000 kW | 34 t | 42 |
| | **unit** | | **2000 kW** | **120 t** | **184** |

- `waytype = track`, `engine_type = electric`, **160 km/h**, intro **2004**.
- Runs only under catenary. The coupling constraints make an invalid consist
  (an intermediate at the head, wrong order, a foreign vehicle inside) impossible.
- **Cost / running cost are provisional** — a placeholder to be balanced against
  pak128's own 2004–2010 EMUs. See `TESTING.md`.

## Livery

SBB scheme, painted in code (no photographic textures): white body, **red doors**,
red cab front around a large dark windscreen, light-grey lower band, grey roof, a
discreet SBB mark, folded pantograph on car C. Window glow and head/tail lamps use
the engine's own night-swap colours (validated by the kit's reserved-colour report).

## Contents

- `SBB_FLIRT_RABe523.pak` — the compiled add-on (all four cars).
- `dat/` — the four generated `.dat` files.
- `sprites/` — the four sprite sheets (8 directions each).
- `blender/` — the Blender project (`.blend` per car) plus the source that built
  them (`flirt.py`, `build.py`, `spec.json`).
- `textures/` — the code-painted livery textures + light masks.
- `screenshots/` — real in-game captures on pak128.
- `SHA256SUMS.txt`, `INVENTORY.md`, `BUILDING.md`, `TESTING.md`, `CHANGELOG.md`,
  `LICENSE.txt`, `REFERENCES.md`.

## Regenerating

The whole thing rebuilds from a clean checkout through the add-on — see
`BUILDING.md`.

## Authorship / licence

Model, livery and data by **victor_18993**, built with the Simutrans Blender Kit
(MIT). See `LICENSE.txt`. Photographs referenced for proportions only; no
third-party textures are included.
