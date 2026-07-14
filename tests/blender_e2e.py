"""End-to-end test INSIDE Blender.

    blender --background --python tests/blender_e2e.py

Builds a deliberately asymmetric test model (so the eight headings are actually
distinguishable), drives the real rig, renders, assembles the sheet, writes the
.dat, and validates the lot. Prints E2E_OK on success.
"""

import os
import sys

import bpy

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from addon import rig                       # noqa: E402
from core import colors, paksets, sheet     # noqa: E402

OUT = os.path.join(_ROOT, "build", "e2e")
PAKSET = "pak128"
FAILED = []


def png_text_chunks(path):
    """Every tEXt chunk in a PNG, as (keyword, value)."""
    import struct
    data = open(path, "rb").read()
    out = []
    i = 8                                    # past the signature
    while i < len(data) - 8:
        length = struct.unpack(">I", data[i:i + 4])[0]
        kind = data[i + 4:i + 8]
        if kind == b"tEXt":
            key, _, value = data[i + 8:i + 8 + length].partition(b"\x00")
            out.append((key.decode("latin1"), value.decode("latin1")))
        if kind == b"IEND":
            break
        i += 12 + length                     # len + type + body + crc
    return out


def check(name, cond, detail=""):
    if cond:
        print("  ok   %s" % name)
    else:
        print("  FAIL %s  %s" % (name, detail))
        FAILED.append(name)


def make_test_vehicle():
    """A body with a cab at one end and a stripe on one side: asymmetric in
    both axes, so a wrong azimuth or a mirrored frame is visible."""
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)

    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.3))
    body = bpy.context.active_object
    body.scale = (0.9, 0.35, 0.3)

    bpy.ops.mesh.primitive_cube_add(size=1, location=(0.6, 0, 0.75))
    cab = bpy.context.active_object
    cab.scale = (0.3, 0.3, 0.25)

    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0.36, 0.35))
    stripe = bpy.context.active_object
    stripe.scale = (0.85, 0.02, 0.08)

    # Paint the stripe with a REAL player colour, using the kit's shadeless
    # special-colour material. If the pipeline is right this survives the render
    # byte-for-byte and the validator sees it; if the view transform or the
    # sRGB/linear conversion is wrong, it will not.
    rig.build_rig(bpy, PAKSET)  # sets Standard view transform before we render
    mat = rig.make_special_color_material(bpy, colors.PLAYER_RAMP_BLUE[3])  # 96,132,167
    stripe.data.materials.append(mat)


def main():
    pak = paksets.get(PAKSET)
    make_test_vehicle()

    frames = rig.render_directions(bpy, OUT, PAKSET, dirs=8, basename="testloco")
    check("rendered 8 frames", len(frames) == 8, str(len(frames)))

    for code, path in frames:
        ok = os.path.exists(path)
        if ok:
            w, h, alpha, _px = sheet.read_png(path)
            ok = (w, h) == (pak.tile_px, pak.tile_px) and alpha
            check("frame %s is %dx%d RGBA" % (code, pak.tile_px, pak.tile_px), ok,
                  "%dx%d alpha=%s" % (w, h, alpha))
        else:
            check("frame %s exists" % code, False, path)

    # Nothing about the machine that rendered it may travel inside a sprite. By
    # default Blender writes seven tEXt chunks into every PNG, one of which is the
    # ABSOLUTE PATH of the .blend - so the author's home directory shipped inside
    # every published sprite. Checked on the bytes, because that is where it was.
    for code, path in frames:
        if not os.path.exists(path):
            continue
        chunks = png_text_chunks(path)
        check("frame %s carries no metadata" % code, chunks == [],
              "; ".join("%s=%s" % kv for kv in chunks))
        raw = open(path, "rb").read()
        check("frame %s does not contain a filesystem path" % code,
              b"Users" not in raw and _ROOT.encode("latin1", "replace") not in raw)

    # the camera must be exactly the engine's projection
    cam = bpy.data.objects[rig.CAM_NAME]
    import math
    check("camera is ORTHO", cam.data.type == "ORTHO")
    check("ortho_scale == tile_world*sqrt(2)",
          abs(cam.data.ortho_scale - pak.ortho_scale) < 1e-6,
          "%.6f vs %.6f" % (cam.data.ortho_scale, pak.ortho_scale))
    # Blender stores euler as float32, so the radians round-trip costs ~1e-6 deg.
    check("camera elevation is 60deg rot_x",
          abs(math.degrees(cam.rotation_euler[0]) - 60.0) < 1e-4,
          "%.6f" % math.degrees(cam.rotation_euler[0]))
    check("alpha film on", bpy.context.scene.render.film_transparent)

    sheet_png, dat_path, placement = rig.build_sheet_and_dat(
        frames, OUT, PAKSET, basename="testloco", cols=4,
        name="Test_Loco", waytype="track", power=1500, speed=140,
    )

    sw, sh, _a, spx = sheet.read_png(sheet_png)
    check("sheet is 4x2 cells",
          (sw, sh) == (4 * pak.tile_px, 2 * pak.tile_px), "%dx%d" % (sw, sh))
    check("sheet dims are a multiple of tile_px (makeobj requires it)",
          sw % pak.tile_px == 0 and sh % pak.tile_px == 0)

    dat = open(dat_path, encoding="utf-8").read()
    check("dat has all 8 image refs",
          all(("EmptyImage[%s]=" % c) in dat for c, _ in frames), dat)
    check("dat references the sheet by name", "testloco.0.0" in dat)
    check("dat is a vehicle", "obj=vehicle" in dat and "waytype=track" in dat)

    # the validator must SEE the player-colour stripe we deliberately painted
    rgb = [(p[0], p[1], p[2]) for p in spx if len(p) >= 3 and p[3] > 0]
    hits = colors.scan(rgb)
    check("validator flags the player-colour stripe", len(hits) > 0,
          "no reserved colours found - render or validator broken")
    for line in colors.report(hits)[:3]:
        print("       -> %s" % line)

    print("\nsheet: %s" % sheet_png)
    print("dat:   %s" % dat_path)
    print("placement: %s" % placement)

    # A RELATIVE output path must work, and until now none of these tests ever
    # tried one - they all build an absolute path out of __file__. Blender does not
    # resolve a relative render.filepath against the process's working directory; it
    # resolves it against the .blend, and an unsaved .blend has nowhere to resolve
    # against. So "build/x" silently sent the PNGs to C:\build\x, outside the
    # project, and the slicer then failed on a file that had "just been written".
    # An artist typing a path into the panel would have hit this on their first try.
    os.chdir(_ROOT)
    rel = os.path.join("build", "relpath_check")
    frames = rig.render_directions(bpy, rel, PAKSET, dirs=4, basename="relcheck")
    check("a relative out_dir lands inside the project", len(frames) == 4)
    for _code, path in frames:
        check("...and %s really exists" % os.path.basename(path),
              os.path.isfile(path), path)
        check("...under the project, not at the drive root",
              os.path.abspath(path).startswith(os.path.abspath(_ROOT)), path)

    if FAILED:
        print("\nE2E_FAILED: %s" % ", ".join(FAILED))
        sys.exit(1)
    print("\nE2E_OK")


main()
