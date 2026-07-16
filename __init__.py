"""Simutrans Blender Kit - Blender add-on entry point.

Install the zip built by tools/build_addon_zip.py, then press N in the 3D view
and pick the Simutrans tab.

The add-on is only a shell: all the geometry lives in core/ (pure stdlib Python,
testable without Blender) and addon/rig.py.
"""

bl_info = {
    "name": "Simutrans Blender Kit",
    "author": "victor_18993",
    "version": (0, 9, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar (N) > Simutrans",
    "description": "Render Simutrans vehicles, ways, catenary, buildings and signals, "
                   "and emit a compilable .dat",
    "category": "Import-Export",
    "doc_url": "https://github.com/Dkijas/simutrans-blender-kit",
}


def register():
    from .addon import ui
    ui.register()


def unregister():
    from .addon import ui
    ui.unregister()
