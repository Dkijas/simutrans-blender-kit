"""Install the add-on the way an artist would, and drive the panel's buttons.

    blender --background --factory-startup --python tests/blender_addon.py

--factory-startup IS REQUIRED, and not just for hygiene. If the add-on is already
enabled in the user's preferences, Blender imports it at startup; installing a
newer zip then overwrites the files on disk but the OLD module object is still in
sys.modules, so the test happily exercises the previous version and passes (or
fails) for the wrong reasons. Factory startup gives us a Blender with no add-ons
loaded, so the copy we install is the copy we test.

An add-on that imports cleanly in a checkout can still fail once Blender has
copied it into its own addons folder and imported it as a package - the relative
imports change, and a panel that fails to register is just silently not there.
So: build the zip, install it, enable it, then call the operators and check the
files land on disk.

Prints ADDON_OK on success.
"""

import os
import sys

import bpy

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from tools import build_addon_zip           # noqa: E402

MODULE = "simutrans_blender_kit"
OUT = os.path.join(_ROOT, "build", "addon_test")
FAILED = []


def check(name, cond, detail=""):
    if cond:
        print("  ok   %s" % name)
    else:
        print("  FAIL %s  %s" % (name, detail))
        FAILED.append(name)


def isolate_from_the_checkout():
    """Make the INSTALLED add-on stand on its own.

    We put the checkout on sys.path to import the zip builder. Leave it there and
    the test is a lie: `core` and `addon` become importable as top-level modules,
    so a stray `from core import ...` inside the installed package resolves
    against the checkout and passes - while a real user, whose Blender has never
    heard of this directory, gets ModuleNotFoundError. That is exactly the bug
    this test missed once already (rig.projection_rot_x). So: drop the checkout
    and forget anything imported from it.
    """
    sys.path[:] = [p for p in sys.path if os.path.abspath(p) != _ROOT]
    for name in list(sys.modules):
        if name == "tools" or name.split(".")[0] in ("core", "addon"):
            del sys.modules[name]

    for name in ("core", "addon"):
        try:
            __import__(name)
            check("%r must NOT be importable on its own" % name, False,
                  "the checkout is still on sys.path - the test would lie")
        except ImportError:
            pass


def main():
    zip_path = build_addon_zip.main()
    isolate_from_the_checkout()

    # Blender may still have it enabled from a previous run
    try:
        bpy.ops.preferences.addon_disable(module=MODULE)
    except Exception:
        pass

    bpy.ops.preferences.addon_install(overwrite=True, filepath=zip_path)
    bpy.ops.preferences.addon_enable(module=MODULE)
    check("add-on enables", MODULE in bpy.context.preferences.addons)

    # the panel and the operators must actually exist now
    check("panel registered", hasattr(bpy.types, "SIMUTRANS_PT_panel"))
    check("sub-panel registered", hasattr(bpy.types, "SIMUTRANS_PT_dat"))
    check("scene props registered", hasattr(bpy.types.Scene, "simutrans"))
    for op in ("build_rig", "render_sheet", "check_colors"):
        check("operator simutrans.%s" % op, hasattr(bpy.ops.simutrans, op))

    # --- now use it exactly as the panel does ---
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)

    p = bpy.context.scene.simutrans

    # The default output is '//simutrans', relative to the .blend. Blender starts
    # with no .blend saved, which is EXACTLY the state an artist first sees the
    # panel in - and back then Blender would quietly resolve '//' against its
    # working directory and scatter the sheet somewhere random. Refuse instead.
    check("default output is blend-relative", p.out_dir.startswith("//"), p.out_dir)
    check("unsaved .blend has no filepath", bpy.data.filepath == "")
    try:
        bpy.ops.simutrans.render_sheet()
        check("unsaved .blend + '//' path is refused", False,
              "it rendered into who-knows-where")
    except RuntimeError as e:
        check("unsaved .blend + '//' path is refused", "Save your .blend" in str(e),
              str(e))

    p.pakset = "pak64"
    p.out_dir = OUT
    p.basename = "uitest"
    p.dirs = "4"
    p.obj_name = "UI_Test"
    p.waytype = "road"
    p.power = 120

    # Render Sheet with an empty scene must refuse, not crash or write junk.
    # An operator that self.report()s an ERROR makes bpy.ops raise, so the
    # refusal arrives as a RuntimeError carrying our message.
    try:
        bpy.ops.simutrans.render_sheet()
        check("empty scene is refused", False, "it went ahead and rendered nothing")
    except RuntimeError as e:
        check("empty scene is refused", "no mesh" in str(e), str(e))

    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.3))
    bpy.context.active_object.scale = (0.8, 0.4, 0.3)

    check("Build Rig runs", bpy.ops.simutrans.build_rig() == {"FINISHED"})
    check("Render Sheet runs", bpy.ops.simutrans.render_sheet() == {"FINISHED"})

    sheet_png = os.path.join(OUT, "uitest.png")
    dat = os.path.join(OUT, "uitest.dat")
    check("sheet written", os.path.exists(sheet_png), sheet_png)
    check("dat written", os.path.exists(dat), dat)

    if os.path.exists(dat):
        text = open(dat, encoding="utf-8").read()
        check("dat used the panel's values",
              "name=UI_Test" in text and "waytype=road" in text
              and "power=120" in text, text[:200])
        check("4 directions only, in engine order",
              all(("EmptyImage[%s]=" % c) in text for c in ("s", "w", "sw", "se"))
              and "EmptyImage[n]=" not in text, text)

    check("Check Colours runs", bpy.ops.simutrans.check_colors() == {"FINISHED"})

    # --- Compile .pak: the button must really produce a .pak ---
    makeobj = os.path.join(_ROOT, "build", "tools", "makeobj.exe")
    if not os.path.exists(makeobj):
        print("  skip Compile .pak (no makeobj at %s)" % makeobj)
    else:
        # refuses before it is told where makeobj is
        p.makeobj_path = ""
        try:
            bpy.ops.simutrans.compile_pak()
            check("compile without makeobj is refused", False, "it went ahead")
        except RuntimeError as e:
            check("compile without makeobj is refused", "makeobj" in str(e), str(e))

        # and refuses a path that is not there, rather than shelling out to it
        p.makeobj_path = os.path.join(OUT, "nope.exe")
        try:
            bpy.ops.simutrans.compile_pak()
            check("a bogus makeobj path is refused", False, "it went ahead")
        except RuntimeError as e:
            check("a bogus makeobj path is refused", "not found" in str(e), str(e))

        install = os.path.join(OUT, "addons")
        p.makeobj_path = makeobj
        p.install_dir = install
        check("Compile .pak runs", bpy.ops.simutrans.compile_pak() == {"FINISHED"})

        pak = os.path.join(OUT, "uitest.pak")
        check("pak written", os.path.exists(pak), pak)
        check("pak is not empty", os.path.exists(pak) and os.path.getsize(pak) > 0)
        check("pak installed to the addons folder",
              os.path.exists(os.path.join(install, "uitest.pak")))

    # --- the panel must actually speak Spanish when Blender does ---
    view = bpy.context.preferences.view
    view.use_translate_interface = True
    view.use_translate_tooltips = True
    view.language = "es"

    from bpy.app.translations import pgettext_iface, pgettext_tip
    CTX = sys.modules[MODULE].addon.translations.CONTEXT

    check("labels translate", pgettext_iface("Build Rig", CTX) == "Montar rig",
          pgettext_iface("Build Rig", CTX))
    check("panel headings translate", pgettext_iface("Output", CTX) == "Salida",
          pgettext_iface("Output", CTX))
    check("property names translate",
          pgettext_iface("Speed (km/h)", CTX) == "Velocidad (km/h)",
          pgettext_iface("Speed (km/h)", CTX))
    check("tooltips translate",
          "vagón" in pgettext_tip("0 makes it an unpowered wagon or trailer", CTX),
          pgettext_tip("0 makes it an unpowered wagon or trailer", CTX))
    check("a format string keeps its %d",
          (pgettext_iface("%d px, ortho_scale %.4f", CTX)
           % (128, 2.8284)).startswith("128"),
          pgettext_iface("%d px, ortho_scale %.4f", CTX))

    # Blender's own catalogue must not hijack our words. It translates "Engine"
    # as the RENDER engine; ours is the locomotive's. Different contexts, so both
    # can be right - and if we ever drop the context, this catches it.
    check("Blender does translate 'Engine' itself",
          pgettext_iface("Engine") != "Engine", pgettext_iface("Engine"))
    check("but OUR 'Engine' is ours", pgettext_iface("Engine", CTX) == "Motor",
          pgettext_iface("Engine", CTX))

    # and English still works when Blender is English
    view.language = "en_US"
    check("English is unchanged", pgettext_iface("Build Rig", CTX) == "Build Rig",
          pgettext_iface("Build Rig", CTX))

    bpy.ops.preferences.addon_disable(module=MODULE)
    check("add-on disables cleanly", MODULE not in bpy.context.preferences.addons)

    if FAILED:
        print("\nADDON_FAILED: %s" % ", ".join(FAILED))
        sys.exit(1)
    print("\nADDON_OK")


main()
