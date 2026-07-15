"""Core tests. Plain asserts, no pytest - runs anywhere, incl. Blender's python.

    python tests/test_core.py
"""

import math
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import (colors, convoy, datgen, directions, night, paksets, projection,
                  schema, sheet, tunnels)
from tools import spec      # NOT core: it is not shipped. See tools/spec.py.

_passed = 0


def check(name, cond, detail=""):
    global _passed
    if cond:
        _passed += 1
        print("  ok   %s" % name)
    else:
        print("  FAIL %s  %s" % (name, detail))
        raise AssertionError(name)


# ---------------------------------------------------------------- projection
def test_camera_reproduces_engine():
    """THE load-bearing test.

    If a 30-degree orthographic camera really is the Simutrans projection, then
    projecting through the camera must give the same pixels as the engine's own
    viewport_t::get_screen_coord(). Any error in the elevation or ortho_scale
    shows up here immediately.
    """
    for tile_px in (64, 128, 192, 256):
        for wx in (-3, -1, 0, 0.5, 1, 2, 7):
            for wy in (-2, 0, 0.25, 1, 3):
                ex, ey = projection.project_engine(wx, wy, tile_px)
                cx, cy = projection.project_camera(wx, wy, 0.0, tile_px, 1.0)
                check(
                    "camera==engine tile=%d (%s,%s)" % (tile_px, wx, wy),
                    abs(ex - cx) < 1e-9 and abs(ey - cy) < 1e-9,
                    "engine=(%.6f,%.6f) camera=(%.6f,%.6f)" % (ex, ey, cx, cy),
                )


def test_elevation_is_exactly_30():
    check("elevation == 30", abs(projection.ELEVATION_DEG - 30.0) < 1e-12)
    check("sin(elev) == 1/2",
          abs(math.sin(math.radians(projection.ELEVATION_DEG)) - 0.5) < 1e-12)
    check("blender rot_x == 60", abs(projection.CAMERA_ROTATION_X_DEG - 60.0) < 1e-12)


def test_ortho_scale_and_the_wiki_rounding():
    # 1 tile = 2 Blender units (the German wiki's convention)
    s = projection.ortho_scale(2.0)
    check("ortho_scale(2) == 2*sqrt(2)", abs(s - 2 * math.sqrt(2)) < 1e-12,
          "got %.6f" % s)
    # The wiki says 2.800. That is ~1% small, so sprites come out ~1% too big.
    err = abs(2.800 - s) / s
    check("wiki's 2.800 is ~1% off (documented)", 0.005 < err < 0.02,
          "relative error %.4f" % err)


def test_ground_sits_three_quarters_down_the_cell():
    """Measured from pak128's own tile cursor (landscape/grounds/marker.png).

    Its flat-tile halves (marker.0.0 + marker.3.0) occupy x 2..125, y 65..126 of
    the 128px cell - centre (63.5, 95.5). So the tile centre is at (1/2, 3/4) of
    the cell, NOT the cell centre, and the diamond fills the bottom half while
    the top half is headroom. tests/blender_alignment.py renders a tile quad
    through the rig and lands on the same (63.5, 95.5).
    """
    check("tile centre x is mid-cell", projection.TILE_CENTRE_IN_CELL[0] == 0.5)
    check("tile centre y is 3/4 down", projection.TILE_CENTRE_IN_CELL[1] == 0.75)

    # marker.png, measured
    check("agrees with pak128's marker.png",
          abs(projection.TILE_CENTRE_IN_CELL[0] * 128 - 63.5) <= 0.5 and
          abs(projection.TILE_CENTRE_IN_CELL[1] * 128 - 95.5) <= 0.5)

    # the camera lift that puts it there: tile_world * sqrt(6)/6
    for tw in (1.0, 2.0, 4.0):
        lift = projection.camera_target_lift(tw)
        check("camera lift == tile_world*sqrt(6)/6 (tw=%g)" % tw,
              abs(lift - tw * math.sqrt(6.0) / 6.0) < 1e-12, "%.6f" % lift)

    # and it really does drop the ground by a quarter of a cell
    tile_px, tw = 128, 2.0
    lift = projection.camera_target_lift(tw)
    px_per_world = tile_px / (math.sqrt(2.0) * tw)
    drop_px = lift * math.cos(math.radians(projection.ELEVATION_DEG)) * px_per_world
    check("lift drops the ground exactly tile_px/4", abs(drop_px - tile_px / 4.0) < 1e-9,
          "%.6f vs %.1f" % (drop_px, tile_px / 4.0))


def test_tile_is_2_to_1():
    for pak in (paksets.PAK64, paksets.PAK128, paksets.PAK256):
        w, h = pak.diamond_px
        check("%s diamond 2:1" % pak.name, w == pak.tile_px and h == pak.tile_px // 2)


def test_pakset_makeobj_arg():
    check("pak64 -> 'pak'", paksets.PAK64.makeobj_arg == "pak")
    check("pak128 -> 'pak128'", paksets.PAK128.makeobj_arg == "pak128")


def test_height_step_is_the_paksets_own():
    """One height level, and it is NOT the same number for everybody.

    settings.cc:1338 reads `tile_height` out of the PAKSET's simuconf.tab, and
    simconst.h:110 scales it to the pakset's tile width:

        rise on screen = tile_height * tile_px / 64

    The measured values are pak128's 8 and the demo pakset's 16, and they both come
    out at sixteen screen pixels: the pakset authors keep the apparent steepness
    constant and move the .tab number to pay for it. This module used to declare 16
    for everyone, which would have drawn pak128's ramps at twice the pitch of the
    pakset they sit in - harmlessly, right up until something read the field.
    """
    check("pak128 rises 16 px a level", abs(paksets.PAK128.height_rise_px - 16) < 1e-9,
          "%.3f" % paksets.PAK128.height_rise_px)
    check("the demo pakset rises 16 px too",
          abs(paksets.PAK64.height_rise_px - 16) < 1e-9,
          "%.3f" % paksets.PAK64.height_rise_px)
    check("...and they get there from DIFFERENT tile_height values",
          paksets.PAK128.height_step != paksets.PAK64.height_step)

    # And the world height must be whatever THIS camera has to lift to draw that.
    for pak in (paksets.PAK64, paksets.PAK128, paksets.PAK256):
        drawn = projection.project_camera(0.0, 0.0, pak.height_world,
                                          pak.tile_px, pak.tile_world)[1]
        check("%s: lifting height_world draws exactly one height level" % pak.name,
              abs(drawn - pak.height_rise_px) < 1e-6,
              "%.4f px vs %.4f" % (drawn, pak.height_rise_px))


# ---------------------------------------------------------------- directions
def test_dir_codes_match_engine():
    check("dir order == vehicle_writer.cc",
          directions.DIR_CODES == ("s", "w", "sw", "se", "n", "e", "ne", "nw"))
    check("4 dirs = first four", directions.codes_for(4) == ("s", "w", "sw", "se"))
    check("8 dirs = all", len(directions.codes_for(8)) == 8)
    try:
        directions.codes_for(6)
        check("6 dirs rejected", False)
    except ValueError:
        check("6 dirs rejected (makeobj only takes 4 or 8)", True)
    # azimuths are distinct and 45 apart
    az = sorted(directions.azimuth_deg(c) % 360 for c in directions.DIR_CODES)
    check("8 distinct azimuths, 45 apart",
          len(set(az)) == 8 and all(abs(az[i + 1] - az[i] - 45) < 1e-9
                                    for i in range(7)))


def test_base_azimuth_matches_real_pakset_art():
    """Pin BASE_AZIMUTH_DEG against a vehicle that actually ships in pak128.

    Reading vehicles/road-psg+mail/aec_aclo_regent_iii (Zeno) - its .dat against
    its sheet - shows unambiguously that:

        nw, se  -> end-on   (the vehicle runs along the camera axis)
        ne, sw  -> broadside
        n,s,e,w -> three-quarter

    The model's nose is +X, and with the camera at azimuth az that axis lands on
    screen at (cos az, -0.5 sin az). So "end-on" is simply where that vector is
    SHORTEST and "broadside" where it is LONGEST. If anyone re-tunes the base
    azimuth and breaks the convention, this fails.
    """
    def screen_extent(code):
        a = math.radians(directions.azimuth_deg(code))
        return math.hypot(math.cos(a), -0.5 * math.sin(a))

    ext = {c: screen_extent(c) for c in directions.DIR_CODES}
    end_on = sorted(ext, key=lambda c: ext[c])[:2]
    broadside = sorted(ext, key=lambda c: -ext[c])[:2]

    check("end-on headings are nw & se (as in real pak128 art)",
          set(end_on) == {"nw", "se"}, str(sorted(ext.items(), key=lambda kv: kv[1])))
    check("broadside headings are ne & sw",
          set(broadside) == {"ne", "sw"}, str(broadside))
    for c in ("n", "s", "e", "w"):
        check("%s is a three-quarter view" % c,
              min(ext.values()) < ext[c] < max(ext.values()))
    check("base azimuth is 135 (was 45 = wrong by 90deg)",
          abs(directions.BASE_AZIMUTH_DEG - 135.0) < 1e-9)


# -------------------------------------------------------------------- colors
def test_reserved_colors():
    check("transparency key", colors.TRANSPARENT == (231, 255, 255))
    check("blue ramp ends", colors.PLAYER_RAMP_BLUE[0] == (36, 75, 103)
          and colors.PLAYER_RAMP_BLUE[-1] == (176, 210, 255))
    check("gold ramp ends", colors.PLAYER_RAMP_GOLD[0] == (123, 88, 3)
          and colors.PLAYER_RAMP_GOLD[-1] == (255, 249, 13))
    check("16 player colours", len(colors.PLAYER_COLORS) == 16)


def test_validator_catches_accidental_player_colour():
    # a sky-ish blue that happens to be exactly a player colour, plus safe pixels
    pixels = [(10, 20, 30)] * 50 + [(96, 132, 167)] * 3 + [(231, 255, 255)] * 99
    hits = colors.scan(pixels)                       # transparency ignored
    check("catches the 3 stray player pixels", hits == {(96, 132, 167): 3},
          str(hits))
    check("classify", colors.classify((96, 132, 167)) == "player colour (blue ramp)")
    check("free colour is free", colors.classify((10, 20, 30)) is None)
    hits2 = colors.scan(pixels, ignore_transparent=False)
    check("transparency counted when asked", hits2[(231, 255, 255)] == 99)


# --------------------------------------------------------------------- sheet
def _solid(path, size, rgba):
    sheet.write_png(path, size, size, [rgba] * (size * size), has_alpha=True)


def _write_indexed_png(path, width, height, depth, palette, indices, trns=None):
    """Hand-build a paletted PNG - real pakset art is indexed, Blender's is not."""
    import struct
    import zlib

    per_byte = 8 // depth
    raw = bytearray()
    for y in range(height):
        raw.append(0)                       # filter: None
        row, acc, filled = bytearray(), 0, 0
        for x in range(width):
            acc = (acc << depth) | indices[y * width + x]
            filled += 1
            if filled == per_byte:
                row.append(acc)
                acc, filled = 0, 0
        if filled:
            row.append(acc << (depth * (per_byte - filled)))
        raw += row

    def chunk(tag, body):
        return (struct.pack(">I", len(body)) + tag + body
                + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF))

    plte = b"".join(bytes(c) for c in palette)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, depth, 3, 0, 0, 0)))
        f.write(chunk(b"PLTE", plte))
        if trns:
            f.write(chunk(b"tRNS", bytes(trns)))
        f.write(chunk(b"IDAT", zlib.compress(bytes(raw), 9)))
        f.write(chunk(b"IEND", b""))


def test_reads_paletted_png():
    """pak128's marker.png is a 2-bit indexed PNG. If we cannot read that, we
    cannot even look at the artwork we are supposed to be compatible with."""
    pal = [(231, 255, 255), (96, 132, 167), (10, 20, 30), (255, 0, 0)]
    idx = [0, 1, 2, 3,
           3, 2, 1, 0]
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, "indexed.png")
        _write_indexed_png(p, 4, 2, 2, pal, idx)
        w, h, alpha, px = sheet.read_png(p)
        check("2-bit indexed: size", (w, h) == (4, 2), "%dx%d" % (w, h))
        check("2-bit indexed: no alpha without tRNS", alpha is False)
        check("2-bit indexed: pixels resolve through the palette",
              px == [pal[i] for i in idx], str(px))

        # same image, but with tRNS making index 0 transparent
        p2 = os.path.join(tmp, "indexed_a.png")
        _write_indexed_png(p2, 4, 2, 2, pal, idx, trns=[0, 255, 255, 255])
        w, h, alpha, px = sheet.read_png(p2)
        check("tRNS gives alpha", alpha is True)
        check("tRNS: index 0 is transparent", px[0] == (231, 255, 255, 0), str(px[0]))
        check("tRNS: index 1 is opaque", px[1] == (96, 132, 167, 255), str(px[1]))

        # and the validator still sees a player colour through the palette
        hits = colors.scan([p[:3] for p in px])
        check("player colour found through the palette",
              hits.get((96, 132, 167)) == 2, str(hits))


def test_png_roundtrip_and_assembly():
    tile = 16  # small, keeps the test fast; layout logic is size-independent
    with tempfile.TemporaryDirectory() as tmp:
        frames = []
        for i, code in enumerate(directions.codes_for(8)):
            p = os.path.join(tmp, "%s.png" % code)
            _solid(p, tile, (i * 10, 5, 7, 255))
            frames.append((code, p))

        # round-trip one of them
        w, h, alpha, px = sheet.read_png(frames[0][1])
        check("png roundtrip", (w, h, alpha) == (tile, tile, True)
              and px[0] == (0, 5, 7, 255), "%s %s" % ((w, h, alpha), px[0]))

        out = os.path.join(tmp, "sheet.png")
        place = sheet.assemble(frames, tile, cols=4, out_path=out)

        check("8 frames placed", len(place) == 8)
        check("row-major 4 cols", place["s"] == (0, 0) and place["se"] == (0, 3)
              and place["n"] == (1, 0) and place["nw"] == (1, 3), str(place))

        sw, sh, _a, spx = sheet.read_png(out)
        check("sheet is 4x2 cells", (sw, sh) == (4 * tile, 2 * tile))
        # cell (1,0) is 'n', the 5th frame -> r = 4*10 = 40
        check("cell content lands in the right cell",
              spx[(1 * tile) * sw + 0] == (40, 5, 7, 255),
              str(spx[(1 * tile) * sw + 0]))

        # a wrongly-sized frame must be rejected, not silently packed
        bad = os.path.join(tmp, "bad.png")
        _solid(bad, tile + 1, (1, 2, 3, 255))
        try:
            sheet.assemble([("s", bad)], tile)
            check("wrong-size frame rejected", False)
        except ValueError:
            check("wrong-size frame rejected", True)


# -------------------------------------------------------------------- datgen
def test_image_block_and_dat():
    place = {"s": (0, 0), "w": (0, 1), "sw": (0, 2), "se": (0, 3)}
    block = datgen.image_block("mytrain", place)
    check("emits engine key order",
          block.splitlines() == [
              "EmptyImage[s]=mytrain.0.0",
              "EmptyImage[w]=mytrain.0.1",
              "EmptyImage[sw]=mytrain.0.2",
              "EmptyImage[se]=mytrain.0.3",
          ], block)

    fb = datgen.image_block("mytrain", {"s": (1, 0)}, freight=True, freight_index=0)
    check("freight key form", fb == "FreightImage[0][s]=mytrain.1.0", fb)

    dat = datgen.vehicle_dat("Test_Loco", block, waytype="track", power=1500)
    check("dat has obj=vehicle", "obj=vehicle" in dat)
    check("dat carries images", "EmptyImage[sw]=mytrain.0.2" in dat)
    check("dat has power", "power=1500" in dat)


def test_freight_variants_emit_freightimagetype():
    """A cargo-variant vehicle needs freightimagetype[i] per freight image.

    Verified against makeobj (the real oracle), which FATALs without them:

        FATAL ERROR: Missing freightimagetype[0] for 3 freight_images!

    (vehicle_writer.cc: it walks freightimagetype[0..N-1] and dies on a gap, and
    each value is written as an obj_good xref, so a typo resolves to nothing at
    game load). So the count and order here MUST track the freightimage[i] blocks.
    """
    tb = datgen.freightimagetype_block(["Kohle", "Oel"])
    check("one line per good, indexed in order",
          tb == "freightimagetype[0]=Kohle\nfreightimagetype[1]=Oel", tb)
    check("no goods -> empty string", datgen.freightimagetype_block([]) == "")

    place = {"s": (0, 0), "w": (0, 1), "sw": (0, 2), "se": (0, 3)}
    empty = datgen.image_block("hop", place)
    f0 = datgen.image_block("hop", {"s": (1, 0)}, freight=True, freight_index=0)
    f1 = datgen.image_block("hop", {"s": (2, 0)}, freight=True, freight_index=1)
    dat = datgen.vehicle_dat("Hopper", empty + "\n" + f0 + "\n" + f1,
                             freight="Kohle", freight_types=["Kohle", "Oel"])
    check("emits freightimagetype[0]", "\nfreightimagetype[0]=Kohle\n" in dat)
    check("emits freightimagetype[1]", "\nfreightimagetype[1]=Oel\n" in dat)
    n_type = dat.count("freightimagetype[")
    n_img = dat.count("FreightImage[0][") and (
        1 + max(int(l.split("[", 2)[1].split("]")[0])
                for l in dat.splitlines() if l.startswith("FreightImage[")))
    check("one freightimagetype per freight index (%d vs %d)" % (n_type, n_img),
          n_type == n_img, dat)


def test_a_vehicle_without_freight_is_byte_identical():
    """Adding freight support must not shift a single byte of a plain vehicle.

    The freightimagetype slot collapses to nothing when freight_types is empty, so
    every vehicle in every existing pakset the kit might regenerate comes out
    exactly as it did before the feature landed.
    """
    block = datgen.image_block("t", {"s": (0, 0), "w": (0, 1)})
    without = datgen.vehicle_dat("Plain", block, waytype="track", power=1500)
    explicit = datgen.vehicle_dat("Plain", block, waytype="track", power=1500,
                                  freight_types=())
    check("freight_types=() is the default", without == explicit)
    check("no freightimagetype line leaks in", "freightimagetype" not in without)
    check("no blank-line churn around payload",
          "\npayload=0\n\n# --- coupling" in without, without)


def test_tunnel_portal_dat():
    """A narrow tunnel: four portal directions, two layers, a mandatory icon.

    Verified against makeobj, which packs it (exit 0). The direction order is the
    writer's own n, s, e, w (tunnel_writer.cc indices[]), NOT the way module's
    n, w, e, s - a portal keyed in the wrong order lands on the wrong hill.
    """
    back = {"n": (0, 0), "s": (0, 1), "e": (0, 2), "w": (0, 3)}
    front = {"n": (1, 0), "s": (1, 1), "e": (1, 2), "w": (1, 3)}

    block = tunnels.image_block("tun", back, front)
    check("back then front, each in n/s/e/w order",
          block.splitlines() == [
              "backimage[n]=tun.0.0", "backimage[s]=tun.0.1",
              "backimage[e]=tun.0.2", "backimage[w]=tun.0.3",
              "frontimage[n]=tun.1.0", "frontimage[s]=tun.1.1",
              "frontimage[e]=tun.1.2", "frontimage[w]=tun.1.3"], block)

    only_back = tunnels.image_block("tun", back)
    check("front is optional", "frontimage" not in only_back and
          only_back.count("backimage") == 4, only_back)

    # all-four-or-none, both layers - a partial set draws the wrong portal
    try:
        tunnels.image_block("tun", {"n": (0, 0), "s": (0, 1), "e": (0, 2)})
        check("partial back is refused", False, "no error raised")
    except ValueError as e:
        check("partial back is refused", "missing w" in str(e), str(e))
    try:
        tunnels.image_block("tun", back, {"n": (1, 0)})
        check("partial front is refused", False, "no error raised")
    except ValueError as e:
        check("partial front is refused", "all four or none" in str(e), str(e))

    ui = tunnels.icon_block("tun", back, icon_dir="s")
    dat = tunnels.tunnel_dat("BKit_Tunnel", block, ui, waytype="track",
                             topspeed=120, cost=50000, maintenance=500)
    check("dat is a tunnel", "obj=tunnel" in dat)
    check("dat carries an icon, or it cannot be built", "\nicon=tun." in dat, dat)
    check("dat carries all four back portals",
          all(("backimage[%s]=" % d) in dat for d in "nsew"), dat)
    check("dat carries all four front portals",
          all(("frontimage[%s]=" % d) in dat for d in "nsew"), dat)

    findings = schema.lint(dat)
    check("the tunnel .dat lints clean", not findings,
          "; ".join(str(f) for f in findings))

    # the linter must catch a tunnel with no icon - the silent unbuildable trap
    without_icon = "\n".join(l for l in dat.splitlines()
                             if not l.startswith("icon="))
    check("the linter catches a tunnel with no icon",
          any(f.level == "error" and "icon" in f.message
              for f in schema.lint(without_icon)),
          "it would ship an unbuildable tunnel in silence")


def test_bridge_dat():
    """A single-height bridge: four image groups, two layers, a mandatory icon.

    Verified against makeobj (exit 0, packs bridge.BKit_Bridge). The groups and
    their directions are the writer's own (bridge_writer.cc names[]): span ns/ew,
    start and ramp n/s/e/w, pillar s/w - read back by position, so a hole shifts
    every image after it onto the wrong piece.
    """
    from core import bridges, schema

    def grp(row0):
        return {"image": {"ns": (row0, 0), "ew": (row0, 1)},
                "start": {"n": (row0 + 1, 0), "s": (row0 + 1, 1),
                          "e": (row0 + 1, 2), "w": (row0 + 1, 3)},
                "ramp": {"n": (row0 + 2, 0), "s": (row0 + 2, 1),
                         "e": (row0 + 2, 2), "w": (row0 + 2, 3)},
                "pillar": {"s": (row0 + 3, 0), "w": (row0 + 3, 1)}}

    back, front = grp(0), grp(4)
    block = bridges.image_block("brg", back, front)
    check("span, start, ramp then pillar, back before front",
          block.splitlines()[:3] == ["backimage[ns]=brg.0.0",
                                      "backimage[ew]=brg.0.1",
                                      "backstart[n]=brg.1.0"], block)
    check("all 24 images (12 back + 12 front)",
          block.count("back") == 12 and block.count("front") == 12, block)

    # a hole in any group is refused - the engine reads by position
    holed = grp(0)
    del holed["start"]["w"]
    try:
        bridges.image_block("brg", holed)
        check("a missing start direction is refused", False, "no error")
    except ValueError as e:
        check("a missing start direction is refused", "missing w" in str(e), str(e))

    ui = bridges.icon_block("brg", back)
    dat = bridges.bridge_dat("BKit_Bridge", block, ui, waytype="track",
                             topspeed=80, cost=200000, maintenance=1000,
                             max_length=8, pillar_distance=2)
    check("dat is a bridge", "obj=bridge" in dat)
    check("dat carries the span, both ways",
          "backimage[ns]=" in dat and "backimage[ew]=" in dat, dat)
    check("dat carries an icon, or it cannot be built", "\nicon=brg." in dat, dat)
    check("dat sets the length and pillar limits",
          "max_length=8" in dat and "pillar_distance=2" in dat, dat)
    check("the bridge .dat lints clean", not schema.lint(dat),
          "; ".join(str(f) for f in schema.lint(dat)))

    without_icon = "\n".join(l for l in dat.splitlines()
                             if not l.startswith("icon="))
    check("the linter catches a bridge with no icon",
          any(f.level == "error" and "icon" in f.message
              for f in schema.lint(without_icon)),
          "it would ship an unbuildable bridge in silence")


def test_dat_has_no_end_of_line_comments():
    """A .dat has NO trailing comments - and the engine dies if you write one.

    tabfile_t::read_line() (dataobj/tabfile.cc) drops a line only when it STARTS
    with '#' or ' '; it never strips a '#' that follows a value. So
    `freight=None   # a note` really does set freight to "None   # a note", and
    the pakset loader then fatals with

        Cannot resolve 'GOOD-None   # a note'

    which is exactly what a real game launch threw at us. Numeric keys mask it
    (atoi stops at the space), so this only ever blows up on string values.
    """
    dat = datgen.vehicle_dat("Test_Loco", datgen.image_block("t", {"s": (0, 0)}),
                             waytype="track", freight="None", engine_type="diesel")
    for n, line in enumerate(dat.splitlines(), 1):
        if "=" not in line or line.startswith("#") or line.startswith(" "):
            continue  # a comment line, or not a key=value at all
        value = line.split("=", 1)[1]
        check("line %d has no trailing comment: %r" % (n, line),
              "#" not in value, "value would become %r" % value)
    check("freight value is exactly 'None'", "\nfreight=None\n" in dat)
    check("engine_type value is exactly 'diesel'", "\nengine_type=diesel\n" in dat)


# ----------------------------------------------------------------- buildings
def test_building_height_step_is_a_whole_tile():
    """obj/gebaeude.cc stacks with `ypos -= raster_width` - a FULL tile_px.

    The tempting mistake is tile_px/2, because that is how tall the ground
    diamond is. Get it wrong and every floor above the first is drawn half a
    cell out.
    """
    from core import buildings

    for tile_px in (64, 128, 256):
        a = buildings.cell_topleft(0, 0, 0, tile_px)
        b = buildings.cell_topleft(0, 0, 1, tile_px)
        check("height step is one full tile_px (tile=%d)" % tile_px,
              a[0] == b[0] and abs((a[1] - b[1]) - tile_px) < 1e-9,
              "%s -> %s" % (a, b))


def test_building_footprint_and_layouts():
    from core import buildings

    check("even layout keeps the footprint", buildings.footprint(3, 2, 0) == (3, 2))
    check("odd layout TRANSPOSES it (l&1 in building_writer.cc)",
          buildings.footprint(3, 2, 1) == (2, 3))

    cells = buildings.cells(2, 1, 0, heights=2)
    check("every tile x height is emitted", len(cells) == 2 * 1 * 2, str(cells))
    check("engine order: y, then x, then height",
          cells == [(0, 0, 0), (0, 0, 1), (1, 0, 0), (1, 0, 1)], str(cells))


def test_building_tiles_step_by_the_engine_projection():
    """Footprint tiles must land where the engine's own projection puts them."""
    from core import buildings, projection

    tile_px = 128
    base = buildings.cell_topleft(0, 0, 0, tile_px)
    for (x, y) in ((1, 0), (0, 1), (2, 3)):
        got = buildings.cell_topleft(x, y, 0, tile_px)
        want = projection.project_engine(x, y, tile_px)
        check("tile (%d,%d) offset == project_engine" % (x, y),
              abs((got[0] - base[0]) - want[0]) < 1e-9
              and abs((got[1] - base[1]) - want[1]) < 1e-9,
              "%s vs %s" % ((got[0] - base[0], got[1] - base[1]), want))


def test_building_canvas_covers_every_cell():
    from core import buildings

    tile_px = 128
    for (sx, sy, heights) in ((1, 1, 1), (1, 1, 4), (3, 2, 3), (2, 4, 2)):
        for layout in range(4):
            w, h, cuts = buildings.canvas_cells(sx, sy, layout, heights, tile_px)
            for (x, y, z), left, top in cuts:
                check("layout %d cell (%d,%d,%d) fits in the %dx%d canvas of a "
                      "%dx%d/%d building" % (layout, x, y, z, w, h, sx, sy, heights),
                      left >= -0.001 and top >= -0.001
                      and left + tile_px <= w + 0.001 and top + tile_px <= h + 0.001,
                      "cell at (%.1f,%.1f)" % (left, top))


def test_building_layout_convention():
    """Layout L turns the model +90*L in Blender, and layout 0's facade faces -Y.

    world/simcity.cc decides a house's layout from the road beside it:
    building_layout[1<<i] == i, and neighbors[] is (0,1), (1,0), (0,-1), (-1,0).
    So layout L means the road - and the facade - is at neighbors[L], which in the
    ENGINE's grid (y grows south) reads south, east, north, west.

    In Blender, where north is +Y, that is -Y, +X, +Y, -X: a step of PLUS 90.

    The sign is the whole point. It used to be -90 here, from a real measurement
    against pak128's res_00_08 (tracking its chimney across the four layouts). The
    measurement was right; it was expressed in the engine's LEFT-handed frame, and
    a rotation changes sense when you reflect the frame it lives in. Every house
    faced away from its street. tests/blender_footprint.py now checks it in pixels.
    """
    from core import buildings, directions, projection

    for L in range(4):
        check("layout %d camera azimuth" % L,
              abs(buildings.layout_azimuth(L)
                  - (projection.WORLD_AZIMUTH_DEG - 90.0 * L)) < 1e-9,
              str(buildings.layout_azimuth(L)))

    # The vehicle base azimuth was MEASURED against a shipped pak128 bus, long
    # before any of this. It has to fall out of the world frame, or the world frame
    # is wrong: a vehicle's nose is +X, "heading south" is -Y, so the model turns
    # -90 and the camera turns +90.
    check("the vehicle base azimuth falls out of the world azimuth",
          abs(directions.BASE_AZIMUTH_DEG
              - projection.world_azimuth(-90.0)) < 1e-9,
          "%s vs %s" % (directions.BASE_AZIMUTH_DEG,
                        projection.world_azimuth(-90.0)))

    # a layout turns the building about the middle of its footprint, not its corner
    check("a 1x1 pivots on its only tile",
          buildings.footprint_centre(1, 1, 0) == (0.0, 0.0))
    check("a 2x1 pivots between its two tiles",
          buildings.footprint_centre(2, 1, 0) == (0.5, 0.0))
    check("and the pivot transposes with the footprint",
          buildings.footprint_centre(2, 1, 1) == (0.0, 0.5))

    # the engine's default layout count (building_writer.cc)
    check("square footprint -> 1 layout", buildings.layouts_for(2, 2) == 1)
    check("oblong footprint -> 2 layouts", buildings.layouts_for(3, 2) == 2)
    check("an explicit count wins", buildings.layouts_for(1, 1, 4) == 4)


def test_ways_orbit_decomposition():
    """Six models, sixteen ribi images, no gaps and no duplicates."""
    from core import projection, ways

    plan = ways.plan()
    check("the six pieces cover every ribi exactly once",
          sorted(r for r, _n, _t in plan) == list(range(16)))

    # the bits are in compass order, so a quarter-turn is a rotate-left
    check("turning north gives east", ways.rotate(ways.NORTH, 1) == ways.EAST)
    check("turning nse gives sew", ways.rotate(0x7, 1) == 0xE)
    check("four turns is a no-op", ways.rotate(0xB, 4) == 0xB)
    check("the code for 5 is ns", ways.code(5) == "ns")
    check("the code for 3 is ne", ways.code(3) == "ne")

    # a turn steps n->e->s->w, which in Blender (+Y north) is MINUS 90 degrees,
    # so the camera goes the other way again
    for t in range(4):
        check("turn %d camera azimuth" % t,
              abs(ways.azimuth_for(t)
                  - (projection.WORLD_AZIMUTH_DEG + 90.0 * t)) < 1e-9)

    check("a road with no cross piece is blind at four-way junctions",
          ways.missing(("none", "end", "straight", "curve", "tee")) == [15])
    check("a road with everything is blind nowhere",
          ways.missing(ways.PIECE_NAMES) == [])


def test_roadsign_index_order():
    """dir + state*4, with dir 0=n 1=s 2=w 3=e - and state 0 is RED.

    Read straight off obj/signal.cc, which asks for get_image_id(3 + state*4) for
    east, (0 + state*4) for north, (2 + ...) for west, (1 + ...) for south. That is
    roadsign_writer's general_sign_directions[] = {n, s, w, e} - NOT compass order,
    and 'fixing' it into n, e, s, w points every sign the wrong way.
    """
    from core import projection, roadsigns

    check("the direction order is n, s, w, e",
          roadsigns.SIGN_DIRS == ("n", "s", "w", "e"))
    check("north is 0", roadsigns.image_index("n") == 0)
    check("south is 1", roadsigns.image_index("s") == 1)
    check("west is 2", roadsigns.image_index("w") == 2)
    check("east is 3", roadsigns.image_index("e") == 3)
    check("a state is a block of four", roadsigns.image_index("e", 1) == 7)

    check("state 0 is RED (obj/roadsign.h:63)", roadsigns.STATE_RED == 0)
    check("state 1 is green", roadsigns.STATE_GREEN == 1)

    # a signal is four images per aspect, in the engine's order
    p = roadsigns.plan(states=2)
    check("a two-aspect signal is eight images", len(p) == 8)
    check("state 0 comes first, north first", p[0] == ("n", 0))
    check("and the second aspect follows whole", p[4] == ("n", 1))

    # the sign is modelled at the north edge and turned, like everything else
    for d, t in (("n", 0), ("e", 1), ("s", 2), ("w", 3)):
        check("%s is %d quarter-turns from north" % (d, t),
              abs(roadsigns.azimuth_for(d)
                  - (projection.WORLD_AZIMUTH_DEG + 90.0 * t)) < 1e-9)


def test_wayobj_is_spelled_with_a_hyphen():
    """obj=way-object. Not way_obj, which is what every other name around it says.

    way_obj_writer.h declares class way_obj_writer_t in way_obj_writer.cc - and then
    get_type_name() returns "way-object". The schema knows because it reads
    get_type_name(); we would have guessed wrong, and did.
    """
    from core import schema, ways

    check("the declared type is way-object", ways.WAYOBJ_TYPE == "way-object")
    check("and the engine knows it", "way-object" in schema.OBJ_TYPES)
    check("while way_obj is not a type at all", "way_obj" not in schema.OBJ_TYPES)

    dat = ways.wayobj_dat("T", "backimage[ns]=x.0.0", "icon=x.0.1")
    check("the emitter spells it right", "obj=way-object" in dat, dat)
    check("and it lints clean", not schema.lint(dat), str(schema.lint(dat)))


def test_schema_reads_every_printf_conversion():
    """%i is not %d, and pretending it is cost us every key of a signal.

    roadsign_writer.cc:45 builds its keys with sprintf(buf, "image[%s][%i]", ...).
    The pattern translator only knew %d and %s, so it recognised NOT ONE of a
    signal's image keys and reported all eight as unknown. The schema had the
    format string all along - it was the reader that was deaf.
    """
    from core import schema

    check("image[n][0] is a key a roadsign reads",
          schema.known_key("roadsign", "image[n][0]"))
    check("image[e][1] too", schema.known_key("roadsign", "image[e][1]"))
    check("and the linter says so",
          not schema.lint("obj=roadsign\nname=T\nicon=x.0.0\nimage[n][0]=x.0.0\n"))


def test_tabfile_parameter_expansion():
    """A .dat key can be a whole family of keys, and real paksets rely on it.

        Image[n,e,s,w][0-1] = classic_signals.0.<4*$1 + $0>

    is EIGHT keys (tabfile_t::find_parameter_expansion). A linter that does not
    expand it reports every one of pak128's signals as unknown - ours did, 33 times,
    all wrong.

    The trap is the leading dash: the engine's test is
    `(*s == ',' || *s == '-') && *(s-1) != '['`, so image[-] - the ribi for "connects
    to nothing" - is a LITERAL, not a range.
    """
    from core import schema

    check("a plain key expands to itself", schema.expand_key("power") == ["power"])
    check("image[-] is a literal, not a range",
          schema.expand_key("image[-]") == ["image[-]"])
    check("a name list expands",
          schema.expand_key("image[n,e,s,w]")
          == ["image[n]", "image[e]", "image[s]", "image[w]"])
    check("a numeric range expands, inclusive",
          schema.expand_key("image[0-2]")
          == ["image[0]", "image[1]", "image[2]"])
    check("two groups make a cross product",
          len(schema.expand_key("image[n,e,s,w][0-1]")) == 8)
    check("and pak128's signals are all known keys",
          all(schema.known_key("roadsign", k)
              for k in schema.expand_key("image[n,e,s,w][0-1]")))


def test_a_comment_after_an_image_is_legal():
    """'#' after a value is only fatal where the engine reads the value as TEXT.

    image_writer.cc:340, the engine's own comment on the image syntax:
        "after the dots also spaces and comments are allowed"

    A number swallows it too, because atoi() stops at the first non-digit. Only a
    text value keeps it - and then `freight=None  # a note` really does become
    "None  # a note" and the pakset loader dies on it. That is the one that cost us
    an evening; the other two are not worth a word.

    Calling all three an error reported 97 false alarms on pak128. A linter that
    cries wolf gets turned off.
    """
    from core import schema

    def errors(dat):
        return [f for f in schema.lint(dat) if f.level == "error"]

    text = "obj=vehicle\nname=T\nfreight=None  # nothing to carry\n"
    check("a comment on a TEXT value is an error",
          any("end-of-line" in f.message for f in errors(text)), str(errors(text)))

    img = "obj=menu\nname=T\nimage[0]=> wkz_icons.4.0\t# landscape\n"
    check("a comment on an IMAGE value is not - the engine allows it",
          not any("end-of-line" in f.message for f in errors(img)), str(errors(img)))

    num = "obj=vehicle\nname=T\npower=600  # horses\n"
    check("a comment on a NUMBER is not either - atoi stops at the space",
          not any("end-of-line" in f.message for f in errors(num)), str(errors(num)))


def test_keys_hidden_in_a_char_buffer():
    """Some keys never appear in an obj.get("...") and are never sprintf'd either.

    factory_writer.cc:291 declares a char BUFFER and then pokes a digit into it:

        char str_smoketile[] = "smoketile[0]";
        ...
        str_smoketile[10] = '0' + i;
        pos_off[i] = obj.get_koord( str_smoketile, koord(0,0) );

    No regex over obj.get() will see that key, and no regex over sprintf will
    either. The literal in the initialiser is the only trace it leaves.

    This is not a hypothetical. Without it the linter reported all thirteen of
    pak128's smoking factories as writing a key the engine ignores. They are
    correct - makeobj reads smoketile[0..3] - and we came within an inch of
    publishing it as a pakset bug. makeobj settled it: compiling bakery.dat with and
    without the index puts the same coordinates in the .pak, and flips the
    num_smoke_offsets byte.
    """
    from core import schema

    for i in range(4):
        check("a factory reads smoketile[%d]" % i,
              schema.known_key("factory", "smoketile[%d]" % i))
        check("a factory reads smokeoffset[%d]" % i,
              schema.known_key("factory", "smokeoffset[%d]" % i))

    dat = ("obj=factory\nname=Bakery\nsmoke=smoke1\n"
           "smoketile[0]=0,2\nsmokeoffset[0]=4,-57\n")
    check("and pak128's spelling lints clean", not schema.lint(dat),
          str(schema.lint(dat)))


def test_an_unknown_obj_type_is_reported_once():
    """A file full of one unknown type is ONE mistake, not twenty-four findings."""
    from core import schema

    dat = "\n".join("obj=program_text\nname=T%d\n----" % i for i in range(24))
    bad = [f for f in schema.lint(dat) if "unknown obj type" in f.message]
    check("one finding, not twenty-four", len(bad) == 1, str(len(bad)))
    check("and it says how many", "24 objects" in bad[0].message, bad[0].message)


def test_writers_delegate_their_keys():
    """obj=factory reads every key obj=building reads.

    factory_writer.cc:225 hands the whole tabfileobj to building_writer_t, which
    then reads its own keys out of it. Miss that and the linter cries wolf on every
    factory in the pakset - it did, 1622 times on pak128.
    """
    from core import schema

    fac = schema.OBJ_TYPES["factory"]
    check("the schema records the delegation",
          "building" in fac["delegates_to"], str(fac["delegates_to"]))
    for key in ("dims", "level", "intro_year"):
        check("a factory reads the building key %r" % key,
              schema.known_key("factory", key))
    check("and the whole image grid too",
          schema.known_key("factory", "backimage[0][0][0][0][0]"))

    # crossing keeps its key prefixes in literals and then indexes them, so the
    # format "%s[%i]" is only half the story (crossing_writer.cc:28)
    check("a crossing reads openimage[ns][0]",
          schema.known_key("crossing", "openimage[ns][0]"))
    check("and front_closedimage[ew][3]",
          schema.known_key("crossing", "front_closedimage[ew][3]"))


def test_no_icon_no_object():
    """A way with no icon= loads, compiles, and cannot be built by anyone.

    builder/wegbauer.cc:123 only makes the build tool if the cursor skin has an
    icon; otherwise it sets the builder to NULL. The same line is in wayobj.cc,
    roadsign.cc, brueckenbauer.cc and tunnelbauer.cc. makeobj says nothing, the
    pakset loads, and the object is simply not in the game. We found it by laying
    the road in a real game and being told there was no such road.
    """
    from core import schema

    dat = "obj=way\nname=Test_Road\nwaytype=road\nimage[-]=x.0.0\n"
    findings = schema.lint(dat)
    check("the linter flags a way with no icon",
          any(f.level == "error" and "icon" in f.message for f in findings),
          str(findings))

    ok = schema.lint(dat + "icon=x.0.1\n")
    check("and is happy once the icon is there",
          not any("icon" in f.message for f in ok), str(ok))

    # PER OBJECT, not per type. Two ways in one file, the first with an icon and the
    # second without: the second is unbuildable and used to be masked, because the
    # icon flag was keyed by obj type and the two shared it.
    two = ("obj=way\nname=Has_Icon\nwaytype=road\nimage[-]=a.0.0\nicon=a.0.1\n"
           "obj=way\nname=No_Icon\nwaytype=road\nimage[-]=b.0.0\n")
    findings = schema.lint(two)
    icon_errors = [f for f in findings if f.level == "error" and "icon" in f.message]
    check("a second icon-less way of the same type is still caught",
          len(icon_errors) == 1, "%d icon errors: %s" % (len(icon_errors), findings))
    check("...and it points at the SECOND object, not the first",
          icon_errors and "No_Icon" not in two[:two.rindex("obj=way")]
          and icon_errors[0].line > two[:two.rindex("obj=way")].count("\n"),
          str(icon_errors))


def test_linter_survives_malformed_input():
    """A broken key must not take down the scan of a whole pakset.

    image[0-] - a range with no upper bound - fed int('') to range() and raised
    ValueError, killing the lint of every file after it. A group the expander
    cannot parse is now left as the literal it is, so the scan survives. (Whether
    that literal is then reported is a separate rule; here we only prove no crash.)
    """
    from core import schema

    dat = "obj=way\nname=Broken\nwaytype=road\nimage[-]=x.0.0\nimage[0-]=x.0.1\n"
    try:
        schema.lint(dat)
        crashed = False
    except Exception as e:               # noqa: BLE001 - the point is "any exception"
        crashed = repr(e)
    check("a malformed range does not crash the linter", crashed is False, crashed)

    # a genuine unknown key is still reported - the malformed one is not a regression
    # in that rule, it is simply accepted as an image pattern
    findings = schema.lint("obj=way\nname=X\nwaytype=road\nimage[-]=x.0.0\n"
                           "icon=x.0.1\nnosuchkey=9\n")
    check("an unknown key is still flagged",
          any("nosuchkey" in f.message for f in findings), str(findings))

    # the expander itself, directly
    check("expand_key leaves an unparseable range whole",
          schema.expand_key("image[0-]") == ["image[0-]"],
          str(schema.expand_key("image[0-]")))


def test_linter_validates_integer_values():
    """A key the engine reads with atoi() must be given an integer.

    atoi never fails - it stops at the first non-digit and returns 0 or a prefix -
    so power=abc is silently 0, cost=1,000 is silently 1, level=2.5 is silently 2,
    and makeobj says nothing. The schema already knows which keys are integers.
    """
    from core import schema

    def has_int_error(value):
        dat = "obj=vehicle\nname=X\npower=%s\nimage[1]=x.0.0\n" % value
        return any("is not an integer" in f.message and f.level == "error"
                   for f in schema.lint(dat))

    for bad in ("abc", "1,000", "2.5", "12px", ""):
        if bad == "":
            continue                     # an empty value is a different shape of odd
        check("power=%s is caught" % bad, has_int_error(bad), bad)

    for good in ("120", "-9", "+3", "250000", "0"):
        check("power=%s is accepted" % good, not has_int_error(good), good)

    # and it must not fire on a NON-integer key: name=abc is perfectly fine
    check("a string key is not held to integer syntax",
          not any("is not an integer" in f.message
                  for f in schema.lint("obj=vehicle\nname=abc123\nimage[1]=x.0.0\n")))


def test_grid_placement_is_pure():
    """The sheet placement depends only on key order and column count.

    It reads no pixels - which is what makes it possible one day to rewrite a .dat
    without re-rendering, since the .dat only ever names a cell by (row, col).
    """
    from core import sheet

    keys = ["a", "b", "c", "d", "e"]
    p = sheet.grid_placement(keys, cols=2)
    check("row-major, wraps at cols",
          p == {"a": (0, 0), "b": (0, 1), "c": (1, 0), "d": (1, 1), "e": (2, 0)},
          str(p))

    # tuple keys (buildings, wayobj) survive unchanged
    tkeys = [(0, 0), (0, 1), (1, 0)]
    check("tuple keys are kept as-is",
          sheet.grid_placement(tkeys, cols=2) == {(0, 0): (0, 0), (0, 1): (0, 1),
                                                  (1, 0): (1, 0)})

    # and it is exactly what assemble() puts out, so the two never drift
    check("cols defaults to one row", sheet.grid_placement(keys) ==
          {k: (0, i) for i, k in enumerate(keys)})


def test_findings_carry_codes_and_can_be_suppressed():
    """Every finding has a stable code, and a file can silence one by that code."""
    from core import schema

    dat = "obj=way\nname=X\nwaytype=road\nimage[-]=x.0.0\n"     # no icon
    findings = schema.lint(dat)
    check("the finding has a code", findings and findings[0].code == "no-icon",
          str([(f.level, f.code) for f in findings]))
    check("every finding carries a non-empty code",
          all(f.code for f in findings), str(findings))
    check("as_dict exposes it",
          findings[0].as_dict()["code"] == "no-icon", str(findings[0].as_dict()))

    silenced = schema.lint("# bkit: ignore=no-icon\n" + dat)
    check("the ignore pragma silences that code",
          not any(f.code == "no-icon" for f in silenced), str(silenced))

    # a pragma for a DIFFERENT code leaves this one alone
    other = schema.lint("# bkit: ignore=dup-key\n" + dat)
    check("an unrelated ignore does not silence it",
          any(f.code == "no-icon" for f in other), str(other))

    # comma-separated, and forgiving of spacing
    two = ("obj=way\nname=A\nwaytype=road\nimage[-]=a.0.0\n"
           "waytype=road\n")                                     # dup + no icon
    both = schema.lint("#  bkit: ignore = no-icon , dup-key\n" + two)
    check("several codes can be silenced at once",
          not both, str(both))


def test_building_image_block():
    from core import buildings, schema

    place = {(0, 0, 0, 0): (0, 0), (0, 0, 0, 1): (0, 1)}
    block = buildings.image_block("house", place)
    check("BackImage[layout][y][x][h][phase]",
          block.splitlines() == ["BackImage[0][0][0][0][0]=house.0.0",
                                 "BackImage[0][0][0][1][0]=house.0.1"], block)

    # canonical key is (layout, x, y, h, phase, season)
    seasoned = buildings.image_block("house", {(0, 0, 0, 0, 0, 0): (0, 0),
                                               (0, 0, 0, 0, 0, 1): (0, 1)})
    check("a season adds a sixth index",
          seasoned.splitlines() == ["BackImage[0][0][0][0][0][0]=house.0.0",
                                    "BackImage[0][0][0][0][0][1]=house.0.1"], seasoned)

    animated = buildings.image_block("house", {(0, 0, 0, 0, 0, 0): (0, 0),
                                               (0, 0, 0, 0, 1, 0): (0, 1)})
    check("a phase is the FIFTH index, before the season",
          animated.splitlines() == ["BackImage[0][0][0][0][0]=house.0.0",
                                    "BackImage[0][0][0][0][1]=house.0.1"], animated)

    try:
        buildings.image_block("house", {(0, 0, 0): (0, 0)})
        check("a malformed key is rejected", False)
    except ValueError:
        check("a malformed key is rejected", True)

    dat_anim = buildings.building_dat("H", animated, dims="1,1", level=1,
                                      animation_time=250)
    check("animation_time lands in the dat",
          "animation_time=250" in dat_anim.splitlines(), dat_anim)
    check("and it still lints clean", not schema.lint(dat_anim),
          str(schema.lint(dat_anim)))

    dat = buildings.building_dat("H", block, btype="res", dims="1,1", level=3)
    check("it is a building", "obj=building" in dat and "type=res" in dat)
    check("and it lints clean against the engine schema", not schema.lint(dat),
          str(schema.lint(dat)))


def test_station_and_depot_buildings():
    """A stop and a depot are obj=building with a type and a waytype.

    Verified against makeobj (exit 0, packs building.BKit_Stop). A stop needs its
    waytype (building_writer.cc reads it) and enables_* for what it accepts; a
    plain building emits neither and so comes out byte-for-byte as before.
    """
    from core import buildings, schema

    check("station block is empty for a plain building",
          buildings.station_block("", ()) == "")
    check("station block emits waytype and enables in order",
          buildings.station_block("track", ["pax", "ware"])
          == "waytype=track\nenables_pax=1\nenables_ware=1",
          buildings.station_block("track", ["pax", "ware"]))

    place = {(0, 0, 0, 0, 0, 0): (0, 0)}
    block = buildings.image_block("stn", place)

    plain = buildings.building_dat("H", block, btype="res", dims="1,1", level=3)
    plain2 = buildings.building_dat("H", block, btype="res", dims="1,1", level=3,
                                    waytype="", enables=())
    check("adding stop support does not shift a plain building", plain == plain2)

    icon = buildings.icon_ref("stn", place)
    check("icon reference is the base tile", icon == "stn.0.0", icon)

    stop = buildings.building_dat("BKit_Stop", block, btype="stop", dims="1,1",
                                  level=2, waytype="track", enables=["pax", "post"],
                                  icon=icon)
    check("stop has type and waytype",
          "\ntype=stop\n" in stop and "\nwaytype=track\n" in stop, stop)
    check("stop enables passengers and mail",
          "\nenables_pax=1\n" in stop and "\nenables_post=1\n" in stop, stop)
    # hausbauer.cc:235: a stop whose icon is empty gets a NULL builder and cannot
    # be placed - the silent unbuildable trap, the same as a way with no icon
    check("stop carries an icon, or it cannot be built",
          "\nicon=stn.0.0\n" in stop and "\ncursor=stn.0.0\n" in stop, stop)
    check("stop lints clean", not schema.lint(stop), str(schema.lint(stop)))

    depot = buildings.building_dat("BKit_Depot", block, btype="depot", dims="1,1",
                                   level=1, waytype="track", icon=icon)
    check("depot has type, waytype and icon",
          "\ntype=depot\n" in depot and "\nwaytype=track\n" in depot
          and "\nicon=" in depot, depot)
    check("depot lints clean", not schema.lint(depot), str(schema.lint(depot)))

    # and a plain building must still be byte-identical - no icon, no waytype
    check("a plain building gets no icon", "icon=" not in plain, plain)


def test_seasons_and_the_third_image_trap():
    """The engine's effective_season table throws a third season image away.

    obj/gebaeude.cc:
        effective_season[][5] = {{0,0,0,0,0}, {0,0,0,0,1}, {0,0,0,0,1},
                                 {0,1,2,3,2}, {0,1,2,3,4}}
    The row for THREE images is a byte-for-byte copy of the row for two, so the
    third is never drawn. An artist can paint it and never see it, and makeobj
    says nothing. The linter has to.
    """
    from core import buildings, schema

    check("1,2,4,5 are the counts worth using",
          buildings.USEFUL_SEASON_COUNTS == (1, 2, 4, 5))
    check("with two images the second is SNOW, not winter",
          buildings.SEASON_MEANING[2] == ("all year", "snow"))
    check("with three, the third is never drawn",
          buildings.SEASON_MEANING[3][2] == "NEVER DRAWN")
    check("summer is season 0 (simworld.cc: 'summer always zero')",
          buildings.SEASON_SUMMER == 0 and buildings.SEASON_NAMES[0] == "summer")

    def dat_with(n_seasons):
        place = {(0, 0, 0, 0, 0, s): (0, s) for s in range(n_seasons)}
        return buildings.building_dat("H", buildings.image_block("h", place),
                                      dims="1,1", level=1)

    for n in (1, 2, 4, 5):
        check("%d season images: no complaint" % n, not schema.lint(dat_with(n)),
              str(schema.lint(dat_with(n))))

    f = schema.lint(dat_with(3))
    check("3 season images: the linter warns", len(f) == 1 and f[0].level == "warning",
          str(f))
    check("...and says the third is never drawn",
          "NEVER draws the third" in f[0].message, f[0].message if f else "")


# -------------------------------------------------------------------- schema
def test_schema_came_from_the_engine():
    from core import schema

    check("engine version recorded", schema.ENGINE_VERSION.count(".") >= 1,
          schema.ENGINE_VERSION)
    check("the obj= types the engine accepts",
          {"vehicle", "building", "way", "roadsign", "bridge", "tunnel", "factory",
           "tree", "good"} <= set(schema.TOP_LEVEL), str(schema.TOP_LEVEL))
    check("internal writers are not offerable as obj=",
          "imagelist" not in schema.TOP_LEVEL and "xref" not in schema.TOP_LEVEL)
    check("hundreds of keys, not a hand-written handful",
          sum(len(t["keys"]) for t in schema.OBJ_TYPES.values()) > 300)

    # keys are case-insensitive: tabfile.cc lowercases every one it reads
    check("EmptyImage[sw] is known", schema.known_key("vehicle", "EmptyImage[sw]"))
    check("FreightImage[2][nw] is known",
          schema.known_key("vehicle", "FreightImage[2][nw]"))
    check("payload is a vehicle key", schema.known_key("vehicle", "payload"))
    check("payload is NOT a building key",
          not schema.known_key("building", "payload"))
    check("name is common to everything", schema.known_key("building", "name")
          and schema.known_key("vehicle", "name"))


def test_linter_is_quiet_on_our_own_output():
    from core import datgen, schema

    block = datgen.image_block("t", {"s": (0, 0), "w": (0, 1)})
    dat = datgen.vehicle_dat("Test", block, waytype="track", power=1500)
    findings = schema.lint(dat)
    check("our generated .dat lints clean", not findings,
          "; ".join(str(f) for f in findings))


def test_linter_catches_the_silent_killers():
    """The two failure modes makeobj does NOT warn about, and one it barely does."""
    from core import schema

    def one(text, level=None):
        f = schema.lint(text)
        return [x for x in f if level is None or x.level == level]

    # 1. the end-of-line comment that cost us a working game
    f = one("obj=vehicle\nname=X\nfreight=None   # a note\n", "error")
    check("catches the end-of-line comment", len(f) == 1 and "comment" in f[0].message,
          str(f))

    # 2. an indented key is DROPPED by the engine, silently
    f = one("obj=vehicle\nname=X\n    power=600\n", "error")
    check("catches the indented key", len(f) == 1 and "indent" in f[0].message.lower(),
          str(f))

    # 3. a typo
    f = one("obj=vehicle\nname=X\npaylaod=40\n", "warning")
    check("catches a typo'd key", len(f) == 1 and "paylaod" in f[0].message, str(f))

    # 4. a key that is real, but belongs to another object type - and SAY so
    f = one("obj=vehicle\nname=X\nclimates=all\n", "warning")
    check("catches a key from the wrong obj type", len(f) == 1, str(f))
    check("...and names the type that does read it",
          "obj=building" in f[0].message, f[0].message if f else "")

    # 5. an obj= the engine never heard of
    f = one("obj=locomotive\nname=X\n", "error")
    check("catches an unknown obj type", len(f) == 1 and "locomotive" in f[0].message,
          str(f))

    # and none of that fires on a clean file
    check("clean .dat is silent",
          not one("obj=vehicle\nname=X\npower=600\nEmptyImage[s]=x.0.0\n"))


# -------------------------------------------------------------- translations
#
# addon/ui.py is parsed, not imported: importing it needs bpy. ast gives us the
# string literals exactly as Python sees them, including implicit concatenation
# across lines, which a plain text search would miss.

_UI_PY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "addon", "ui.py")

# Not prose, so not translated: the add-on's own name.
_UNTRANSLATED = {"Simutrans"}


def _ui_ast():
    import ast
    with open(_UI_PY, encoding="utf-8") as f:
        return ast.parse(f.read())


def _all_ui_strings():
    import ast
    return {n.value for n in ast.walk(_ui_ast())
            if isinstance(n, ast.Constant) and isinstance(n.value, str)}


def _ui_user_facing_strings():
    """Strings the panel shows: _() calls, bl_label/bl_description, and the
    name=/description=/text= keywords."""
    import ast
    out = set()
    for n in ast.walk(_ui_ast()):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == "_"):
            for a in n.args:
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    out.add(a.value)
        if isinstance(n, ast.Call):
            for kw in n.keywords:
                if (kw.arg in ("name", "description", "text")
                        and isinstance(kw.value, ast.Constant)
                        and isinstance(kw.value.value, str)):
                    out.add(kw.value.value)
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if (isinstance(t, ast.Name) and t.id in ("bl_label", "bl_description")
                        and isinstance(n.value, ast.Constant)):
                    out.add(n.value.value)
    return out - _UNTRANSLATED


def _placeholders(s):
    """The %-conversions in a format string, in order: '%d px' -> ('d',)."""
    import re
    return tuple(re.findall(r"%[-#0 +]*[0-9.*]*([diouxXeEfFgGcrsa%])", s))


def test_every_ui_string_is_declared_for_translation():
    from addon import translations

    declared = set(translations.SOURCE_STRINGS)
    shown = _ui_user_facing_strings()

    missing = shown - declared
    check("no user-facing string is missing from SOURCE_STRINGS",
          not missing, "untranslatable: %s" % sorted(missing))

    # and nothing declared that the UI no longer shows
    literals = _all_ui_strings()
    stale = declared - literals
    check("SOURCE_STRINGS has no stale entries", not stale,
          "not in ui.py any more: %s" % sorted(stale))


def test_translations_are_complete_and_safe():
    from addon import translations

    declared = set(translations.SOURCE_STRINGS)
    check("Spanish exists", "es" in translations.LANGUAGES)

    for locale, table in translations.LANGUAGES.items():
        missing = declared - set(table)
        check("%s translates every string" % locale, not missing,
              "missing: %s" % sorted(missing))

        invented = set(table) - declared
        check("%s invents nothing" % locale, not invented,
              "not a UI string: %s" % sorted(invented))

        # A translation that drops or reorders a %d crashes at runtime, in the
        # user's language only - exactly the bug nobody hits before shipping.
        for src, dst in table.items():
            check("%s keeps the format specifiers of %r" % (locale, src[:32]),
                  _placeholders(src) == _placeholders(dst),
                  "%s vs %s" % (_placeholders(src), _placeholders(dst)))

        for src, dst in table.items():
            check("%s actually translates %r" % (locale, src[:32]),
                  dst.strip() != "", "empty translation")


def test_blender_translation_dict_shape():
    from addon import translations

    d = translations.as_blender_dict()
    check("keyed by locale", set(d) == set(translations.LANGUAGES))
    for locale, table in d.items():
        for key in table:
            check("%s key is (our context, msgid)" % locale,
                  isinstance(key, tuple) and len(key) == 2
                  and key[0] == translations.CONTEXT,
                  str(key))
            break   # shape is uniform; one is enough per locale


def test_every_ui_string_declares_our_translation_context():
    """A string drawn without CTX falls into Blender's shared catalogue.

    That is not a style point. Blender already translates "Engine" - as its
    RENDER engine - so `name="Engine"` in the default context showed up in the
    panel as "Motor de procesamiento" instead of our "Motor". And operator labels
    are looked up in the "Operator" context, not the default one, so the buttons
    stayed English while the rest of the panel turned Spanish. Both bugs were
    real; this test is what stops them coming back.
    """
    import ast

    tree = _ui_ast()

    for node in ast.walk(tree):
        # every property that has a name= must also carry translation_context=CTX
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id.endswith("Property"):
            kw = {k.arg for k in node.keywords}
            if "name" in kw:
                check("%s(name=...) declares translation_context" % node.func.id,
                      "translation_context" in kw,
                      ast.dump(node)[:90])

        # every Operator / Panel class must declare bl_translation_context
        if isinstance(node, ast.ClassDef):
            attrs = {t.id for n in node.body if isinstance(n, ast.Assign)
                     for t in n.targets if isinstance(t, ast.Name)}
            if "bl_label" in attrs:
                check("class %s declares bl_translation_context" % node.name,
                      "bl_translation_context" in attrs)

        # every layout.label(text=...) must pass text_ctxt
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "label":
            kw = {k.arg for k in node.keywords}
            if "text" in kw:
                check("layout.label() passes text_ctxt", "text_ctxt" in kw,
                      ast.dump(node)[:90])


# ---------------------------------------------------------------- night
def test_night_is_the_engines_arithmetic():
    """Every branch of calc_base_pal_from_night_shift(), checked against the source.

    display/simgraph16.cc runs THREE different paths and they do not resemble each
    other. Getting any one of them wrong makes a preview that lies, which is worse
    than no preview at all - an artist would trust it.
    """
    # 1. A LIGHT is a blend between the two tables, at full brightness (line 1926).
    #    At deep night it lands exactly on the night entry - no scaling, no rounding.
    for day, nite, _what in colors.LIGHTS:
        check("light %s -> its night entry at night=4" % (day,),
              night.shade(day, 4) == nite,
              "got %s, want %s" % (night.shade(day, 4), nite))
        check("light %s is untouched at noon" % (day,), night.shade(day, 0) == day)

    # the halfway house, the way the engine writes it: (day*2 + night*2) >> 2
    mid = night.shade(colors.WINDOW_DARK, 2)
    want = tuple((colors.WINDOW_DARK[i] * 2 + colors.LIGHTS[0][1][i] * 2) >> 2
                 for i in range(3))
    check("a light at night=2 is the engine's integer blend", mid == want,
          "got %s, want %s" % (mid, want))

    # 2. AN ORDINARY PIXEL is quantised to 555 and then scaled - R,G by 0.75^n and
    #    B by 0.83^n. Blue falls slower: that is why night goes cold, not just dim.
    grey = night.shade((200, 200, 200), 4)
    rg, b = night.multipliers(4)
    want = (int((200 & 0xF8) * rg), int((200 & 0xF8) * rg), int((200 & 0xF8) * b))
    check("ordinary pixel is 555-quantised, then scaled", grey == want,
          "got %s, want %s" % (grey, want))
    check("and blue survives night better than red", grey[2] > grey[0])

    # 3. A PLAYER COLOUR darkens too, but from its 888 value: it is an index in the
    #    pak, so it never meets the 555 quantiser (simgraph16.cc:1891).
    pc = colors.PLAYER_RAMP_BLUE[3]
    check("player colour is scaled from its 888 value",
          night.shade(pc, 3) == night._scale(pc, *night.multipliers(3)))

    # and the whole reason the Civia's glass had to be exact: one count off the
    # engine's colour and the pixel is ordinary paint, which goes dark.
    almost = (colors.WINDOW_DARK[0] - 1, colors.WINDOW_DARK[1], colors.WINDOW_DARK[2])
    check("a window one count out does NOT light up",
          night.shade(almost, 4) != night.shade(colors.WINDOW_DARK, 4))
    check("it just gets dark, like paint",
          sum(night.shade(almost, 4)) < sum(almost))


def test_a_non_darkening_grey_is_not_a_light():
    """The engine's light table holds five greys whose night entry IS their day one.

    They hold their brightness; they do not glow. Counting them as lights would tell
    an artist their train lights up when it does not - so lights_in() drops them.
    """
    grey = colors.LIGHTS[5][0]
    check("the grey is in the engine's light table", grey in colors.LIGHT_DAY)
    check("it does not change at night", night.shade(grey, 4) == grey)
    check("and lights_in() does not call it a light",
          night.lights_in([grey + (255,)]) == {})
    check("while a real window IS one",
          night.lights_in([colors.WINDOW_DARK + (255,)]) ==
          {colors.WINDOW_DARK: 1})


def test_night_preview_writes_a_sheet():
    px = [colors.WINDOW_DARK + (255,), (200, 200, 200, 255),
          (0, 0, 0, 0), colors.HEADLIGHT + (255,)]
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "day.png")
        dst = os.path.join(tmp, "night.png")
        sheet.write_png(src, 2, 2, px, has_alpha=True)
        hits = night.preview(src, dst, night=4)

        check("the two lights are reported", len(hits) == 2, str(hits))
        _w, _h, alpha, got = sheet.read_png(dst)
        check("alpha survives", alpha and got[2][3] == 0)
        check("the window is now the engine's night colour",
              got[0][:3] == colors.LIGHTS[0][1])
        check("the grey went dark", got[1][0] < 200)


# ---------------------------------------------------------------- convoy
def test_convoy_joint_arithmetic():
    check("equal lengths need no offsets at all",
          convoy.art_offsets([8, 8, 8, 8, 8]) == [0, 0, 0, 0, 0])
    check("and have no joints to close", convoy.joint_gaps([8, 8, 8]) == [0, 0])

    # the Civia, as first built, from the prototype's real metres
    gaps = convoy.joint_gaps([14, 11, 13, 9])
    check("a long car followed by a short one opens a hole", gaps[0] == 1.5)
    check("a short car followed by a long one overlaps", gaps[1] == -1.0)

    # one tile of travel is (tile_px/2, tile_px/4) on screen, so the distance ALONG
    # the way is tile_px*sqrt(5)/4 = 71.55 px at 128, not 128. This is the factor of
    # two that makes a predicted gap wrong.
    check("along-track px uses the 2:1 diamond, not the tile width",
          abs(convoy.along_track_px(1.5, 128) - 6.7) < 0.05,
          "%.2f" % convoy.along_track_px(1.5, 128))
    check("and its x component is half the tile per tile",
          abs(convoy.screen_dx_px(2, 128) - 8.0) < 1e-9)


def test_convoy_offsets_predict_pak128s_own_art():
    """The formula, checked against art somebody else drew years ago.

    pak128's Skoda 19 Tr is a three-car articulated trolleybus of lengths 8, 4, 4.
    These are the measured ink centres of its `e` heading, cell by cell, straight off
    the sheet pak128 ships (vehicles/road-psg+mail/skoda_19_tr*.png):

        front  45.0 px      middle  53.5 px      rear  53.0 px

    If the engine really trails each car by the length of the one in FRONT, the art
    of car i has to sit (L[i-1]-L[i])/2 carunits forward of centre, cumulatively.
    That predicts the middle car at +8.0 px and the rear at +8.0 px relative to the
    front. Measured: +8.5 and +8.0.

    We very nearly shipped a linter rule calling those two cars a bug.
    """
    measured = [45.0, 53.5, 53.0]
    offsets = convoy.art_offsets([8, 4, 4])
    check("the offsets are cumulative, not per-joint", offsets == [0.0, 2.0, 2.0])

    for i, off in enumerate(offsets):
        want = convoy.screen_dx_px(off, 128)
        got = measured[i] - measured[0]
        check("Skoda car %d: predicted %+.1f px, pak128 drew %+.1f" % (i, want, got),
              abs(want - got) <= 1.0)


# ---------------------------------------------------------------- tabfile
def test_a_key_said_twice_is_a_key_said_once():
    """tabfile.cc:74 - put() keeps the FIRST value and drops the rest.

    pak128's horses.dat says waytype=road and then waytype=bio, and `bio` is not a
    waytype: get_waytype.cc calls dbg->fatal() on anything it does not know. If the
    engine read the second line, makeobj could not compile the file - and it does,
    exit 0. So the second line is dead, the horses are fine, and a linter that reads
    it is the thing that is broken. Ours was.
    """
    dat = ("obj=vehicle\n"
           "name=Horse\n"
           "waytype=road\n"
           "waytype=bio\n")
    findings = schema.lint(dat)
    check("the dead line is NOT an error - makeobj compiles this",
          not [f for f in findings if f.level == "error"],
          str(findings))
    dups = [f for f in findings if "already set" in f.message]
    check("but it is reported as dead", len(dups) == 1, str(findings))
    check("and it points at the line that wins", "line 3" in dups[0].message)
    check("naming the value that wins", "'road'" in dups[0].message)

    # a key used once in each of two objects is not a duplicate
    two = "obj=vehicle\nname=A\nwaytype=road\n---\nobj=vehicle\nname=B\nwaytype=road\n"
    check("the tally resets at the object separator",
          not [f for f in schema.lint(two) if "already set" in f.message])


def test_forced_chains_are_what_the_depot_builds():
    dat = ("obj=vehicle\nname=Cab\nlength=8\nConstraint[Next][0]=Mid\n"
           "---\n"
           "obj=vehicle\nname=Mid\nlength=4\nConstraint[Prev][0]=Cab\n"
           "Constraint[Next][0]=Tail\n"
           "---\n"
           "obj=vehicle\nname=Tail\nlength=4\nConstraint[Prev][0]=Mid\n"
           "Constraint[Next][0]=none\n")
    vs = schema.vehicles_in(dat)
    check("three vehicles, with their lengths", [v.length for v in vs] == [8, 4, 4])
    check("'none' is not a successor", vs[2].next == [])

    chains = schema.chains(vs)
    check("one chain", len(chains) == 1, str(chains))
    check("head to tail, in order",
          [v.name for v in chains[0]] == ["Cab", "Mid", "Tail"])
    check("and it needs the Skoda's offsets",
          convoy.art_offsets([v.length for v in chains[0]]) == [0.0, 2.0, 2.0])

    # a vehicle that takes ANY follower is not a forced chain: what comes next is the
    # player's choice, so there is nothing to line up in advance
    loose = "obj=vehicle\nname=Loco\nlength=8\n---\nobj=vehicle\nname=Van\nlength=6\n"
    check("no constraints, no chain", schema.chains(schema.vehicles_in(loose)) == [])


# ---------------------------------------------------------------- spec
def _fact(**kw):
    base = {"value": 1, "kind": "measured", "source": "https://example.org/x"}
    base.update(kw)
    return {"name": "T", "facts": {"speed": base}}


def test_a_number_with_no_source_does_not_reach_the_dat():
    """The rule that would have caught the infographic.

    We were handed longitud=13200, potencia=2000, vel_max=140, intro_year=2009 by an
    image model, in the same confident voice it would have used had it read them off
    the builder's plate. The real 465 is 2200 kW, 120 km/h, 2004. A .pak full of
    confident nonsense compiles perfectly, runs perfectly, and is wrong - so the
    check cannot be "be careful", it has to be mechanical.
    """
    for bad in (None, "", "   "):
        try:
            spec.Spec(_fact(source=bad))
            check("a source of %r is refused" % bad, False)
        except spec.SpecError as e:
            check("a source of %r is refused" % bad, "no source" in str(e))

    # and the specific shrugs, by name
    for bad in ("chatgpt", "AI", "an LLM said so", "obvious", "typical", "guess"):
        try:
            spec.Spec(_fact(source=bad))
            check("%r is refused as a source" % bad, False)
        except spec.SpecError as e:
            check("%r is refused as a source" % bad, "not a source" in str(e))

    # derived arithmetic has to show its working
    try:
        spec.Spec(_fact(kind="derived", source="speed"))
        check("derived without a formula is refused", False)
    except spec.SpecError as e:
        check("derived without a formula is refused", "formula" in str(e))

    good = spec.Spec(_fact(kind="derived", source="power", formula="2200 / 4"))
    check("...and accepted with one", good.value("speed") == 1)


def test_a_guess_is_allowed_but_never_silent():
    s = spec.Spec({"name": "T", "facts": {
        "cost": {"value": 1800000, "kind": "provisional",
                 "source": "a guess, in cents - nobody has balanced this"},
        "speed": {"value": 120, "kind": "measured", "source": "https://x/civia"},
    }})
    check("the guess builds", s.value("cost") == 1800000)
    check("but it is listed as one", [f.key for f in s.provisional()] == ["cost"])
    check("and the measured number is not",
          "speed" not in [f.key for f in s.provisional()])

    # a provisional number still has to say why, or the report cannot quote it
    try:
        spec.Spec({"name": "T", "facts": {
            "cost": {"value": 1, "kind": "provisional", "source": ""}}})
        check("a nameless guess is refused", False)
    except spec.SpecError as e:
        check("a nameless guess is refused", "WHY it is a guess" in str(e))


def test_the_civia_spec_is_real_and_every_number_defensible():
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "assets", "civia_465", "spec.json")
    s = spec.load(path)

    check("it loads, so every source passed the check", s.name == "CiviaS465")
    check("five cars", len(s.cars) == 5)
    check("and the last one is turned around", s.cars[-1]["reversed"] is True)

    # the four numbers the image model got wrong, and what the sources actually say
    check("speed is the real 120, not the infographic's 140", s.value("speed") == 120)
    check("power is the real 2200, not 2000", s.value("power_total_kw") == 2200)
    check("it entered service in 2004, not 2009", s.value("intro_year") == 2004)

    kinds = s.sources()
    check("it rests on measured facts", len(kinds.get("measured", [])) >= 8)
    check("on the engine's own source", "window_colour" in kinds.get("engine", []))
    check("on a pixel measurement of the drawing",
          "drawing_height_to_rail_m" in kinds.get("reference", []))
    check("and it names its guesses", [f.key for f in s.provisional()] ==
          ["cost", "runningcost"])


if __name__ == "__main__":
    for fn in [v for k, v in sorted(globals().items()) if k.startswith("test_")]:
        print("\n%s" % fn.__name__)
        fn()
    print("\n%d checks passed" % _passed)
