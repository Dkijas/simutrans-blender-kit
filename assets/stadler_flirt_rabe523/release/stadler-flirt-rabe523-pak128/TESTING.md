# TESTING — Stadler FLIRT RABe 523 (SBB) for pak128, v0.1.0

Nothing below is claimed unless it was actually run.

## Environment

| item | value |
|---|---|
| Simutrans | 124.5.1 nightly (source `a5056d2f7`, r12109) |
| Backends | headless (`-DSIMUTRANS_BACKEND=none`) for the functional test; SDL2 windowed for the screenshots |
| pakset | pak128 (compiled testbed) |
| makeobj | 60.12 (Simutrans 124.5.1) |
| Blender | 5.1.2 |
| Simutrans Blender Kit | `769fc0b` |
| Platform | Windows 11, MSYS2/MINGW64 |

## Build / pipeline

| check | result |
|---|---|
| `build.py -- all` through the add-on | **FLIRT_OK** — 4 cars: Build Rig, Render Sheet, Compile .pak all ok |
| reserved-colour report per car | **0 accidental** reserved colours; window colour present on every car (188–234 px lit panes); head + tail lamps present on both cab cars |
| single combined release pak (`makeobj`) | 4 vehicles packed, 26 755 bytes, compiles clean |

## In-game (headless, pak128, real game)

Scenario `flirt523` lays electrified rail (straight + diagonal), hangs catenary,
builds a rail depot, and asks the **engine** — not the .dat — four things:

| check | result |
|---|---|
| cab car in the depot catalogue | **pass** |
| engine agrees it is electric (`needs_electrification()`) | **pass** |
| one depot click assembles **4 cars in order** [A, B, C, D] | **pass** (couplings chain) |
| the unit moves on pak128 rail under pak128 catenary | **pass** — moved (2,8) → (3,8) |
| **the single combined release `.pak`** re-run through the same scenario | **FLIRT523_OK** (the shipped artifact, not just the per-car paks) |

Sentinel: `FLIRT523_OK`.

## Eight directions / alignment

The screenshot run drove the unit through a straight run and a diagonal/curve; the
real captures (`screenshots/`) show the cars following the track including the
diagonal with no visible gap or overlap between the four equal-length cars, wheels
on the rail. The 8-direction sheets were also inspected per car off the render.

## Screenshots (real, in-game, pak128)

Captured in the SDL2 windowed build driving the **real product flow** via a
temporary, authorised `debug.take_screenshot()` / `debug.center_view()` hook, which
was afterwards **fully reverted, rebuilt and verified absent** from source
(`center_view` count 0, `api_control.cc` diff empty) and from the binary
(`center_view` count 0). Captures: `flirt_line`, `flirt_diagonal`, `flirt_depot`,
`flirt_station`, `flirt_forum_header` (UI trimmed; header cropped).

## Not tested / known gaps (honest)

- **Cost / capacity balance**: costs are provisional placeholders, not measured
  against pak128 stock yet.
- **Night lights, live**: the window/head/tail night-swap **colours are validated
  in the sprite**, but a live night screenshot was not captured — the engine
  day→night level is driven by the game clock and was not forced to night in the
  automated run. Toggle day/night in-game to see the lamps.
- **Info-window / depot-dialog screenshots**: those are GUI windows that the
  script API cannot open, so they are not auto-captured; open them manually on the
  running unit for the speed/power/capacity panel.
- **Double unit**: two full FLIRTs cannot be coupled (single-successor chain, by
  design), so no double-unit shot.
- **Save/load, bridges, tunnels**: not exercised in this pass; the unit is an
  ordinary fixed rail consist and uses no special mechanics, but this is stated as
  untested rather than claimed.
