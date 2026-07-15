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
    """Build the zip from source, then install and enable it as a person would.

    It used to install whatever zip was already sitting in build/. This suite only
    passed against current code because the `addon` suite happens to run before it
    and happens to rebuild the zip; run this file on its own and it tested whatever
    was last built - which it duly did, reporting the OLD warning text for a change
    that was already in the tree.
    """
    import subprocess
    subprocess.run([sys.executable,
                    os.path.join(_ROOT, "tools", "build_addon_zip.py")], check=True)

    zip_path = os.path.join(_ROOT, "build", "simutrans_blender_kit.zip")
    if not os.path.exists(zip_path):
        raise SystemExit("tools/build_addon_zip.py produced no %s" % zip_path)
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


def press_and_catch(props, basename):
    """Press Render Sheet and read back what it REPORTED to the user.

    Not what it printed. Blender's console is not the artist's screen, and the whole
    question is whether the warning reached the PANEL. report() disappears into
    Blender's C layer and cannot be intercepted from Python - shadowing it on the
    operator class does nothing, because bpy_struct resolves the name itself - so
    the operator keeps its own record and this reads that.
    """
    from simutrans_blender_kit.addon import ui as ui_mod

    del ui_mod.REPORTS[:]
    result = render(props, basename)
    return result, list(ui_mod.REPORTS)


def press_material_and_catch(props):
    """Press Apply Material and read back what it reported. See press_and_catch.

    bpy.ops raises when an operator returns CANCELLED, which is exactly the case
    under test (nothing selected), so the report is read regardless.
    """
    from simutrans_blender_kit.addon import ui as ui_mod
    del ui_mod.REPORTS[:]
    try:
        result = bpy.ops.simutrans.apply_material()
    except RuntimeError:
        result = {"CANCELLED"}
    return result, list(ui_mod.REPORTS)


def press_write_dat_and_catch():
    """Press Write .dat and read back what it reported."""
    from simutrans_blender_kit.addon import ui as ui_mod
    del ui_mod.REPORTS[:]
    try:
        result = bpy.ops.simutrans.write_dat()
    except RuntimeError:
        result = {"CANCELLED"}
    return result, list(ui_mod.REPORTS)


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

    # --- cargo-variant wagon, driven from the panel through the freight_ collections
    clear()
    cube(sx=1.0, sy=0.4, sz=0.3)                       # the flatbed, always there
    coal = new_collection("freight_0")
    cube(z=0.55, sx=0.9, sy=0.35, sz=0.2, collection=coal)
    oil = new_collection("freight_1")
    cube(z=0.7, sx=0.3, sy=0.3, sz=0.6, collection=oil)
    p.obj_name = "Panel_Hopper"
    p.freight_goods = "Kohle, Oel"
    check("the panel renders a cargo-variant wagon",
          render(p, "phopper") == {"FINISHED"})
    dat = dat_of("phopper")
    check("...and writes the empty images", dat and "EmptyImage[s]=" in dat, dat)
    check("...and a freight image per good",
          dat and "FreightImage[0][s]=" in dat and "FreightImage[1][s]=" in dat, dat)
    check("...and the freightimagetype the engine fatals without",
          dat and "\nfreightimagetype[0]=Kohle\n" in dat
          and "\nfreightimagetype[1]=Oel\n" in dat, dat)

    # the mismatch guard: two goods, one collection -> the panel must SAY so, not
    # ship a wagon the engine will reject. An ERROR report makes bpy.ops raise, so
    # read REPORTS around the call (they are appended before report() raises).
    bpy.data.collections.remove(oil)
    from simutrans_blender_kit.addon import ui as ui_mod
    del ui_mod.REPORTS[:]
    try:
        render(p, "phopper_bad")
    except RuntimeError:
        pass
    reports = list(ui_mod.REPORTS)
    check("a good with no freight_ collection is reported to the panel",
          any(lvl == {"ERROR"} and "freight_" in msg for lvl, msg in reports),
          str(reports))
    p.freight_goods = ""

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

    # --- tunnel portal, back and front layers
    clear()
    back = new_collection("tunnel_portal")
    cube(x=-0.22, y=0.15, z=0.25, sx=0.12, sy=0.5, sz=0.5, collection=back)
    cube(x=0.22, y=0.15, z=0.25, sx=0.12, sy=0.5, sz=0.5, collection=back)
    cube(x=0.0, y=-0.3, z=0.4, sx=0.9, sy=0.4, sz=0.8, collection=back)
    front = new_collection("tunnel_portal_front")
    cube(x=0.0, y=0.3, z=0.48, sx=0.6, sy=0.16, sz=0.14, collection=front)

    p.obj_type = "tunnel"
    p.obj_name = "Panel_Tunnel"
    p.waytype = "track"
    p.topspeed = 120
    check("the panel renders a tunnel", render(p, "ptunnel") == {"FINISHED"})
    dat = dat_of("ptunnel")
    check("...and writes a tunnel .dat", dat and "obj=tunnel" in dat)
    check("...with all four back portals",
          dat and all(("backimage[%s]=" % d) in dat for d in "nsew"), dat)
    check("...and all four front portals",
          dat and all(("frontimage[%s]=" % d) in dat for d in "nsew"), dat)
    check("...and an icon, without which nobody could build it",
          dat and "icon=" in dat, dat)

    # every .dat the panel wrote must lint clean - the panel lints them itself, but
    # this is the check that it is not just printing and shrugging
    from simutrans_blender_kit.core import schema
    for basename in ("pvehicle", "pbuilding", "pway", "pwayobj", "psign", "ptunnel"):
        text = dat_of(basename)
        findings = schema.lint(text) if text else [1]
        check("%s.dat lints clean" % basename, not findings, str(findings))

    # --- DOES THE ARTIST EVER SEE THE WARNING?
    #
    # The rig has always known when a model runs off the edge of its cell. It said
    # so to the CONSOLE, which is not open on an artist's screen, and the panel
    # said "Rendered". So the sprite shipped with the cab cut off, and the tool had
    # told nobody. This checks what the operator REPORTS, not what it prints.
    clear()
    p.obj_type = "vehicle"
    p.dirs = "4"
    cube(sx=3.0, sy=3.0, sz=3.0)          # far too big for a 64px tile
    result, reported = press_and_catch(p, "pclip")

    check("an oversized model still renders", result == {"FINISHED"}, str(result))
    check("...and the PANEL says it does not fit, not just the console",
          any("WARNING" in level and "does not fit" in message
              for level, message in reported),
          "the operator reported: %r" % (reported,))

    # and the opposite: a model that fits must not cry wolf
    clear()
    cube(sx=0.4, sy=0.4, sz=0.3)
    _result, quiet = press_and_catch(p, "pfits")
    check("a model that fits raises no clipping warning",
          not any("does not fit" in m for _l, m in quiet), str(quiet))

    # --- CAN AN ARTIST PAINT A PLAYER COLOUR WITHOUT WRITING PYTHON?
    #
    # This is the reason the kit exists, and until now it had no button: the
    # material functions were reachable only from a script. An artist selects a
    # mesh, picks "Player colour", presses the button - and the pixels that come
    # out have to be a player colour the engine will actually recolour.
    clear()
    p.obj_type = "vehicle"
    p.dirs = "4"
    ob = cube(sx=0.4, sy=0.4, sz=0.3)

    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    p.material = "player"
    result = bpy.ops.simutrans.apply_material()
    check("the Apply Material button runs", result == {"FINISHED"}, str(result))
    check("the object came away with a material", bool(ob.data.materials))

    render(p, "pplayer")
    _w, _h, alpha, px = sheet.read_png(os.path.join(OUT, "pplayer.png"))
    body = [(q[0], q[1], q[2]) for q in px if not (alpha and q[3] == 0)]
    hits = colors.scan(body)
    player_hits = sum(n for rgb, n in hits.items()
                      if colors.classify(rgb) and "player" in colors.classify(rgb))
    check("...and the rendered sprite really is player-colour, exactly",
          player_hits > 50, "%d player-colour pixels (hits: %r)"
          % (player_hits, {("#%02X%02X%02X" % k): v for k, v in hits.items()}))

    # a night light next, because that is the other material an artist cannot reach
    clear()
    ob = cube(sx=0.4, sy=0.4, sz=0.3)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    p.material = "signal_purple"
    bpy.ops.simutrans.apply_material()
    render(p, "ppurple")
    _w, _h, alpha, px = sheet.read_png(os.path.join(OUT, "ppurple.png"))
    body = [(q[0], q[1], q[2]) for q in px if not (alpha and q[3] == 0)]
    check("the purple signal lamp is the colour makeobj matches (#FF017F)",
          colors.LAMP_PURPLE in body,
          "not one #FF017F pixel - a signal painted from the panel would not light")

    # and the button must refuse when nothing is selected, rather than do nothing
    clear()
    p.material = "player"
    _r, reported = press_material_and_catch(p)
    check("with nothing selected, the button says so",
          any("ERROR" in level for level, _m in reported), str(reported))

    # --- WRITE .DAT WITHOUT RE-RENDERING
    #
    # Change a number, rewrite the .dat, and it must be byte-for-byte what a full
    # render would have produced - because the expensive step (the render) is skipped
    # and only the .dat is rebuilt from the frames already on disk.
    clear()
    p.obj_type = "vehicle"
    p.dirs = "4"
    p.basename = "prewrite"
    p.power = 1000
    cube(sx=0.4, sy=0.4, sz=0.3)
    render(p, "prewrite")
    after_render = dat_of("prewrite")
    check("a render produced a .dat", after_render is not None)
    check("the rendered .dat has the rendered power",
          after_render and "power=1000" in after_render, "no power=1000")

    # write .dat only, nothing changed: identical file, no render
    result = bpy.ops.simutrans.write_dat()
    check("Write .dat runs after a render", result == {"FINISHED"}, str(result))
    after_write = dat_of("prewrite")
    check("Write .dat with nothing changed reproduces the .dat exactly",
          after_write == after_render, "differs")

    # now CHANGE a number and write .dat only - the new number, same image refs
    p.power = 2500
    bpy.ops.simutrans.write_dat()
    changed = dat_of("prewrite")
    check("Write .dat picks up the new power", "power=2500" in changed, "no 2500")
    check("...and the image references are unchanged",
          [l for l in changed.splitlines() if l.startswith("image")]
          == [l for l in after_render.splitlines() if l.startswith("image")])

    # and it refuses when there was no render for this basename
    p.basename = "never_rendered"
    _r, reported = press_write_dat_and_catch()
    check("Write .dat with no prior render says so",
          any("ERROR" in level for level, _m in reported), str(reported))

    print("\nout: %s" % OUT)
    if FAILED:
        print("\nPANEL_FAILED: %s" % ", ".join(FAILED))
        sys.exit(1)
    print("\nPANEL_OK")


main()
