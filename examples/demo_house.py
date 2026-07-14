"""A real, installable city building from a Blender model.

    blender --background --python examples/demo_house.py -- [pakset] [outdir]

The building counterpart of demo_loco.py. Same model convention (standing on
z = 0, over the world origin); the difference is that a building is cut into
height slices rather than rendered once per heading.
"""

import os
import sys

import bpy

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from addon import rig                        # noqa: E402
from core import buildings, colors, paksets, schema, sheet   # noqa: E402

_argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
PAKSET = _argv[0] if _argv else "pak64"
OUT = _argv[1] if len(_argv) > 1 else os.path.join(_ROOT, "build", "demo_house")
BASENAME = "bkithouse"


SNOW = "SNOW_CAP"
BEACON = "ROOF_BEACON"


def season_setup(bpy_, season):
    """Season 1 is the SNOW image - not 'winter'. The engine only draws it above
    the snowline or in an arctic climate (obj/gebaeude.cc effective_season)."""
    cap = bpy_.data.objects.get(SNOW)
    if cap is not None:
        cap.hide_render = (season != 1)


def phase_setup(bpy_, phase):
    """A roof beacon that blinks. The engine starts each building on a RANDOM
    phase (obj/gebaeude.cc), so a street of these does not blink in unison.

    Note it sits on the ridge, not on a corner: a corner light vanishes behind
    the house in half the layouts, and then the animation "does nothing" for
    reasons that have nothing to do with the animation.
    """
    b = bpy_.data.objects.get(BEACON)
    if b is not None:
        b.hide_render = (phase == 0)


def build_model():
    """A narrow three-storey townhouse: taller than one cell, so it must stack."""
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)

    # a tile is 2 Blender units across; this is ~3.4 units tall
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 1.4))
    body = bpy.context.active_object
    body.scale = (1.5, 1.5, 2.8)

    # a pitched roof, so the top slice is unmistakably not just more wall
    bpy.ops.mesh.primitive_cone_add(radius1=1.15, radius2=0, depth=1.2,
                                    location=(0, 0, 3.4), vertices=4,
                                    rotation=(0, 0, 0.785398))

    # a porch on +Y: the FACADE. The kit's convention is that this side faces the
    # road in layout 0, so a wrong rotation shows up immediately as a house whose
    # front door points at the neighbour's garden.
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 1.5, 0.5))
    porch = bpy.context.active_object
    porch.scale = (0.8, 0.5, 1.0)

    # snow on the roof, hidden except in the snow image
    bpy.ops.mesh.primitive_cone_add(radius1=1.25, radius2=0, depth=1.3,
                                    location=(0, 0, 3.45), vertices=4,
                                    rotation=(0, 0, 0.785398))
    cap = bpy.context.active_object
    cap.name = SNOW
    cap.hide_render = True

    # a beacon on the ridge, only on phase 1
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.28, location=(0, 0, 4.15))
    beacon = bpy.context.active_object
    beacon.name = BEACON
    beacon.hide_render = True

    # a band that takes the company colour in game
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.30))
    band = bpy.context.active_object
    band.scale = (1.55, 1.55, 0.18)
    band.data.materials.append(
        rig.make_special_color_material(bpy, colors.PLAYER_RAMP_BLUE[3]))


def main():
    os.makedirs(OUT, exist_ok=True)
    pak = paksets.get(PAKSET)
    build_model()

    frames = rig.render_building(bpy, OUT, PAKSET, basename=BASENAME,
                                 size_x=1, size_y=1, layouts=4,
                                 seasons=2, season_setup=season_setup,
                                 phases=2, phase_setup=phase_setup)

    sheet_png = os.path.join(OUT, "%s.png" % BASENAME)
    placement = sheet.assemble(frames, pak.tile_px, cols=4, out_path=sheet_png)
    block = buildings.image_block(BASENAME, placement)
    dat = buildings.building_dat("BKit_House", block, btype="res", dims="1,1,4",
                                 level=3, chance=100,
                                 animation_time=buildings.DEFAULT_ANIMATION_TIME_MS)
    dat_path = os.path.join(OUT, "%s.dat" % BASENAME)
    with open(dat_path, "w", encoding="utf-8") as f:
        f.write(dat)

    findings = schema.lint(dat)
    for f in findings:
        print("LINT %s" % f)

    print("\nheight slices: %d" % len(frames))
    print("sheet: %s" % sheet_png)
    print("dat:   %s" % dat_path)
    print("\nDEMO_HOUSE_OK" if not findings else "\nDEMO_HOUSE_LINT_FAILED")


main()
