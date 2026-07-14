"""Build a real, installable Simutrans vehicle from a Blender model.

    blender --background --python examples/demo_loco.py -- [pakset] [outdir]

This is the whole point of the kit in one file: model -> 8 renders -> sheet ->
.dat. Feed the result to makeobj and it is a .pak the game loads.

Defaults to pak64, because that is the pakset that ships with the engine repo.
"""

import os
import sys

import bpy

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from addon import rig                    # noqa: E402
from core import colors                  # noqa: E402

_argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
PAKSET = _argv[0] if _argv else "pak64"
OUT = _argv[1] if len(_argv) > 1 else os.path.join(_ROOT, "build", "demo")
BASENAME = "bkitloco"


def build_model():
    """A small diesel switcher. Nose points +X - the kit's model convention.

    Deliberately asymmetric front-to-back and left-to-right, so that a wrong
    heading is obvious the moment it runs on a track in-game.
    """
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)

    # hood (long, low) - the front of the loco
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0.30, 0, 0.40))
    hood = bpy.context.active_object
    hood.scale = (0.62, 0.46, 0.30)

    # cab (tall, at the back)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(-0.42, 0, 0.56))
    cab = bpy.context.active_object
    cab.scale = (0.38, 0.50, 0.46)

    # frame / running board
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.20))
    frame = bpy.context.active_object
    frame.scale = (1.05, 0.54, 0.10)

    # a player-colour band along the frame: in-game it takes the company colour
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.255))
    band = bpy.context.active_object
    band.scale = (1.06, 0.56, 0.05)
    band.data.materials.append(
        rig.make_special_color_material(bpy, colors.PLAYER_RAMP_BLUE[3])
    )

    return [hood, cab, frame, band]


def main():
    os.makedirs(OUT, exist_ok=True)
    build_model()  # render_directions builds the rig itself

    frames = rig.render_directions(bpy, OUT, PAKSET, dirs=8, basename=BASENAME)
    sheet_png, dat_path, placement = rig.build_sheet_and_dat(
        frames, OUT, PAKSET, basename=BASENAME, cols=4,
        name="BKit_Switcher", waytype="track",
        power=600, speed=90, weight=60, length=8,
        cost=800000, runningcost=800,
        intro_year=1900, engine_type="diesel",
    )

    print("\nsheet: %s" % sheet_png)
    print("dat:   %s" % dat_path)
    print("cells: %s" % placement)
    print("\nDEMO_OK")


main()
