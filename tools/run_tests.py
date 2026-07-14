"""One command, one verdict: core + Blender + the game.

    python tools/run_tests.py            everything
    python tools/run_tests.py core       just one suite
    python tools/run_tests.py --list

Why this exists
---------------
The three test surfaces had nothing in common but me remembering to run them.
Worse, the game side was verified by hand: launch the windowed game, sleep 20
seconds, grep a log file, then `taskkill /IM simutrans.exe`. Every one of those
steps is a lie waiting to happen - a sleep that is too short passes as a failure,
a grep that finds a stale log passes as a success, and killing by image NAME
kills the player's own game if they happen to have one open.

Simutrans' own runner (tools/run-automated-tests.sh) does roughly the same thing,
and is Linux-only besides (it polls /proc). So this one:

  * runs the game HEADLESS (built with -DSIMUTRANS_BACKEND=none, which compiles
    to COLOUR_DEPTH=0 and a null renderer - no window, no SDL),
  * reads its stdout as it comes instead of sleeping and grepping a file,
  * stops the moment there is a verdict, and kills by PID, never by name,
  * treats "no verdict before the timeout" as a FAILURE, not as a pass,
  * and returns a single exit code.

The game loops forever once a scenario has run, so killing it is not a hack: the
verdict is the terminating condition. There is nothing to wait for.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Overridable, because nobody else has my directory layout.
BLENDER = os.environ.get(
    "SIMUTRANS_BLENDER",
    r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe")
SIMUTRANS_SRC = os.environ.get(
    "SIMUTRANS_SRC", os.path.join(os.path.dirname(ROOT), "simutrans"))

HEADLESS = os.path.join(ROOT, "build", "sim-headless", "simutrans", "simutrans.exe")
GAME_BASE = os.path.join(SIMUTRANS_SRC, "simutrans")   # holds config/ and pak/
USERDIR = os.path.join(ROOT, "build", "sim-userdir")
MAKEOBJ = os.path.join(ROOT, "build", "tools", "makeobj.exe")

# The pak128 testbed: a real pakset and a game root of our own, both outside the
# game's repository. See assets/civia_465/README.md.
GAME128_BASE = os.path.join(ROOT, "build", "game")
USERDIR128 = os.path.join(ROOT, "build", "sim-userdir128")

# The scenarios are SOURCE. They used to exist only under build/, inside the
# throwaway user directories the game runs against - so a `rm -rf build`, the most
# ordinary thing anyone does to a build directory, silently deleted thirteen tests.
# They live here now and are copied in before each game suite.
SCENARIOS = os.path.join(ROOT, "tests", "scenarios")

# The engine's own distress signals, taken from tools/run-automated-tests.sh.
# Without these a broken script just... never prints its sentinel, and we would
# sit there until the timeout wondering why.
#
# _FAIL is OURS, and it is here because leaving it out cost three minutes of
# staring at nothing: a scenario that correctly decided the answer was NO printed
# BKITHOUSE_FAIL, which is not an engine error, so the runner kept waiting for an
# _OK that was never coming. A verdict of "no" is still a verdict.
GAME_FAILURES = (
    r"_FAIL\b",
    r"error \[Call function failed\] calling",
    r"error \[Reading / compiling script failed\] calling",
    r"</error>",
    r"FATAL ERROR",
)


class Result:
    def __init__(self, name, ok, detail="", seconds=0.0, skipped=False):
        self.name, self.ok, self.detail = name, ok, detail
        self.seconds, self.skipped = seconds, skipped


def _run(cmd, cwd, success, failures, timeout, name):
    """Run a process, watch its output, stop at the first verdict."""
    start = time.time()
    try:
        proc = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True,
                                bufsize=1, errors="replace")
    except OSError as e:
        return Result(name, False, "could not start: %s" % e)

    killer = threading.Timer(timeout, proc.kill)
    killer.start()

    verdict = None
    tail = []
    try:
        for line in proc.stdout:
            line = line.rstrip()
            tail.append(line)
            del tail[:-40]                       # keep the last 40 for the report
            if re.search(success, line):
                verdict = Result(name, True, line.strip())
                break
            if any(re.search(f, line) for f in failures):
                verdict = Result(name, False, line.strip())
                break
    finally:
        killer.cancel()
        proc.kill()          # it either finished or loops forever; either way, done
        proc.wait()

    if verdict is None:
        # No sentinel. NOT a pass - this is the failure mode a sleep-and-grep
        # runner silently turns into a green tick.
        detail = "no verdict within %ds. Last output:\n        %s" % (
            timeout, "\n        ".join(tail[-8:]) or "(nothing)")
        return Result(name, False, detail, time.time() - start)

    verdict.seconds = time.time() - start
    return verdict


def suite_core():
    return _run([sys.executable, os.path.join("tests", "test_core.py")], ROOT,
                r"\d+ checks passed", (r"^  FAIL", r"Traceback"), 120, "core")


def suite_schema():
    """Is our copy of the .dat schema still what the engine's writers say?"""
    r = _run([sys.executable, os.path.join("tests", "test_schema_drift.py"), SIMUTRANS_SRC],
             ROOT, r"\bSCHEMA_OK\b", (r"\bSCHEMA_FAILED\b", r"Traceback"), 120, "schema")
    if not r.ok and "SCHEMA_SKIP" in r.detail:
        r.skipped = True
    return r


def _blender(script, sentinel, extra=()):
    if not os.path.exists(BLENDER):
        return Result(script, False, "Blender not found at %s (set SIMUTRANS_BLENDER)"
                      % BLENDER, skipped=True)
    cmd = [BLENDER, "--background"] + list(extra) + \
          ["--python", os.path.join("tests", script)]
    return _run(cmd, ROOT, sentinel, (r"_FAILED", r"Traceback"), 900, script)


def suite_blender_e2e():
    return _blender("blender_e2e.py", r"\bE2E_OK\b")


def suite_blender_alignment():
    return _blender("blender_alignment.py", r"\bALIGN_OK\b")


def suite_blender_addon():
    # --factory-startup or the already-enabled add-on shadows the one we install
    return _blender("blender_addon.py", r"\bADDON_OK\b", extra=["--factory-startup"])


def _stage_scenarios(pakname, userdir):
    """Copy the scenarios from source into the user directory the game will read.

    Overwrites rather than merges: a scenario left behind from an older run is a
    test that passes for the wrong reason. Returns None, or a message.
    """
    src = os.path.join(SCENARIOS, pakname)
    if not os.path.isdir(src):
        return "no scenarios at %s" % src

    dst = os.path.join(userdir, "addons", pakname, "scenario")
    os.makedirs(dst, exist_ok=True)
    for entry in os.listdir(src):
        if os.path.isdir(os.path.join(src, entry)):
            target = os.path.join(dst, entry)
            shutil.rmtree(target, ignore_errors=True)
            shutil.copytree(os.path.join(src, entry), target)
    return None


def _game(scenario, sentinel, name):
    for path, what in ((HEADLESS, "headless simutrans (cmake -DSIMUTRANS_BACKEND=none"
                                  " --target simutrans)"),
                       (GAME_BASE, "the game's base dir (set SIMUTRANS_SRC)")):
        if not os.path.exists(path):
            return Result(name, False, "missing %s: %s" % (what, path), skipped=True)

    problem = _stage_scenarios("pak", USERDIR)
    if problem:
        return Result(name, False, problem)

    cmd = [HEADLESS, "-use_workdir", "-objects", "pak", "-addons",
           "-set_userdir", USERDIR, "-scenario", scenario, "-debug", "1"]
    return _run(cmd, GAME_BASE, sentinel, GAME_FAILURES, 180, name)


def suite_game_catalogue():
    """Is the generated vehicle actually in the engine's own depot list?"""
    return _game("bkitcheck", r"BKITCHECK_OK", "game:catalogue")


def suite_game_running():
    """Can it be bought, put on a rail, and driven?"""
    return _game("bkitdemo", r"BKITDEMO_OK", "game:running")


def suite_blender_building():
    """A building: sliced into height stacks, and the .dat lints clean."""
    # No r-prefix here once cost a red suite for no reason: in a plain Python
    # string "\bX\b" is not a word-boundary regex, it is a BACKSPACE, the text,
    # and another BACKSPACE - and it matches nothing. The sentinel is unique
    # enough on its own, so there is nothing to bound.
    return _blender("blender_building.py", "BUILDING_OK")


def suite_blender_footprint():
    """Does a building face its road, and does a 2x1 stay on its own plot?"""
    return _blender("blender_footprint.py", "FOOTPRINT_OK")


def suite_blender_way():
    """A way: six models turned into sixteen ribi images, checked pixel by pixel."""
    return _blender("blender_way.py", "WAY_OK")


def suite_game_house():
    """Can the generated house actually be planted on the map?"""
    return _game("bkithouse", r"BKITHOUSE_OK", "game:house")


def suite_blender_infra():
    """Catenary in two layers, and a signal whose state 0 is really red."""
    return _blender("blender_infra.py", "INFRA_OK")


def suite_game_road():
    """Can the generated road be laid, and does the engine agree on the ribis?"""
    return _game("bkitroad", r"BKITROAD_OK", "game:road")


def suite_game_infra():
    """Does the catenary electrify the rail, and can the signal be planted?"""
    return _game("bkitinfra", r"BKITINFRA_OK", "game:infra")


def suite_blender_panel():
    """Drive the PANEL itself - every object type, through bpy.ops, from the zip."""
    return _blender("blender_panel.py", "PANEL_OK", extra=("--factory-startup",))


def suite_demo_all():
    """One object of EVERY type, rendered in one Blender run."""
    return _blender("../examples/demo_all.py", "DEMO_ALL_OK")


def suite_game_all():
    """All five together in one game - and the ELECTRIC loco has to actually move."""
    return _game("bkitall", r"BKITALL_OK", "game:all")


def suite_civia():
    """The Civia S/465: sheets, clipping, reserved colours, couplings, .dat, .pak."""
    return _run([sys.executable,
                 os.path.join("assets", "civia_465", "tests", "test_civia465.py")],
                ROOT, r"\bCIVIA465_TESTS_OK\b",
                (r"CIVIA465_TESTS_FAILED", r"Traceback"), 300, "civia")


def _game128(scenario, sentinel, name):
    """The pak128 testbed: a real pakset, in a game root built OUTSIDE the repo.

    The other game suites run against the demo pak that ships with the source. An
    addon has to prove itself inside somebody else's pakset, so this one runs
    against pak128 proper, with our .pak in a user addons directory.
    """
    for path, what in ((HEADLESS, "headless simutrans"),
                       (GAME128_BASE, "the pak128 game root (see"
                                      " assets/civia_465/README.md)"),
                       (os.path.join(GAME128_BASE, "pak128"), "pak128 itself")):
        if not os.path.exists(path):
            return Result(name, False, "missing %s: %s" % (what, path), skipped=True)

    problem = _stage_scenarios("pak128", USERDIR128)
    if problem:
        return Result(name, False, problem)

    cmd = [HEADLESS, "-use_workdir", "-objects", "pak128", "-addons",
           "-set_userdir", USERDIR128, "-scenario", scenario, "-debug", "1"]
    return _run(cmd, GAME128_BASE, sentinel, GAME_FAILURES, 240, name)


def suite_game_civia():
    """One click on the cab car has to give five cars, in order, and they must run."""
    return _game128("civia465", r"CIVIA465_OK", "game:civia")


def suite_game_metro9k():
    """One click on the cab car has to give SIX cars, in order, and they must run."""
    return _game128("metro9k", r"METRO9K_OK", "game:metro9k")


def suite_game_metro9k_line():
    """The next question up: put it on a line with stations and does it WORK?"""
    return _game128("metro9kline", r"METRO9KLINE_OK", "game:metro9k-line")


SUITES = {
    "core": suite_core,
    "schema": suite_schema,
    "e2e": suite_blender_e2e,
    "alignment": suite_blender_alignment,
    "building": suite_blender_building,
    "footprint": suite_blender_footprint,
    "way": suite_blender_way,
    "infra": suite_blender_infra,
    "addon": suite_blender_addon,
    "panel": suite_blender_panel,
    "demo-all": suite_demo_all,
    "catalogue": suite_game_catalogue,
    "running": suite_game_running,
    "house": suite_game_house,
    "road": suite_game_road,
    "game-infra": suite_game_infra,
    "game-all": suite_game_all,
    "civia": suite_civia,
    "game-civia": suite_game_civia,
    "game-metro9k": suite_game_metro9k,
    "game-metro9k-line": suite_game_metro9k_line,
}
ORDER = ("core", "schema", "e2e", "alignment", "building", "footprint", "way",
         "infra", "addon", "panel", "demo-all", "catalogue", "running", "house",
         "road", "game-infra", "game-all", "civia", "game-civia",
         "game-metro9k", "game-metro9k-line")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("suites", nargs="*", help="default: all of them")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    if args.list:
        for name in ORDER:
            print("  %-12s %s" % (name, SUITES[name].__doc__ or ""))
        return 0

    chosen = args.suites or ORDER
    unknown = [s for s in chosen if s not in SUITES]
    if unknown:
        print("unknown suite(s): %s (try --list)" % ", ".join(unknown))
        return 2

    results = []
    for name in chosen:
        print("--> %s" % name, flush=True)
        r = SUITES[name]()
        r.name = name                    # report by suite name, not by script file
        results.append(r)
        mark = "SKIP" if r.skipped else ("ok" if r.ok else "FAIL")
        print("    %-4s %5.1fs  %s\n" % (mark, r.seconds, r.detail), flush=True)

    print("=" * 64)
    failed = [r for r in results if not r.ok and not r.skipped]
    skipped = [r for r in results if r.skipped]
    for r in results:
        print("  %-4s %-14s %5.1fs"
              % ("SKIP" if r.skipped else ("ok" if r.ok else "FAIL"),
                 r.name, r.seconds))

    # A skip is not a pass. If a suite could not run, say so and fail - a runner
    # that quietly skips the only test of a subsystem is worse than no runner.
    if skipped:
        print("\n%d suite(s) COULD NOT RUN - that is not a pass:" % len(skipped))
        for r in skipped:
            print("  %s: %s" % (r.name, r.detail))
    if failed:
        print("\nFAILED: %s" % ", ".join(r.name for r in failed))

    ok = not failed and not skipped
    print("\n%s" % ("ALL GREEN" if ok else "NOT GREEN"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
