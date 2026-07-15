"""A building, end to end, inside Blender.

    blender --background --python tests/blender_building.py

A vehicle is one sprite per heading; a building is a GRID - footprint tiles x
height slices - and the interesting failure is the stacking. So build a tower
that is deliberately several cells tall and check that:

  * it comes out as more than one height slice (a one-slice "tower" means the
    stacking never happened and the roof is simply missing in game),
  * every slice is exactly one cell,
  * the slices are CONTIGUOUS from h=0 up (the engine stops at the first missing
    height, so a hole silently decapitates the building),
  * the .dat lints clean against the engine's own schema.

Prints BUILDING_OK on success.
"""

import os
import sys

import bpy

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from addon import rig                                    # noqa: E402
from core import buildings, colors, factories, paksets, schema, sheet  # noqa: E402

OUT = os.path.join(_ROOT, "build", "house")
PAKSET = "pak128"
FAILED = []


def check(name, cond, detail=""):
    if cond:
        print("  ok   %s" % name)
    else:
        print("  FAIL %s  %s" % (name, detail))
        FAILED.append(name)


SNOW = "SNOW_CAP"
LAMP = "PORCH_LAMP"


def season_setup(bpy_, season):
    """Put the snow on for the snow image, take it off for the rest.

    With TWO images the second is the SNOW image - NOT "winter". The engine only
    reaches for it above the snowline or in an arctic climate
    (obj/gebaeude.cc); in a temperate December it still draws image 0.
    """
    snow = bpy_.data.objects.get(SNOW)
    if snow is not None:
        snow.hide_render = (season != buildings.SEASON_AUTUMN)   # index 1 = snow


def phase_setup(bpy_, phase):
    """A porch lamp that blinks. The engine cycles the phases every
    animation_time ms - and starts each building on a RANDOM one
    (obj/gebaeude.cc: anim_frame = sim_async_rand(phases)), so a street of these
    does not blink in unison."""
    lamp = bpy_.data.objects.get(LAMP)
    if lamp is not None:
        lamp.hide_render = (phase == 0)


def build_tower():
    """A 1x1 house, clearly taller than one cell, with a player-colour band."""
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)

    # tile_world is 2.0, so a tile is 2 units across. Make it ~3 units tall:
    # that is comfortably more than one cell and must produce several slices.
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 1.5))
    body = bpy.context.active_object
    body.scale = (1.6, 1.6, 3.0)

    bpy.ops.mesh.primitive_cone_add(radius1=1.2, depth=1.0, location=(0, 0, 3.5))

    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.35))
    band = bpy.context.active_object
    band.scale = (1.65, 1.65, 0.2)
    band.data.materials.append(
        rig.make_special_color_material(bpy, colors.PLAYER_RAMP_BLUE[3]))

    # a snow cap, hidden except in the snow image
    bpy.ops.mesh.primitive_cone_add(radius1=1.35, depth=0.5, location=(0, 0, 4.05))
    cap = bpy.context.active_object
    cap.name = SNOW
    cap.hide_render = True

    # a beacon that is only there on phase 1. It sits on the ROOF RIDGE, not on a
    # corner: a corner lamp disappears behind the house in half the layouts, and
    # then "the animation does nothing" is true - just not for the reason you
    # think. (It took a red test to notice.)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.3, location=(0, 0, 4.5))
    lamp = bpy.context.active_object
    lamp.name = LAMP
    lamp.hide_render = True


def main():
    pak = paksets.get(PAKSET)
    build_tower()

    frames = rig.render_building(bpy, OUT, PAKSET, basename="bkithouse",
                                 size_x=1, size_y=1, layouts=4,
                                 seasons=2, season_setup=season_setup,
                                 phases=2, phase_setup=phase_setup)
    keys = [k for k, _p in frames]
    print("       images: %d %s" % (len(keys), keys[:4]))

    check("all four layouts rendered", sorted({k[0] for k in keys}) == [0, 1, 2, 3],
          str(sorted({k[0] for k in keys})))
    check("the tower needed more than one height slice per layout",
          len([k for k in keys if k[0] == 0]) > 1,
          "the stacking did not happen")

    # contiguity is per (layout, season): the engine walks h upward inside ONE
    # image list and stops at the first gap
    for layout in range(4):
        for season in range(2):
            for phase in range(2):
                hs = sorted(k[3] for k in keys if k[0] == layout
                            and k[4] == phase and k[5] == season)
                check("layout %d phase %d season %d: heights contiguous"
                      % (layout, phase, season),
                      hs == list(range(len(hs))), str(hs))

    # the animation must actually animate
    for L in range(4):
        p0 = sheet.read_png(dict(frames)[(L, 0, 0, 1, 0, 0)])[3]
        p1 = sheet.read_png(dict(frames)[(L, 0, 0, 1, 1, 0)])[3]
        check("layout %d: phase 1 really differs from phase 0" % L, p0 != p1,
              "identical - phase_setup did nothing")

    # the four layouts are the same house turned; if the rotation were a no-op we
    # would be shipping four identical images and every house would face one way
    ground = {L: sheet.read_png(dict(frames)[(L, 0, 0, 0, 0, 0)])[3] for L in range(4)}
    check("the layouts are actually different images",
          len({tuple(v) for v in ground.values()}) == 4,
          "some layouts rendered identically - the model is not turning")

    # season 1 is the SNOW image; if it came out identical to season 0 the whole
    # season pass did nothing and the artist would never know
    for L in range(4):
        summer = sheet.read_png(dict(frames)[(L, 0, 0, 1, 0, 0)])[3]
        snow = sheet.read_png(dict(frames)[(L, 0, 0, 1, 0, 1)])[3]
        check("layout %d: the snow image really differs from the all-year one" % L,
              summer != snow, "identical - season_setup did nothing")

    for key, path in frames:
        w, h, alpha, _px = sheet.read_png(path)
        check("slice %s is one cell (%dx%d RGBA)" % (key, pak.tile_px, pak.tile_px),
              (w, h) == (pak.tile_px, pak.tile_px) and alpha, "%dx%d" % (w, h))

    # the ground slice must not be empty: that is the one the engine always draws
    _w, _h, _a, px0 = sheet.read_png(dict(frames)[(0, 0, 0, 0, 0, 0)])
    check("the ground slice has pixels", any(p[3] for p in px0))

    sheet_png = os.path.join(OUT, "bkithouse.png")
    placement = sheet.assemble(frames, pak.tile_px, cols=4, out_path=sheet_png)
    block = buildings.image_block("bkithouse", placement)
    dat = buildings.building_dat("BKit_House", block, btype="res", dims="1,1,4",
                                 level=3,
                                 animation_time=buildings.DEFAULT_ANIMATION_TIME_MS)
    dat_path = os.path.join(OUT, "bkithouse.dat")
    with open(dat_path, "w", encoding="utf-8") as f:
        f.write(dat)

    check("dat is a building", "obj=building" in dat)
    check("dat uses the six-index (season) form",
          "BackImage[0][0][0][0][0][0]=" in dat, dat)
    check("dat carries a stacked image", "BackImage[0][0][0][1][0][0]=" in dat, dat)
    check("dat carries every layout",
          all(("BackImage[%d][0][0][0][0][0]=" % L) in dat for L in range(4)), dat)
    check("dat carries the snow image",
          "BackImage[0][0][0][0][0][1]=" in dat, dat)
    check("dat carries the second animation phase",
          "BackImage[0][0][0][0][1][0]=" in dat, dat)
    check("dat sets animation_time", "animation_time=300" in dat, dat)

    findings = schema.lint(dat)
    for f in findings:
        print("       %s" % f)
    check("the .dat lints clean against the engine schema", not findings,
          "%d finding(s)" % len(findings))

    # the player-colour band must have survived the render, as it does for vehicles
    _sw, _sh, salpha, spx = sheet.read_png(sheet_png)
    rgb = [(p[0], p[1], p[2]) for p in spx if not (salpha and p[3] == 0)]
    check("the player-colour band survived", bool(colors.scan(rgb)),
          "no reserved colour in the sheet")

    # --- the same sprites, written as a STATION STOP for the game to try to build.
    # A stop is just a building with a type and a waytype - and an icon, without
    # which hausbauer.cc:235 gives it no builder and the game offers it to nobody.
    stop_png = os.path.join(OUT, "bkitstop.png")
    stop_place = sheet.assemble(frames, pak.tile_px, cols=4, out_path=stop_png)
    stop_dat = buildings.building_dat(
        "BKit_Stop", buildings.image_block("bkitstop", stop_place),
        btype="stop", dims="1,1,4", level=2, waytype="track",
        enables=["pax", "post"],
        icon=buildings.icon_ref("bkitstop", stop_place),
        animation_time=buildings.DEFAULT_ANIMATION_TIME_MS)
    stop_path = os.path.join(OUT, "bkitstop.dat")
    with open(stop_path, "w", encoding="utf-8") as f:
        f.write(stop_dat)
    check("stop dat is a stop with a waytype",
          "type=stop" in stop_dat and "waytype=track" in stop_dat, stop_dat)
    check("stop dat carries an icon, or the game will not build it",
          "\nicon=" in stop_dat, stop_dat)
    check("stop dat lints clean", not schema.lint(stop_dat),
          str(schema.lint(stop_dat)))

    # --- the same sprites, written as a FACTORY for the game to load. A factory
    # is a building plus economics (factory_writer.cc embeds the building); it
    # needs the mandatory mapcolor and a good that resolves at load.
    fac_png = os.path.join(OUT, "bkitfactory.png")
    fac_place = sheet.assemble(frames, pak.tile_px, cols=4, out_path=fac_png)
    fac_dat = factories.factory_dat(
        "BKit_Mine", buildings.image_block("bkitfactory", fac_place),
        mapcolor=42, dims="1,1", level=1, location="Land", productivity=20,
        outputs=[("Kohle", 40, 100)])
    fac_path = os.path.join(OUT, "bkitfactory.dat")
    with open(fac_path, "w", encoding="utf-8") as f:
        f.write(fac_dat)
    check("factory dat is an obj=factory with a mapcolor and a product",
          "obj=factory" in fac_dat and "mapcolor=42" in fac_dat
          and "outputgood[0]=Kohle" in fac_dat, fac_dat)
    check("factory dat lints clean", not schema.lint(fac_dat),
          str(schema.lint(fac_dat)))

    print("\nsheet: %s\ndat:   %s" % (sheet_png, dat_path))
    if FAILED:
        print("\nBUILDING_FAILED: %s" % ", ".join(FAILED))
        sys.exit(1)
    print("\nBUILDING_OK")


main()
