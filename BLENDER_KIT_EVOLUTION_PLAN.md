# Blender Kit — Evolution Plan (QA toolchain)

Status: **DRAFT / not started**. This document is mandatory before any code
change and is the contract the phases are checked against. It supersedes any
verbal scope: if a phase drifts from here, this file is updated first.

## 0. Prime directive & guardrails (non-negotiable)

- **No vehicle-specific logic in `core/`.** Nothing about the FLIRT, a MAGLEV,
  SBB liveries, or any single asset may live in a shared module. Asset facts stay
  under `assets/<name>/`. The QA reads *declarations*, never hard-codes a subject.
- **Backward compatibility is preserved.** Every existing entry point keeps its
  signature and behaviour: `core.scenecheck.check`, `core.colors.scan/classify`,
  `core.directions.*`, `tools/lint_dat.py`, `addon/*` operators, the panel. New
  behaviour is additive and opt-in; a scene that passed before still passes.
- **Pure core, thin Blender shell.** New logic goes in `core/` as pure functions
  over plain data (the `scenecheck.Scene` pattern). `addon/*_blender.py` only
  adapts `bpy` → plain data. A rule that needs Blender to test is a rule tested
  once — forbidden.
- **Zero false positives on shipped pak128 art is the acceptance bar** for any
  new ERROR-level rule, exactly as `README`/`scenecheck` already promise. When a
  rule cannot tell *wrong* from *unusual*, it is a WARNING, never an ERROR.
- **No secrets, no tokens, ever** — not in code, config, logs, reports, tests or
  history. `.gitignore` already covers `.env`, `.venv`, `__pycache__`, paksets,
  Makeobj, `.blend1`.
- **Every phase ends at a checkpoint**: tests green, `run_tests.py` clean, a
  one-paragraph handoff, and an explicit go/no-go before the next phase.

## 1. Gap analysis (what already exists — do NOT rebuild)

| Capability | Home today | Verdict |
|---|---|---|
| Scene audit (3 levels, pure) | `core/scenecheck.py` | Mature — **extend** |
| Reserved/special-colour scan | `core/colors.py` | Mature — **extend** |
| 8-direction azimuth model | `core/directions.py` | Mature — reuse |
| Alignment probes | `tests/blender_alignment.py`, scenecheck geom | Partial — **extend** |
| Portable `.dat` linter | `tools/lint_dat.py`, `build_standalone_linter.py` | Partial — **extend** |
| Consist assembly/validation | `core/consists.py`, `core/convoy.py` | Mature — reuse |
| Pakset profiles | `core/paksets.py` | Mature — reuse |
| Test runner | `tools/run_tests.py` | Mature — reuse |
| CI | `.github/workflows/tests.yml` | Mature — extend |

**The real, uncovered gaps** (this is what the evolution actually delivers):

1. **Diagonal foreshortening is unvalidated.** `scenecheck` checks the modelled
   X-span against declared `length` on the *straight* axis only. The FLIRT failed
   on **diagonals**, where the sprite is foreshortened and neighbouring cars gap.
   Nothing measures a rendered sheet direction-by-direction.
2. **No cross-direction comparison.** `directions.py` knows the azimuths but no
   tool checks that the eight rendered cells are mutually consistent (silhouette
   width per heading, footprint centre drift, a car facing the wrong way).
3. **No consist-level preview/validation from an asset spec.** `consists.py`
   validates coupling rules; nothing renders/checks a whole unit's cars *together*
   for alignment before packaging.
4. **No single Quality Gate** that runs scene-audit + colour-scan + alignment +
   direction-comparison + dat-lint and returns one PASS/FAIL with a report.
5. **No machine-readable report** an agent (me) can consume programmatically.

## 2. Phased plan (with mandatory checkpoints)

### Phase 1 — Direction-consistency analysis on rendered sheets  ← START HERE
Closes gap 2 (cross-direction consistency) with checks the measured data proves
robust across every good asset. **Scope corrected after measuring real sheets:**
the FLIRT cars are all `length=8` (equal), so by `convoy.py`'s engine-verified
model their joints butt by construction — the earlier "diagonal gap" was an
UNCERTAIN diagnosis (the 20 px end-on silhouette it blamed is identical in the
clean Civia). Judging joint/gap needs declared length + the whole consist, so it
moves to **Phase 3**; Phase 1 does not fabricate a rule on a shaky premise.
- `core/spritemetrics.py` (new, pure): given a decoded sheet (`sheet.read_png`
  pixels — stdlib, no Pillow), compute per-direction opaque bbox, coverage, mass
  centroid, and left/right reach. Mirrors `colors.scan`: caller passes pixels.
- `core/directioncheck.py` (new, pure): rules the data supports with wide margin —
  `missing-direction` (expected cell empty → ERROR), `facing-order` (broadside
  sw/ne must be widest, end-on se/nw narrowest, else model faces wrong / cells
  misordered → WARNING), `opposite-mismatch` (opposite pairs must match in size →
  WARNING), `off-centre` (centroid X off tile centre, lenient so asymmetric cabs
  pass → WARNING), `coverage` (per-direction metrics → INFORMATION). Reuses
  `directions.py`; Findings are `scenecheck.Finding` so the Gate composes cleanly.
- `tools/analyze_sheet.py` (new): CLI over `core.sheet` + the two modules; `--json`.
- Tests: `tests/test_spritemetrics.py`, `tests/test_directioncheck.py` (pure).
  Each rule tested on a synthetic sheet that trips it AND one that must not
  (the repo's two-sided convention), plus the real Civia sheet to prove zero
  false positives.
- **Checkpoint 1**: new tests green; `run_tests.py` clean; analyzer runs clean on
  the clean Civia/Metro sheets AND flags an injected fault (a mis-ordered sheet).
  Re-run it on the FLIRT sheet to REPLACE the uncertain diagnosis with real
  numbers (report, don't pre-judge). Handoff + go/no-go.

### Phase 2 — Advanced special-colour validation
Extends `core/colors.py` without breaking `scan/classify`.
- Near-miss detection (a pixel 1–2 away from a reserved colour — the "window one
  count off" trap the module's own docstring describes), region clustering (where
  on the sprite), and a per-cell breakdown. Additive helpers; existing API frozen.
- `tools/analyze_sheet.py` gains `--colours`. Tests extend `test_core`/new file.
- **Checkpoint 2**.

### Phase 3 — Consist preview & validation from a spec
- `core/consistcheck.py` (new, pure): given a list of car specs + their sheet
  metrics, validate joint continuity (straight butt + diagonal spacing) across the
  whole unit, reusing Phase 1 metrics and `consists.py` coupling rules.
- **Checkpoint 3**.

### Phase 4 — Quality Gate + machine-readable report
- `core/qualitygate.py` (new, pure): compose scene-audit + colour + direction +
  consist + dat-lint into one result; severity roll-up; stable finding codes.
- `tools/quality_gate.py` (new): CLI over an `assets/<name>/` dir → PASS/FAIL,
  `--json` report, non-zero exit on ERROR (usable in CI and by me directly).
- **Checkpoint 4**.

### Phase 5 — QA UI, logging, diagnostics, docs, CI
- Optional panel button surfacing the gate inside Blender (thin shell only).
- Structured logging (no secrets), `docs/quality-gate.md`, extend
  `.github/workflows/tests.yml` to run the gate on a fixture asset.
- **Checkpoint 5** — final handoff.

## 3. Manifest contract for Sprite Studio (defined here, built in Phase 4)

The independent Sprite Studio consumes, not reimplements, this Kit's rules. The
Quality Gate emits a versioned JSON manifest describing: reserved-colour table
identity, 8-direction cell mapping, per-direction expected silhouette class, and
declared length. Sprite Studio validates foreign/non-Blender sheets against the
*same* contract. The manifest schema lives beside `qualitygate.py` and is the
single source of truth both tools agree on. **No shared code across repos** — a
documented, versioned data contract only.

## 4. Out of scope

- No FLIRT redo here (done later, *through* this gate).
- No new render pipeline; we analyse what `rig.py` already renders.
- No aesthetic judgements; the checker never calls art ugly.

## 5. Definition of done

All five checkpoints passed; every existing test still green; a shipped-pak128
vehicle passes the gate with zero findings; the FLIRT v0.1 sheet is flagged with
the diagonal-gap finding that motivated this work; docs updated; CI runs the gate.
