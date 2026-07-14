"""Drive the PANEL, for every kind of object, the way an artist would.

    blender --background --factory-startup --python tests/blender_panel.py

tests/blender_addon.py checks that the add-on installs and registers. This one
checks that it WORKS: it sets the panel's properties and calls the operators, for
all five object types, and then reads the .dat that came out.

The distinction matters. The kit's Python API has been exercised from the start,
but until now nothing ever went through bpy.ops - and the panel is the only part
most people will ever touch. A tutorial that says "press the button" is only true
if somebody has pressed the button.

Prints PANEL_OK on success.
"""

import os
import sys

import bpy

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

OUT = os.path.join(_ROOT, "build", "panel")
FAILED = []


def check(name, cond, detail=""):
    if cond:
        print("  ok   %s" % name)
    else:
        print("  FAIL %s  %s" % (name, detail))
        FAILED.append(name)


def install_the_addon():
    """Install and enable it exactly as the tutorial tells people to."""
    zip_path = os.path.join(_ROOT, "build", "simutrans_blender_kit.zip")
    if not os.path.exists(zip_path):
        raise SystemExit("no add-on zip at %s - run tools/build_addon_zip.py"
                         % zip_path)
    bpy.ops.preferences.addon_install(filepath=zip_path, overwrite=True)
    bpy.ops.preferences.addon_enable(module="simutrans_blender_kit")

    # Read the sheets back with the INSTALLED code, not the checkout's: the whole
    # point of this suite is that what we ship is what we tested.
    global colors, night, rig, sheet
    from simutrans_blender_kit.addon import rig
    from simutrans_blender_kit.core import colors, night, sheet


def clear():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for col in list(bpy.data.collections):
        bpy.data.collections.remove(col)


def cube(x=0.0, y=0.0, z=0.5, sx=0.6, sy=0.6, sz=0.5, collection=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, z))
    ob = bpy.context.active_object
    ob.scale = (sx, sy, sz)
    if collection is not None:
        bpy.context.scene.collection.objects.unlink(ob)
        collection.objects.link(ob)
    return ob


def new_collection(name):
    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)
    return col


def render(props, basename):
    """Press the buttons. Actually press them."""
    props.basename = basename
    props.out_dir = OUT
    bpy.ops.simutrans.build_rig()
    return bpy.ops.simutrans.render_sheet()


def dat_of(basename):
    path = os.path.join(OUT, "%s.dat" % basename)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return f.read()


def main():
    install_the_addon()
    os.makedirs(OUT, exist_ok=True)
    p = bpy.context.scene.simutrans
    p.pakset = "pak64"

    # --- vehicle
    clear()
    cube(sx=1.0, sy=0.4, sz=0.3)
    p.obj_type = "vehicle"
    p.obj_name = "Panel_Loco"
    p.waytype = "track"
    p.engine_type = "electric"
    p.power = 500
    check("the panel renders a vehicle", render(p, "pvehicle") == {"FINISHED"})
    dat = dat_of("pvehicle")
    check("...and writes a vehicle .dat", dat and "obj=vehicle" in dat)
    check("...with all eight headings",
          dat and all(("EmptyImage[%s]=" % d) in dat
                      for d in ("s", "w", "sw", "se", "n", "e", "ne", "nw")), dat)
    # An EMPTY constraint field must write NO constraint at all. Writing `none`
    # instead would mean "nothing may go in front of me", i.e. this vehicle could
    # only ever run alone - which is what the kit used to do to every vehicle it
    # made, and is the bug these two fields exist to make visible.
    check("...and no coupling constraints unless asked",
          dat and "Constraint[" not in dat, dat)

    # --- the night preview, pressed like an artist presses it
    #
    # The sheet we just rendered is plain paint: nothing in it carries one of the
    # engine's light colours, so the honest answer is "this train runs dark", and
    # the button has to SAY so rather than hand back a pretty blue picture.
    check("the panel makes a night preview",
          bpy.ops.simutrans.night_preview() == {"FINISHED"})
    dark = os.path.join(OUT, "pvehicle_night.png")
    check("...and writes it next to the sheet", os.path.exists(dark))

    _w, _h, _a, day_px = sheet.read_png(os.path.join(OUT, "pvehicle.png"))
    _w, _h, _a, night_px = sheet.read_png(dark)
    check("...with the bodywork darkened",
          sum(sum(q[:3]) for q in night_px) < sum(sum(q[:3]) for q in day_px))
    check("...and nothing lit, because nothing was painted to light",
          not night.lights_in(day_px))

    # now give it a window in the engine's own colour and do it again
    glass = cube(x=0.0, z=0.75, sx=0.9, sy=0.45, sz=0.12)
    glass.data.materials.append(
        rig.make_special_color_material(bpy, colors.WINDOW_DARK, "glass"))
    check("the panel re-renders with a window", render(p, "pnight") == {"FINISHED"})
    p.basename = "pnight"
    check("the night preview runs again",
          bpy.ops.simutrans.night_preview() == {"FINISHED"})

    _w, _h, _a, day_px = sheet.read_png(os.path.join(OUT, "pnight.png"))
    _w, _h, _a, night_px = sheet.read_png(os.path.join(OUT, "pnight_night.png"))
    lit = night.lights_in(day_px)
    check("the window survived the render as the engine's exact colour",
          colors.WINDOW_DARK in lit, str(lit))
    warm = colors.LIGHTS[0][1]
    check("and at night it is the engine's warm yellow, byte for byte",
          sum(1 for q in night_px if q[:3] == warm) == lit[colors.WINDOW_DARK],
          "want %d px of %s" % (lit[colors.WINDOW_DARK], (warm,)))
    check("while the paint around it got darker, not brighter",
          sum(sum(q[:3]) for q in night_px) < sum(sum(q[:3]) for q in day_px))
    p.basename = "pvehicle"

    # --- vehicle with a coupling, driven from the panel
    clear()
    cube(sx=1.0, sy=0.4, sz=0.3)
    p.obj_name = "Panel_Coach"
    p.constraint_prev = "none, Panel_Loco"
    p.constraint_next = "Panel_Loco"
    check("the panel renders a coupled vehicle",
          render(p, "pcoach") == {"FINISHED"})
    dat = dat_of("pcoach")
    check("...and writes what may go in front of it",
          dat and "Constraint[Prev][0]=none" in dat
          and "Constraint[Prev][1]=Panel_Loco" in dat, dat)
    check("...and what may go behind it",
          dat and "Constraint[Next][0]=Panel_Loco" in dat, dat)
    p.constraint_prev = ""
    p.constraint_next = ""

    # --- building, with a snow season and an animated phase, from collections
    clear()
    cube(sz=0.8)
    snow = new_collection("season_1")
    cube(z=1.75, sx=0.65, sy=0.65, sz=0.12, collection=snow)
    lamp = new_collection("phase_1")
    cube(z=1.95, sx=0.15, sy=0.15, sz=0.15, collection=lamp)

    p.obj_type = "building"
    p.obj_name = "Panel_House"
    p.size_x, p.size_y, p.layouts = 1, 1, 4
    p.btype, p.level = "res", 3
    p.seasons, p.phases = 2, 2
    check("the panel renders a building", render(p, "pbuilding") == {"FINISHED"})
    dat = dat_of("pbuilding")
    check("...and writes a building .dat", dat and "obj=building" in dat)
    check("...with four layouts",
          dat and all(("BackImage[%d][0][0][0][0][0]=" % L) in dat
                      for L in range(4)), dat)
    check("...with a snow image (season 1)",
          dat and "BackImage[0][0][0][0][0][1]=" in dat, dat)
    check("...and a second animation phase",
          dat and "BackImage[0][0][0][0][1][0]=" in dat, dat)
    check("...and an animation_time", dat and "animation_time=" in dat, dat)

    # --- way, from the six collections
    clear()
    from simutrans_blender_kit.core import ways      # the INSTALLED copy
    for piece, base in ways.PIECES:
        col = new_collection("way_" + piece)
        cube(z=0.02, sx=0.3, sy=0.3, sz=0.02, collection=col)
        for bit, (bx, by) in ways.RIBI_BLENDER_VECTOR.items():
            if base & bit:
                cube(x=bx * 0.5, y=by * 0.5, z=0.02,
                     sx=0.3 if bx == 0 else 1.3, sy=0.3 if by == 0 else 1.3,
                     sz=0.02, collection=col)

    p.obj_type = "way"
    p.obj_name = "Panel_Road"
    p.waytype = "road"
    p.topspeed = 60
    check("the panel renders a way", render(p, "pway") == {"FINISHED"})
    dat = dat_of("pway")
    check("...and writes a way .dat", dat and "obj=way" in dat)
    check("...with all sixteen ribis",
          dat and all(("image[%s]=" % ways.code(r)) in dat for r in range(16)), dat)
    check("...and an icon, without which nobody could build it",
          dat and "icon=" in dat, dat)

    # --- wayobj, back and front
    clear()
    for piece, base in ways.PIECES:
        back = new_collection("wayobj_" + piece)
        cube(x=-0.4, y=0.4, z=0.45, sx=0.06, sy=0.06, sz=0.45, collection=back)
        front = new_collection("wayobj_" + piece + "_front")
        for bit, (bx, by) in ways.RIBI_BLENDER_VECTOR.items():
            if base & bit:
                cube(x=bx * 0.25, y=by * 0.25, z=0.85,
                     sx=0.05 if bx == 0 else 0.5, sy=0.05 if by == 0 else 0.5,
                     sz=0.03, collection=front)

    p.obj_type = "wayobj"
    p.obj_name = "Panel_Catenary"
    p.waytype = "track"
    p.own_waytype = "electrified_track"
    check("the panel renders a catenary", render(p, "pwayobj") == {"FINISHED"})
    dat = dat_of("pwayobj")
    check("...and writes a way-object .dat (with the hyphen)",
          dat and "obj=way-object" in dat)
    check("...in two layers",
          dat and "backimage[ns]=" in dat and "frontimage[ns]=" in dat, dat)
    check("...granting electrification",
          dat and "own_waytype=electrified_track" in dat, dat)

    # --- signal, two aspects from state_0 / state_1
    clear()
    cube(x=0.3, y=0.4, z=0.3, sx=0.06, sy=0.06, sz=0.3)
    red = new_collection("state_0")
    cube(x=0.3, y=0.4, z=0.65, sx=0.12, sy=0.12, sz=0.12, collection=red)
    green = new_collection("state_1")
    cube(x=0.3, y=0.45, z=0.65, sx=0.12, sy=0.12, sz=0.12, collection=green)

    p.obj_type = "roadsign"
    p.obj_name = "Panel_Signal"
    p.waytype = "track"
    p.is_signal = True
    p.states = 2
    check("the panel renders a signal", render(p, "psign") == {"FINISHED"})
    dat = dat_of("psign")
    check("...and writes a roadsign .dat", dat and "obj=roadsign" in dat)
    check("...as a signal", dat and "is_signal=1" in dat, dat)
    check("...with four directions in the RED state",
          dat and all(("image[%s][0]=" % d) in dat
                      for d in ("n", "s", "w", "e")), dat)
    check("...and a green one", dat and "image[n][1]=" in dat, dat)

    # every .dat the panel wrote must lint clean - the panel lints them itself, but
    # this is the check that it is not just printing and shrugging
    from simutrans_blender_kit.core import schema
    for basename in ("pvehicle", "pbuilding", "pway", "pwayobj", "psign"):
        text = dat_of(basename)
        findings = schema.lint(text) if text else [1]
        check("%s.dat lints clean" % basename, not findings, str(findings))

    print("\nout: %s" % OUT)
    if FAILED:
        print("\nPANEL_FAILED: %s" % ", ".join(FAILED))
        sys.exit(1)
    print("\nPANEL_OK")


main()
