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
sys.path.insert(0, ROOT)

from core import paksets                      # noqa: E402  (stdlib only, no bpy)
from tools import toolchain                   # noqa: E402

# Found, not assumed. Every one of these used to be a Windows literal, and the
# Blender one named a specific VERSION - so the suite broke on Linux, on macOS,
# and on the next Windows machine to install a newer Blender. Each honours an
# environment variable, because nobody else has this directory layout.
BLENDER = toolchain.find_blender()
MAKEOBJ = toolchain.find_makeobj(ROOT)
HEADLESS = toolchain.find_headless(ROOT)

SIMUTRANS_SRC = os.environ.get(
    "SIMUTRANS_SRC", os.path.join(os.path.dirname(ROOT), "simutrans"))
GAME_BASE = os.path.join(SIMUTRANS_SRC, "simutrans")   # holds config/ and pak/
USERDIR = os.path.join(ROOT, "build", "sim-userdir")

# The pak128 testbed: a real pakset and a game root of our own, both outside the
# game's repository. See assets/civia_465/README.md.
GAME128_BASE = os.path.join(ROOT, "build", "game")
USERDIR128 = os.path.join(ROOT, "build", "sim-userdir128")

# The scenarios are SOURCE. They used to exist only under build/, inside the
# throwaway user directories the game runs against - so a `rm -rf build`, the most
# ordinary thing anyone does to a build directory, silently deleted thirteen tests.
# They live here now and are copied in before each game suite.
SCENARIOS = os.path.join(ROOT, "tests", "scenarios")

ADDONS = os.path.join(USERDIR, "addons", "pak")
ADDONS128 = os.path.join(USERDIR128, "addons", "pak128")

# THE LOOP.
#
# Every object a game scenario asks for, and the .dat this run rendered it from.
#
# Until this table existed there was no path at all from a render to a .pak the
# game loads. The .pak files in the addons directories had been copied there by
# hand, once; the Blender suites wrote their .dat and sheets into build/<dir>/ and
# stopped. So a full run could be ALL GREEN against art that was a day old, and a
# regression in the renderer could not turn a single game suite red.
#
# It was not hypothetical. A stale CiviaS465.pak sat in the pak128 addons folder
# declaring the same object names as the freshly built civia465_*.pak beside it,
# and nothing said which one the engine answered with.
#
#     (.dat, relative to build/) (pakset makeobj is told) (name it installs as)
PAK_BUILDS = (
    (("demo", "bkitloco.dat"),      "pak64",  "bkitloco.pak"),
    (("house", "bkithouse.dat"),    "pak128", "bkithouse.pak"),
    (("house", "bkitstop.dat"),     "pak128", "bkitstop.pak"),
    (("house", "bkitfactory.dat"),  "pak128", "bkitfactory.pak"),
    (("freight", "bkithopper.dat"), "pak128", "bkithopper.pak"),
    (("tunnel", "bkittunnel.dat"),  "pak128", "bkittunnel.pak"),
    (("bridge", "bkitbridge.dat"),  "pak128", "bkitbridge.pak"),
    (("way", "bkitroad.dat"),       "pak128", "bkitroad.pak"),
    (("infra", "bkitwire.dat"),     "pak128", "bkitwire.pak"),
    (("infra", "bkitsignal.dat"),   "pak128", "bkitsignal.pak"),
    (("demo_all", "bkloco.dat"),    "pak64",  "bkall_bkloco.pak"),
    (("demo_all", "bkhouse.dat"),   "pak64",  "bkall_bkhouse.pak"),
    (("demo_all", "bkroad.dat"),    "pak64",  "bkall_bkroad.pak"),
    (("demo_all", "bksignal.dat"),  "pak64",  "bkall_bksignal.pak"),
    (("demo_all", "bkwire.dat"),    "pak64",  "bkall_bkwire.pak"),
)

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


def suite_templates():
    """The object templates: do they name what the renderer actually reads?"""
    return _run([sys.executable, os.path.join("tests", "test_templates.py")], ROOT,
                "TEMPLATE_TESTS_OK", ("TEMPLATE_TESTS_FAILED", "Traceback"), 120,
                "templates")


def suite_colours():
    """Does makeobj really recognise the colours we tell the artist to paint?"""
    r = _run([sys.executable, os.path.join("tests", "test_colours_makeobj.py")], ROOT,
             "COLOURS_OK", ("COLOURS_FAILED", "Traceback"), 300, "colours")
    if not r.ok and "COLOURS_SKIP" in r.detail:
        r.skipped = True
    return r


def suite_schema():
    """Is our copy of the .dat schema still what the engine's writers say?"""
    r = _run([sys.executable, os.path.join("tests", "test_schema_drift.py"), SIMUTRANS_SRC],
             ROOT, r"\bSCHEMA_OK\b", (r"\bSCHEMA_FAILED\b", r"Traceback"), 120, "schema")
    if not r.ok and "SCHEMA_SKIP" in r.detail:
        r.skipped = True
    return r


def suite_profile():
    """Does each pakset profile match the real pakset's own simuconf.tab?"""
    r = _run([sys.executable, os.path.join("tests", "test_pakset_profile.py")],
             ROOT, r"\bPROFILE_OK\b", (r"\bPROFILE_FAILED\b", r"Traceback"), 120,
             "profile")
    if not r.ok and "PROFILE_SKIP" in r.detail:
        r.skipped = True
    return r


def _blender(script, sentinel, extra=(), script_args=()):
    if not BLENDER:
        return Result(script, False, "no Blender found (put it on PATH, or set"
                      " SIMUTRANS_BLENDER)", skipped=True)
    cmd = [BLENDER, "--background"] + list(extra) + \
          ["--python", os.path.join("tests", script)]
    if script_args:
        cmd += ["--"] + list(script_args)    # Blender passes these on to the script
    return _run(cmd, ROOT, sentinel, (r"_FAILED", r"Traceback"), 900, script)


def suite_blender_e2e():
    return _blender("blender_e2e.py", r"\bE2E_OK\b")


def suite_blender_alignment():
    return _blender("blender_alignment.py", r"\bALIGN_OK\b")


def suite_blender_addon():
    # --factory-startup or the already-enabled add-on shadows the one we install
    return _blender("blender_addon.py", r"\bADDON_OK\b", extra=["--factory-startup"])


def suite_demo_loco():
    """The switcher the first two game suites actually ask for, rendered here."""
    return _blender("../examples/demo_loco.py", "DEMO_OK")


def suite_asset_civia():
    """The Civia S/465, built through the add-on's own buttons. Installs its .pak."""
    return _blender("../assets/civia_465/blender/build.py", "CIVIA465_OK",
                    extra=("--factory-startup",), script_args=("all",))


def suite_asset_metro9k():
    """The Metro 9000, likewise. Installs its .pak into the pak128 addons dir."""
    return _blender("../assets/metro9k/blender/build.py", "METRO9K_OK",
                    extra=("--factory-startup",), script_args=("all",))


def suite_paks():
    """Compile the .pak the game suites load, from the art THIS RUN rendered.

    Wipes first. A .pak left behind by an earlier run is an object the engine will
    load without comment, and a scenario that passes on yesterday's art is not a
    test of today's code.

    makeobj returning zero is not the proof - it exits zero on plenty of things
    that will not load. The proof is the game suites that come after this one.
    """
    start = time.time()
    if not MAKEOBJ:
        return Result("paks", False, "no makeobj found. Build it from the Simutrans"
                      " source (cmake --build <dir> --target makeobj), put it on"
                      " PATH, or set SIMUTRANS_MAKEOBJ")

    wiped = 0
    for addons in (ADDONS, ADDONS128):
        os.makedirs(addons, exist_ok=True)
        for entry in os.listdir(addons):
            if entry.endswith(".pak"):
                os.remove(os.path.join(addons, entry))
                wiped += 1

    for parts, pakset, installed in PAK_BUILDS:
        dat = os.path.join(ROOT, "build", *parts)
        if not os.path.exists(dat):
            return Result("paks", False, "no %s - did its producer suite run?"
                          % os.path.join(*parts), time.time() - start)

        out = os.path.dirname(dat)
        pak = os.path.splitext(dat)[0] + ".pak"
        # in the .dat's own directory: its image references are relative to it
        proc = subprocess.run(
            [MAKEOBJ, paksets.get(pakset).makeobj_arg,
             os.path.basename(pak), os.path.basename(dat)],
            cwd=out, capture_output=True, text=True, errors="replace")

        if proc.returncode != 0 or not os.path.exists(pak) or not os.path.getsize(pak):
            tail = (proc.stdout + proc.stderr).strip().splitlines()
            return Result("paks", False, "makeobj failed on %s: %s"
                          % (os.path.join(*parts),
                             tail[-1] if tail else "exit %d" % proc.returncode),
                          time.time() - start)

        shutil.copy2(pak, os.path.join(ADDONS, installed))

    return Result("paks", True, "wiped %d stale, built %d from this run's art"
                  % (wiped, len(PAK_BUILDS)), time.time() - start)


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
    if not HEADLESS:
        return Result(name, False, "no headless simutrans (cmake"
                      " -DSIMUTRANS_BACKEND=none --target simutrans, or set"
                      " SIMUTRANS_HEADLESS)", skipped=True)
    if not os.path.exists(GAME_BASE):
        return Result(name, False, "missing the game's base dir (set SIMUTRANS_SRC):"
                      " %s" % GAME_BASE, skipped=True)

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


def suite_blender_freight():
    """Cargo variants: empty vs loaded sheets must differ, pixel for pixel."""
    return _blender("blender_freight.py", "FREIGHT_OK")


def suite_blender_tunnel():
    """A tunnel portal: four turned directions in two layers, back and front."""
    return _blender("blender_tunnel.py", "TUNNEL_OK")


def suite_blender_bridge():
    """A bridge: span, start, ramp and pillar, each turned, in two layers."""
    return _blender("blender_bridge.py", "BRIDGE_OK")


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
    if not HEADLESS:
        return Result(name, False, "no headless simutrans (set SIMUTRANS_HEADLESS)",
                      skipped=True)
    for path, what in ((GAME128_BASE, "the pak128 game root (see"
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


def suite_game_hopper():
    """A cargo-variant wagon loads and its freightimagetype goods really resolve."""
    return _game("bkithopper", r"BKITHOPPER_OK", "game:hopper")


def suite_game_tunnel():
    """The generated tunnel loads and is in the engine's own tunnel builder list."""
    return _game("bkittunnel", r"BKITTUNNEL_OK", "game:tunnel")


def suite_game_stop():
    """The generated station stop loads and, icon and all, is buildable."""
    return _game("bkitstop", r"BKITSTOP_OK", "game:stop")


def suite_game_bridge():
    """The generated bridge loads and is in the engine's own bridge builder list."""
    return _game("bkitbridge", r"BKITBRIDGE_OK", "game:bridge")


def suite_game_factory():
    """The generated factory loads with its good resolved, in the factory table."""
    return _game("bkitfactory", r"BKITFACTORY_OK", "game:factory")


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
    "templates": suite_templates,
    "schema": suite_schema,
    "colours": suite_colours,
    "profile": suite_profile,
    "e2e": suite_blender_e2e,
    "alignment": suite_blender_alignment,
    "building": suite_blender_building,
    "footprint": suite_blender_footprint,
    "way": suite_blender_way,
    "freight": suite_blender_freight,
    "tunnel": suite_blender_tunnel,
    "bridge": suite_blender_bridge,
    "infra": suite_blender_infra,
    "addon": suite_blender_addon,
    "panel": suite_blender_panel,
    "demo-all": suite_demo_all,
    "demo-loco": suite_demo_loco,
    "paks": suite_paks,
    "asset-civia": suite_asset_civia,
    "asset-metro9k": suite_asset_metro9k,
    "catalogue": suite_game_catalogue,
    "running": suite_game_running,
    "hopper": suite_game_hopper,
    "tunnel-game": suite_game_tunnel,
    "stop": suite_game_stop,
    "bridge-game": suite_game_bridge,
    "factory-game": suite_game_factory,
    "house": suite_game_house,
    "road": suite_game_road,
    "game-infra": suite_game_infra,
    "game-all": suite_game_all,
    "civia": suite_civia,
    "game-civia": suite_game_civia,
    "game-metro9k": suite_game_metro9k,
    "game-metro9k-line": suite_game_metro9k_line,
}
# Producers first, then the .pak they feed, then the game. The order IS the loop:
# nothing downstream of "paks" can pass on art that this run did not render.
ORDER = ("core", "templates", "schema", "colours", "profile",
         # producers: the art and the .dat
         "e2e", "alignment", "building", "footprint", "way", "freight", "tunnel",
         "bridge", "infra", "addon", "panel", "demo-all", "demo-loco",
         # the .pak the game will load, compiled from what was just rendered
         "paks",
         # the game, against the demo pakset
         "catalogue", "running", "hopper", "tunnel-game", "stop", "bridge-game",
         "factory-game", "house", "road", "game-infra", "game-all",
         # the game, against a real pakset - these build and install their own
         "asset-civia", "civia", "asset-metro9k",
         "game-civia", "game-metro9k", "game-metro9k-line")


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
