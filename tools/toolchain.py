"""Finding the programs the test harness shells out to, on whatever machine it is.

There is no Simutrans knowledge in here. It exists because every path in the
harness was written as a Windows literal:

    build/tools/makeobj.exe
    build/sim-headless/simutrans/simutrans.exe
    C:\\Program Files\\Blender Foundation\\Blender 5.1\\blender.exe

so on Linux or macOS the suite could not compile a .pak, could not run the game,
and could not find Blender - and the last one names a specific Blender VERSION,
so it also breaks on the next Windows machine that installs 5.2.

Deliberately harness-only: it lives in tools/ and is not packed into the add-on.
The panel already asks the artist to browse to makeobj, which works everywhere.

Every lookup can be overridden by an environment variable, because nobody else
has this directory layout.
"""

import os
import shutil


def exe(name):
    """`makeobj` on Linux and macOS, `makeobj.exe` on Windows."""
    return name + ".exe" if os.name == "nt" else name


def _first_file(*paths):
    for path in paths:
        if path and os.path.isfile(path):
            return path
    return None


def find_makeobj(root):
    """The makeobj binary, or None.

    Looked for in the kit's own build directory, then in the Simutrans source
    tree beside it (which is where it is actually built from), then on PATH.
    """
    override = os.environ.get("SIMUTRANS_MAKEOBJ")
    if override:
        return override if os.path.isfile(override) else None

    name = exe("makeobj")
    game = os.environ.get("SIMUTRANS_SRC", os.path.join(os.path.dirname(root), "simutrans"))
    return _first_file(
        os.path.join(root, "build", "tools", name),
        os.path.join(game, "build", "tools", name),
        os.path.join(game, "build", name),
    ) or shutil.which(name)


def find_headless(root):
    """The headless Simutrans built with -DSIMUTRANS_BACKEND=none, or None."""
    override = os.environ.get("SIMUTRANS_HEADLESS")
    if override:
        return override if os.path.isfile(override) else None

    name = exe("simutrans")
    return _first_file(
        os.path.join(root, "build", "sim-headless", "simutrans", name),
        os.path.join(root, "build", "sim-headless", name),
    )


def find_blender():
    """Blender, or None. PATH first - a version pinned in a path always rots."""
    override = os.environ.get("SIMUTRANS_BLENDER")
    if override:
        return override if os.path.isfile(override) else None

    found = shutil.which(exe("blender"))
    if found:
        return found

    # Windows and macOS installers do not put it on PATH. Newest version wins.
    roots = (r"C:\Program Files\Blender Foundation",
             "/Applications/Blender.app/Contents/MacOS")
    best = None
    for base in roots:
        if not os.path.isdir(base):
            continue
        if os.path.isfile(os.path.join(base, "Blender")):
            return os.path.join(base, "Blender")         # macOS
        for entry in sorted(os.listdir(base), reverse=True):
            candidate = os.path.join(base, entry, exe("blender"))
            if os.path.isfile(candidate):
                best = best or candidate
    return best
