"""The Blender UI: a Simutrans tab in the 3D view sidebar (press N).

Four buttons, in the order you actually use them:

    Build Rig      camera + sun + render settings for the chosen pakset
    Render Sheet   the 8 headings, the sprite sheet, and the .dat
    Check Colours  scan the sheet for reserved colours
    Compile .pak   run makeobj, and optionally install the result

Everything here is a thin shell over addon.rig and core.*, which are what the
tests exercise. The panel deliberately owns no geometry logic of its own.

EVERY user-visible string carries CTX, our own translation context. Blender's
message catalogue is shared, and it already owns words like "Engine" - leave a
string in the default context and Blender will cheerfully translate the
locomotive's engine as its RENDER engine. See addon/translations.py.
"""

import os

import bpy
from bpy.app import translations as bpy_translations
from bpy.props import (BoolProperty, EnumProperty, FloatVectorProperty,
                       IntProperty, StringProperty)
from bpy.types import Operator, Panel, PropertyGroup

try:
    from . import library, rig, template, translations, workflow
    from ..core import (buildings, colors, components, factories, night, package,
                        paksets, scenecheck, schema, sheet, templates, variants)
except ImportError:                                   # running from a checkout
    from addon import library, rig, template, translations, workflow
    from core import (buildings, colors, components, factories, night, package,
                      paksets, scenecheck, schema, sheet, templates, variants)

CTX = translations.CONTEXT


def _(msg):
    """Translate a string WE format. Blender only sees the ones it draws itself
    (bl_label, bl_description, property names); anything with a % in it, and
    everything handed to self.report(), has to come through here."""
    return bpy_translations.pgettext_iface(msg, CTX)


_ENGINE_TYPES = ("steam", "diesel", "electric", "bio", "sail", "hydrogene",
                 "fuel_cell", "battery")

# THE ENGINE'S OWN SPELLINGS, from descriptor/writer/get_waytype.cc - and it
# dbg->fatal()s on anything else, so a wrong one here does not misbehave, it kills
# the build. This list used to say "monorail", "maglev", "narrowgauge" and "tram",
# and every one of those four would have taken makeobj down with
# 'invalid waytype "monorail"'. They are monorail_track, maglev_track,
# narrowgauge_track and tram_track. Nobody had picked one yet.
_WAYTYPES = ("track", "road", "water", "air", "monorail_track", "maglev_track",
             "narrowgauge_track", "tram_track", "power", "decoration")

# what a wayobj GRANTS to the way it sits on. electrified_track is catenary, and it
# is the whole reason an electric locomotive will move.
_OWN_WAYTYPES = ("electrified_track",) + _WAYTYPES


class SimutransProps(PropertyGroup):
    pakset: EnumProperty(
        name="Pakset", translation_context=CTX,
        items=[(p, p, _("tile is %d px") % paksets.get(p).tile_px)
               for p in ("pak64", "pak128", "pak192", "pak256")],
        default="pak128",
    )
    # WHAT ARE WE MAKING. Everything downstream hangs off this: how many views get
    # rendered, how they are keyed, and which .dat comes out the other end.
    obj_type: EnumProperty(
        name="Object", translation_context=CTX,
        items=[
            ("vehicle", "Vehicle", "a train, a bus, a ship - 4 or 8 headings"),
            ("building", "Building", "a house, a factory - turned to face its street"),
            ("way", "Way", "a road, a rail - six models, sixteen images"),
            ("wayobj", "Catenary", "overhead line and the like, in two layers"),
            ("roadsign", "Sign / Signal", "four directions, one aspect each"),
            ("tunnel", "Tunnel", "a portal, four directions, two layers"),
            ("bridge", "Bridge", "span, ramps, pillars - in two layers"),
            ("factory", "Factory", "a building that makes or consumes goods"),
        ],
        default="vehicle",
    )

    # --- building
    size_x: IntProperty(name="Tiles east", translation_context=CTX,
                        default=1, min=1, max=8)
    size_y: IntProperty(name="Tiles south", translation_context=CTX,
                        default=1, min=1, max=8)
    layouts: IntProperty(
        name="Layouts", translation_context=CTX, default=0, min=0, max=4,
        description="How many ways round it can be built. 0 lets the engine "
                    "decide: 1 for a square footprint, 2 otherwise",
    )
    btype: EnumProperty(
        name="Kind", translation_context=CTX,
        items=[(t, t, "") for t in ("res", "com", "ind", "cur", "tow",
                                    "stop", "depot", "extension")],
        default="res",
    )
    level: IntProperty(name="Level", translation_context=CTX, default=1, min=1,
                       description="drives demand, and the default capacity "
                                   "(level x 32)")
    chance: IntProperty(name="Chance", translation_context=CTX, default=100,
                        min=0, max=100,
                        description="how often a city picks this house; 0 = never")
    # For a stop / depot / extension building (Kind), which its waytype field
    # already covers. A stop that enables nothing accepts nobody.
    enables_pax: BoolProperty(name="Accepts passengers", translation_context=CTX,
                              default=False)
    enables_post: BoolProperty(name="Accepts mail", translation_context=CTX,
                               default=False)
    enables_ware: BoolProperty(name="Accepts goods", translation_context=CTX,
                               default=False)
    seasons: IntProperty(
        name="Seasons", translation_context=CTX, default=1, min=1, max=5,
        description="1, 2, 4 or 5 - never 3, the engine NEVER draws the third "
                    "image. Put each season's extras in a collection 'season_1', "
                    "'season_2', ...",
    )
    phases: IntProperty(
        name="Phases", translation_context=CTX, default=1, min=1, max=16,
        description="animation frames. Put each frame's extras in a collection "
                    "'phase_1', 'phase_2', ...",
    )

    # --- way / wayobj
    topspeed: IntProperty(name="Top speed", translation_context=CTX,
                          default=50, min=1)
    maintenance: IntProperty(name="Maintenance", translation_context=CTX,
                             default=100, min=0)
    own_waytype: EnumProperty(
        name="Grants", translation_context=CTX,
        items=[(w, w, "") for w in _OWN_WAYTYPES], default="electrified_track",
        description="what the wayobj gives the way underneath. Catenary is "
                    "electrified_track - that is what lets an electric loco run",
    )

    # --- roadsign
    is_signal: BoolProperty(
        name="Block signal", translation_context=CTX, default=False,
        description="a signal rather than a sign. It then needs two aspects, and "
                    "STATE 0 IS RED",
    )
    states: IntProperty(
        name="Aspects", translation_context=CTX, default=1, min=1, max=8,
        description="1 for a plain sign, 2 for a signal. State 0 is RED. Put each "
                    "aspect's extras in a collection 'state_0', 'state_1', ...",
    )

    dirs: EnumProperty(
        name="Dirs", translation_context=CTX,
        items=[("8", "8 (asymmetric)", "every heading rendered"),
               ("4", "4 (symmetric)", "the engine reuses each for its opposite")],
        default="8",
    )
    out_dir: StringProperty(
        name="Output", translation_context=CTX,
        subtype="DIR_PATH", default="//simutrans",
        description="Where the sheet and the .dat go. '//' is relative to the "
                    ".blend, so save the .blend first or give an absolute path",
    )
    basename: StringProperty(name="Sheet", translation_context=CTX,
                             default="vehicle")

    obj_name: StringProperty(name="Name", translation_context=CTX,
                             default="My_Vehicle")
    author: StringProperty(name="Author", translation_context=CTX, default="")
    # the waytype and engine_type VALUES stay in English on purpose: they are the
    # literal keywords makeobj reads out of the .dat
    waytype: EnumProperty(name="Waytype", translation_context=CTX,
                          items=[(w, w, "") for w in _WAYTYPES], default="track")
    engine_type: EnumProperty(name="Engine", translation_context=CTX,
                              items=[(e, e, "") for e in _ENGINE_TYPES],
                              default="diesel")
    speed: IntProperty(name="Speed (km/h)", translation_context=CTX,
                       default=100, min=1)
    power: IntProperty(name="Power (kW)", translation_context=CTX,
                       default=0, min=0,
                       description="0 makes it an unpowered wagon or trailer")
    weight: IntProperty(name="Weight (t)", translation_context=CTX,
                        default=20, min=1)
    length: IntProperty(name="Length", translation_context=CTX,
                        default=8, min=1, max=16,
                        description="in 1/16 of a tile; 8 is half a tile")
    payload: IntProperty(name="Payload", translation_context=CTX, default=0, min=0)
    freight: StringProperty(name="Freight", translation_context=CTX, default="None")
    factory_mapcolor: IntProperty(
        name="Map colour", translation_context=CTX, default=1, min=0, max=254,
        description="The colour the factory shows on the minimap (0-254). The "
                    "engine refuses a factory without one")
    factory_productivity: IntProperty(
        name="Productivity", translation_context=CTX, default=10, min=0,
        description="How much the factory makes per step")
    factory_location: EnumProperty(
        name="Location", translation_context=CTX,
        items=[(t, t, "") for t in ("Land", "water", "city", "river", "shore",
                                    "forest")],
        default="Land",
        description="Where the industry generator may place it")
    factory_output_good: StringProperty(
        name="Makes", translation_context=CTX, default="",
        description="The good this factory PRODUCES (e.g. 'Kohle'). Must be a real "
                    "pakset good. Empty for a pure consumer")
    factory_output_capacity: IntProperty(
        name="Output store", translation_context=CTX, default=40, min=11,
        description="Storage for the produced good. Must be more than 10")
    factory_input_good: StringProperty(
        name="Consumes", translation_context=CTX, default="",
        description="A good this factory CONSUMES (e.g. 'Eisenerz'). Must be a real "
                    "pakset good. Empty for a pure producer")
    max_length: IntProperty(
        name="Max length", translation_context=CTX, default=0, min=0,
        description="Longest span the bridge may cross, in tiles. 0 = unlimited")
    max_height: IntProperty(
        name="Max height", translation_context=CTX, default=4, min=1,
        description="How high above the ground the bridge may be built")
    pillar_distance: IntProperty(
        name="Pillar every", translation_context=CTX, default=0, min=0,
        description="Place a pillar every N tiles. 0 = no pillars")
    tunnel_way: StringProperty(
        name="Inner way", translation_context=CTX, default="",
        description="Optional: the name of the way built inside the tunnel. It is "
                    "written as a cross-reference and must resolve to a real way at "
                    "game load, so leave it EMPTY unless you have one",
    )
    freight_goods: StringProperty(
        name="Cargo variants", translation_context=CTX, default="",
        description="Comma-separated goods for a wagon that looks different loaded "
                    "(e.g. 'Kohle, Oel'). Put each load in a collection freight_0, "
                    "freight_1, ... in the same order. Leave EMPTY for a wagon that "
                    "looks the same whatever it carries",
    )
    cost: IntProperty(name="Cost (cents)", translation_context=CTX,
                      default=1000000, min=0)
    runningcost: IntProperty(name="Running cost", translation_context=CTX,
                             default=100, min=0)
    intro_year: IntProperty(name="Intro year", translation_context=CTX, default=1900)

    # Two labels that used to both read "Couples ..." and truncated to the same
    # thing in the narrow sidebar. They now lead with the word that tells them
    # apart, and match what the field actually lists: the neighbours allowed on
    # each side.
    constraint_prev: StringProperty(
        name="In front", translation_context=CTX, default="",
        description="Comma-separated vehicle names that may go IN FRONT of this "
                    "one. Use 'none' to allow it at the head of the train. Leave "
                    "EMPTY to couple behind anything - an empty field is not the "
                    "same as 'none'",
    )
    constraint_next: StringProperty(
        name="Behind", translation_context=CTX, default="",
        description="Comma-separated vehicle names that may go BEHIND this one. "
                    "Use 'none' to allow it at the tail. Leave EMPTY to couple to "
                    "anything",
    )

    makeobj_path: StringProperty(
        name="makeobj", translation_context=CTX, subtype="FILE_PATH", default="",
        description="Path to the makeobj executable. It is not shipped with "
                    "Blender: build it from the Simutrans source with "
                    "'cmake --build <dir> --target makeobj'",
    )
    install_dir: StringProperty(
        name="Install to", translation_context=CTX, subtype="DIR_PATH", default="",
        description="Optional. Copy the compiled .pak here - normally a pakset's "
                    "addons folder, so the game picks it up",
    )

    night_level: IntProperty(
        name="Night", translation_context=CTX, default=4, min=0, max=4,
        description="How dark. The game's clock runs 0 (noon) to 4 (deep night) - "
                    "display/simview.cc hours2night[]",
    )

    align_offset: FloatVectorProperty(
        name="Align offset", translation_context=CTX,
        size=3, default=(0.0, 0.0, 0.0), subtype="TRANSLATION",
        description="Nudge the vehicle inside its cell. Leave at zero unless it "
                    "does not ride the centre of the way",
    )
    write_dat: BoolProperty(name="Write .dat", translation_context=CTX, default=True)

    # --- materials.
    #
    # rig.make_special_color_material and friends are the whole reason the kit
    # exists - a player-colour patch that the engine recolours per company, a window
    # that lights up at night - and until now they had NO button. An artist who did
    # not write Python could not paint one. These do.
    material: EnumProperty(
        name="Material", translation_context=CTX,
        items=[
            ("player", "Player colour", "recoloured per company. Emission, so it "
                                        "survives to the pak exactly"),
            ("window", "Window (warm)", "dark by day, warm yellow at night"),
            ("window_blue", "Window (blue)", "lit blue at night"),
            ("headlight", "Headlight", "near-white by day, yellow after dark"),
            ("lamp_red", "Red lamp", "a red light, day and night"),
            ("lamp_green", "Green lamp", "a green light"),
            ("lamp_yellow", "Yellow lamp", "a yellow light"),
            ("signal_purple", "Signal (purple)", "the purple signal lamp - you paint "
                                                 "#FF017F, the game draws #E100E1"),
            ("paint", "Plain paint", "an ordinary LIT colour - a roof, a hull. Uses "
                                     "the colour below"),
        ],
        default="player",
    )
    paint_color: FloatVectorProperty(
        name="Paint", translation_context=CTX, subtype="COLOR",
        size=3, min=0.0, max=1.0, default=(0.5, 0.5, 0.5),
        description="The colour for Plain paint. The reserved materials above ignore "
                    "it - their colour is fixed by the engine",
    )

    # --- reference photos.
    #
    # The real thing's measurements, so a photo can be scaled to the size the
    # model has to end up. Metres, because that is what a spec sheet gives you.
    ref_image: StringProperty(
        name="Image", translation_context=CTX, subtype="FILE_PATH", default="",
        description="A photo or drawing already on your disk. Nothing is "
                    "downloaded",
    )
    ref_side: EnumProperty(
        name="View", translation_context=CTX,
        items=[("side", "Side", "seen from the left - length along +X"),
               ("front", "Front", "seen from the nose - width across"),
               ("top", "Top", "seen from above")],
        default="side",
    )
    ref_length_m: FloatVectorProperty(
        name="Real size (m)", translation_context=CTX, size=3,
        default=(20.0, 3.0, 4.0), min=0.01, subtype="XYZ",
        description="The REAL length, width and height in metres. The photo is "
                    "scaled to these, so a model traced over it comes out the "
                    "right size",
    )
    metres_per_tile: IntProperty(
        name="Metres per tile", translation_context=CTX, default=40, min=1,
        description="How many metres of the world one tile is. The engine has NO "
                    "metres - this is the pakset's own convention, and pak128's "
                    "is roughly 40",
    )

    # --- variants.
    #
    # ONE string, holding the JSON core/variants.py owns. Not a CollectionProperty:
    # that would put the format in bpy, where it could not be migrated without
    # Blender and could not be tested without it either. This way an old .blend's
    # variants are read by the same load() the tests exercise, and the schema
    # version travels with the document.
    variants_json: StringProperty(
        name="Variants", translation_context=CTX, default="",
        description="The variant list, as JSON. Edited through the buttons - "
                    "there is no need to read it",
    )
    variant_index: IntProperty(name="Variant", translation_context=CTX,
                               default=0, min=0)
    variant_name: StringProperty(
        name="Variant name", translation_context=CTX, default="",
        description="What this variant is called. It becomes name= in its own "
                    ".dat - a variant IS a separate object",
    )
    variant_material: StringProperty(
        name="Repaint", translation_context=CTX, default="",
        description="The material this variant repaints. Leave empty for a "
                    "variant that differs only in its numbers",
    )
    variant_color: FloatVectorProperty(
        name="To", translation_context=CTX, subtype="COLOR",
        size=3, min=0.0, max=1.0, default=(0.5, 0.5, 0.5))

    # --- components
    component_key: StringProperty(
        name="Component", translation_context=CTX, default="",
        description="Which component to bring in. Press Refresh to list what is "
                    "available",
    )
    component_mode: EnumProperty(
        name="How", translation_context=CTX,
        items=[("append", "Copy in", "a real copy. Yours forever, renders "
                                     "anywhere - including on someone else's "
                                     "machine"),
               ("link", "Link", "the component's own .blend stays the master. "
                                "Fix it once, every project updates - but the "
                                "file must be there at render time"),
               ("instance", "Instance", "one mesh, many copies. Cheap for eight "
                                        "bogies")],
        default="append",
    )

    # --- preview
    preview_fingerprint: StringProperty(
        name="Preview state", translation_context=CTX, default="",
        description="What the scene looked like when the preview was made. Not "
                    "for editing")

    # --- publishing
    pkg_version: StringProperty(name="Version", translation_context=CTX,
                                default="1.0.0")
    pkg_license: StringProperty(
        name="Licence", translation_context=CTX, default="",
        description="Required. Without one nobody may legally ship your work, "
                    "and most paksets will not take it")
    pkg_category: StringProperty(name="Category", translation_context=CTX,
                                 default="vehicle")
    pkg_description: StringProperty(name="Description", translation_context=CTX,
                                    default="")
    pkg_dir: StringProperty(
        name="Package to", translation_context=CTX, subtype="DIR_PATH",
        default="", description="Where the .zip goes. Nothing is uploaded")


# WHAT TO MODEL, said in the panel, at the moment it matters. An artist should not
# have to go and read a README to find out that a way is six collections. The first
# line of each carries the icon.
_MODEL_HINT = {
    "vehicle": ("Model: nose along +X,",
                "on z=0, at the origin"),
    "building": ("Model: facade toward -Y",
                 "(Blender's Front view),",
                 "growing east (+X) and south (-Y)"),
    "way": ("Six collections:",
            "way_none, way_end, way_straight,",
            "way_curve, way_tee, way_cross"),
    "wayobj": ("Six collections wayobj_none ...",
               "wayobj_cross, and for each, a",
               "wayobj_<piece>_front for the parts",
               "drawn OVER the vehicles"),
    "roadsign": ("Model it at the tile's NORTH",
                 "edge (+Y). For a signal, put each",
                 "aspect's lamp in state_0 / state_1;",
                 "STATE 0 IS RED"),
    "tunnel": ("Collection tunnel_portal on a",
               "ramp facing NORTH, and",
               "tunnel_portal_front for the parts",
               "drawn OVER the vehicles"),
    "bridge": ("Collections bridge_span,",
               "bridge_start, bridge_ramp,",
               "bridge_pillar, and a _front for",
               "the parts drawn OVER the vehicles"),
    "factory": ("Model it like a building:",
                "facade toward -Y, growing",
                "east (+X) and south (-Y).",
                "Give it a Map colour"),
}


def _out_dir(props):
    """The output directory, or (None, reason) if it cannot be resolved.

    A '//' path is relative to the .blend file. Until the .blend is saved there
    is nothing to be relative TO, and Blender quietly resolves it against the
    current working directory - which is wherever Blender happened to be
    launched from. Rendering a sheet into that is worse than refusing to.
    """
    raw = props.out_dir
    if raw.startswith("//") and not bpy.data.filepath:
        return None, _("Save your .blend first, or set an absolute Output path "
                       "('//' means 'next to the .blend', and there isn't one yet)")
    path = bpy.path.abspath(raw)
    if not path:
        return None, _("Set an Output directory")
    return path, None


def _names(text):
    """"a, b" -> ("a", "b"). Empty string -> (), which means NO constraint at all.

    And no constraint at all is not the same as a constraint of `none`: with no
    Constraint[Prev] the vehicle couples behind anything, while a Prev list whose
    only entry is `none` means "the only thing allowed in front of me is nothing",
    so the vehicle can ONLY ever run alone (descriptor/vehicle_desc.h:219). The
    empty field therefore has to stay empty, not become "none".
    """
    return tuple(n.strip() for n in text.split(",") if n.strip())


# The last render, per (output dir, basename), kept so the .dat can be rewritten
# WITHOUT rendering again. The expensive step is the Blender render; the per-frame
# PNGs it produced still sit on disk, so rebuilding the sheet and the .dat from the
# same frame list is a matter of milliseconds. An artist can change power= or cost=
# and press Write .dat instead of re-rendering 320 headings. In memory, so it lasts
# a Blender session - which is exactly the edit-the-numbers loop it is for.
_LAST_RENDER = {}


def _render(p, out):
    """Render the selected object and build its .dat. -> (frames, sheet, dat).

    Two steps kept apart on purpose: rendering the headings (slow, Blender), then
    building the sheet and .dat from them (fast, no Blender). The second step is
    _build_dat, and it is exactly what Write .dat re-runs on its own.
    """
    if p.obj_type == "vehicle":
        goods = _names(p.freight_goods)
        if goods:
            # A cargo-variant wagon: one loaded sheet per good, from collections
            # freight_0..freight_N-1. The good count and the collection count must
            # agree - the engine needs exactly one freightimagetype per freight
            # image (vehicle_writer.cc), so a mismatch is caught here, not shipped.
            n_col = rig.freight_variant_count(bpy)
            if n_col != len(goods):
                raise ValueError(
                    _("You listed %d cargo variant(s) but there are %d freight_ "
                      "collection(s). Make one collection freight_0..freight_%d, "
                      "one per good, in order") % (len(goods), n_col, len(goods) - 1))
            empty, variants = rig.render_freight_variants(
                bpy, out, p.pakset, dirs=int(p.dirs), basename=p.basename,
                align_offset=tuple(p.align_offset), count=len(goods))
            record = {"obj_type": "vehicle", "freight": True,
                      "empty": empty, "variants": variants, "goods": goods}
            frames = list(empty) + [f for v in variants for f in v]
        else:
            frames = rig.render_directions(
                bpy, out, p.pakset, dirs=int(p.dirs), basename=p.basename,
                align_offset=tuple(p.align_offset))
            record = {"obj_type": "vehicle", "frames": frames}

    elif p.obj_type == "building":
        season_setup = rig.collection_variant_setup("season_") if p.seasons > 1 else None
        phase_setup = rig.collection_variant_setup("phase_") if p.phases > 1 else None
        frames = rig.render_building(
            bpy, out, p.pakset, basename=p.basename,
            size_x=p.size_x, size_y=p.size_y,
            layouts=(p.layouts or None), seasons=p.seasons,
            season_setup=season_setup, phases=p.phases, phase_setup=phase_setup,
            align_offset=tuple(p.align_offset))
        record = {"obj_type": "building", "frames": frames}

    elif p.obj_type == "way":
        frames = rig.render_way(bpy, out, p.pakset, basename=p.basename,
                                align_offset=tuple(p.align_offset))
        # The ramp, if the artist modelled one (collection way_slope, and way_slope2
        # for a double-height ramp). Without it the way is INVISIBLE on every slope
        # in the game - weg.cc:545 has no fallback, unlike the diagonals.
        slope_frames = slope2_frames = ()
        if rig.has_slope_model(bpy):
            slope_frames = rig.render_way_slopes(
                bpy, out, p.pakset, basename=p.basename,
                align_offset=tuple(p.align_offset))
        if rig.has_slope_model(bpy, double=True):
            slope2_frames = rig.render_way_slopes(
                bpy, out, p.pakset, basename=p.basename, double=True,
                align_offset=tuple(p.align_offset))
        # On a pakset whose hills are double by default (pak128), a way with a
        # single ramp but no way_slope2 gets its single image stretched over every
        # ordinary hill. Say so - the panel is where the artist will see it.
        rig.warn_if_double_slope_missing(bpy, p.pakset)
        record = {"obj_type": "way", "frames": frames,
                  "slope_frames": slope_frames, "slope2_frames": slope2_frames}

    elif p.obj_type == "wayobj":
        frames = rig.render_wayobj(bpy, out, p.pakset, basename=p.basename,
                                   align_offset=tuple(p.align_offset))
        # The ramp (collection wayobj_slope). Without it the catenary is not drawn
        # on a slope at all - wayobj.cc:270, no guard.
        slope_frames = ()
        if rig.has_wayobj_slope_model(bpy):
            slope_frames = rig.render_wayobj_slopes(
                bpy, out, p.pakset, basename=p.basename,
                align_offset=tuple(p.align_offset))
        record = {"obj_type": "wayobj", "frames": frames,
                  "slope_frames": slope_frames}

    elif p.obj_type == "roadsign":
        state_setup = rig.collection_variant_setup("state_") if p.states > 1 else None
        frames = rig.render_roadsign(
            bpy, out, p.pakset, basename=p.basename, states=p.states,
            state_setup=state_setup, align_offset=tuple(p.align_offset))
        record = {"obj_type": "roadsign", "frames": frames}

    elif p.obj_type == "tunnel":
        if not rig.has_tunnel_model(bpy):
            raise ValueError(_("No tunnel_portal collection - model the portal on "
                               "a north-facing ramp and put it in tunnel_portal"))
        portals = rig.render_tunnel_portals(
            bpy, out, p.pakset, basename=p.basename,
            align_offset=tuple(p.align_offset))
        record = {"obj_type": "tunnel", "portals": portals}
        frames = list(portals["back"]) + list(portals.get("front", []))

    elif p.obj_type == "bridge":
        if not rig.has_bridge_model(bpy):
            raise ValueError(_("No bridge_span collection - model the pieces in "
                               "bridge_span, bridge_start, bridge_ramp, "
                               "bridge_pillar"))
        pieces = rig.render_bridge_pieces(
            bpy, out, p.pakset, basename=p.basename,
            align_offset=tuple(p.align_offset))
        record = {"obj_type": "bridge", "pieces": pieces}
        frames = [f for grp in pieces["back"].values() for f in grp]

    elif p.obj_type == "factory":
        # A factory IS a building - same render, different .dat (obj=factory).
        frames = rig.render_building(
            bpy, out, p.pakset, basename=p.basename,
            size_x=p.size_x, size_y=p.size_y, layouts=1,
            align_offset=tuple(p.align_offset))
        record = {"obj_type": "factory", "frames": frames}

    else:
        raise ValueError("unknown object type %r" % (p.obj_type,))

    _LAST_RENDER[(out, p.basename)] = record
    if not p.write_dat:
        return frames, None, None
    png, dat = _build_dat(p, out, record)
    return frames, png, dat


def _build_dat(p, out, record):
    """Sheet + .dat from an already-rendered frame list. No Blender. -> (png, dat).

    Reads the frames from `record` and every other value from the panel, so it is
    the one place a .dat is written - whether straight after a render or, later,
    from Write .dat with the numbers changed and not a pixel re-rendered.
    """
    common = dict(name=p.obj_name, author=p.author)
    kind = record["obj_type"]
    frames = record.get("frames")

    if kind == "vehicle":
        vehicle_kwargs = dict(
            waytype=p.waytype, engine_type=p.engine_type, speed=p.speed,
            power=p.power, weight=p.weight, length=p.length, payload=p.payload,
            freight=p.freight, cost=p.cost, runningcost=p.runningcost,
            intro_year=p.intro_year,
            constraint_prev=_names(p.constraint_prev),
            constraint_next=_names(p.constraint_next), **common)
        if record.get("freight"):
            png, dat, _pl = rig.build_freight_sheet_and_dat(
                record["empty"], record["variants"], record["goods"], out,
                p.pakset, basename=p.basename, cols=4, **vehicle_kwargs)
            return png, dat
        png, dat, _pl = rig.build_sheet_and_dat(
            frames, out, p.pakset, basename=p.basename, cols=4, **vehicle_kwargs)
        return png, dat

    if kind == "building":
        pak = paksets.get(p.pakset)
        png = os.path.join(out, "%s.png" % p.basename)
        placement = sheet.assemble(frames, pak.tile_px, cols=4, out_path=png)
        n_layouts = buildings.layouts_for(p.size_x, p.size_y, p.layouts or None)
        # waytype and enables belong to a stop/depot/extension only; a plain house
        # must not pick up a waytype left over from an earlier way render.
        is_station = p.btype in ("stop", "depot", "extension")
        enables = [e for e, on in (("pax", p.enables_pax), ("post", p.enables_post),
                                   ("ware", p.enables_ware)) if on]
        text = buildings.building_dat(
            images=buildings.image_block(p.basename, placement),
            btype=p.btype, dims="%d,%d,%d" % (p.size_x, p.size_y, n_layouts),
            level=p.level, chance=p.chance, intro_year=p.intro_year,
            waytype=p.waytype if is_station else "",
            enables=enables if is_station else (),
            icon=buildings.icon_ref(p.basename, placement) if is_station else "",
            animation_time=(buildings.DEFAULT_ANIMATION_TIME_MS
                            if p.phases > 1 else None),
            **common)
        dat = os.path.join(out, "%s.dat" % p.basename)
        with open(dat, "w", encoding="utf-8") as f:
            f.write(text)
        return png, dat

    if kind == "way":
        png, dat, _pl = rig.build_way_sheet_and_dat(
            frames, out, p.pakset, basename=p.basename, cols=4,
            slope_frames=record.get("slope_frames", ()),
            slope2_frames=record.get("slope2_frames", ()),
            waytype=p.waytype, topspeed=p.topspeed, cost=p.cost,
            maintenance=p.maintenance, intro_year=p.intro_year, **common)
        return png, dat

    if kind == "wayobj":
        png, dat, _pl = rig.build_wayobj_sheet_and_dat(
            frames, out, p.pakset, basename=p.basename, cols=8,
            slope_frames=record.get("slope_frames", ()),
            waytype=p.waytype, own_waytype=p.own_waytype, cost=p.cost,
            maintenance=p.maintenance, topspeed=p.topspeed,
            intro_year=p.intro_year, **common)
        return png, dat

    if kind == "roadsign":
        png, dat, _pl = rig.build_roadsign_sheet_and_dat(
            frames, out, p.pakset, basename=p.basename, cols=4,
            waytype=p.waytype, is_signal=int(p.is_signal), cost=p.cost,
            intro_year=p.intro_year, **common)
        return png, dat

    if kind == "tunnel":
        png, dat, _pl = rig.build_tunnel_sheet_and_dat(
            record["portals"], out, p.pakset, basename=p.basename, cols=4,
            waytype=p.waytype, topspeed=p.topspeed, cost=p.cost,
            maintenance=p.maintenance, intro_year=p.intro_year,
            way=p.tunnel_way, **common)
        return png, dat

    if kind == "bridge":
        png, dat, _pl = rig.build_bridge_sheet_and_dat(
            record["pieces"], out, p.pakset, basename=p.basename, cols=4,
            waytype=p.waytype, topspeed=p.topspeed, cost=p.cost,
            maintenance=p.maintenance, intro_year=p.intro_year,
            max_length=p.max_length, max_height=p.max_height,
            pillar_distance=p.pillar_distance, **common)
        return png, dat

    if kind == "factory":
        pak = paksets.get(p.pakset)
        png = os.path.join(out, "%s.png" % p.basename)
        placement = sheet.assemble(frames, pak.tile_px, cols=4, out_path=png)
        outputs = ([(p.factory_output_good, p.factory_output_capacity, 100)]
                   if p.factory_output_good else [])
        inputs = ([(p.factory_input_good, 1, 40, 100)]
                  if p.factory_input_good else [])
        text = factories.factory_dat(
            images=buildings.image_block(p.basename, placement),
            mapcolor=p.factory_mapcolor, dims="%d,%d" % (p.size_x, p.size_y),
            level=p.level, location=p.factory_location,
            productivity=p.factory_productivity,
            outputs=outputs, inputs=inputs, **common)
        dat = os.path.join(out, "%s.dat" % p.basename)
        with open(dat, "w", encoding="utf-8") as f:
            f.write(text)
        return png, dat

    raise ValueError("unknown object type %r" % (kind,))


class SIMUTRANS_OT_build_rig(Operator):
    bl_idname = "simutrans.build_rig"
    bl_label = "Build Rig"
    bl_translation_context = CTX
    bl_description = ("Create the Simutrans camera and sun and set the render "
                      "options this pakset needs")
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        p = context.scene.simutrans
        pak = rig.build_rig(bpy, p.pakset)
        self.report({"INFO"}, _("%s rig: %d px, ortho_scale %.4f")
                    % (pak.name, pak.tile_px, pak.ortho_scale))
        return {"FINISHED"}


def _template_opts(p):
    """The panel's numbers, in the words core.templates uses."""
    return dict(seasons=p.seasons, phases=p.phases, states=p.states,
                freight_variants=len(_names(p.freight_goods)))


class SIMUTRANS_OT_create_template(Operator):
    bl_idname = "simutrans.create_template"
    bl_label = "Create Template"
    bl_translation_context = CTX
    bl_description = ("Make the collections this object needs, named the way the "
                      "renderer reads them, and the guides that show which way is "
                      "forward and how big a tile is. Safe to press again")
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        p = context.scene.simutrans
        made, kept, guides = template.create(
            bpy, p.obj_type, p.pakset, length=p.length, size_x=p.size_x,
            size_y=p.size_y, **_template_opts(p))

        if made:
            say(self, {"INFO"}, _("%d collection(s): %s")
                % (len(made), ", ".join(made)))
        if kept:
            # Said out loud, because "nothing happened" is what a second press
            # looks like otherwise, and an artist who cannot tell "already there"
            # from "broken" presses it a third time.
            say(self, {"INFO"}, _("%d already there, left alone") % len(kept))
        if not made and not kept:
            say(self, {"INFO"},
                _("A %s needs no collections - the guides are the template")
                % p.obj_type)
        say(self, {"INFO"}, _("%d guide(s) - they never render") % len(guides))
        return {"FINISHED"}


class SIMUTRANS_OT_setup_reference(Operator):
    bl_idname = "simutrans.setup_reference"
    bl_label = "Place Reference"
    bl_translation_context = CTX
    bl_description = ("Put a photo where the model goes, scaled from the real "
                      "measurements you typed. Nothing is downloaded")
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        p = context.scene.simutrans
        path = bpy.path.abspath(p.ref_image) if p.ref_image else ""
        if not path:
            say(self, {"ERROR"}, _("Pick a reference image first"))
            return {"CANCELLED"}
        try:
            ob = template.setup_reference(
                bpy, p.ref_side, path,
                length_m=p.ref_length_m[0], width_m=p.ref_length_m[1],
                height_m=p.ref_length_m[2], pakset_name=p.pakset,
                metres_per_tile=p.metres_per_tile)
        except (ValueError, RuntimeError) as e:
            say(self, {"ERROR"}, str(e))
            return {"CANCELLED"}
        if ob is None:
            say(self, {"ERROR"},
                _("There is already an object with that name and it is not a "
                  "reference. Rename it first - I will not delete your work"))
            return {"CANCELLED"}
        say(self, {"INFO"}, _("%s placed, %d m per tile")
            % (ob.name, p.metres_per_tile))
        return {"FINISHED"}


class SIMUTRANS_OT_validate(Operator):
    bl_idname = "simutrans.validate"
    bl_label = "Validate"
    bl_translation_context = CTX
    bl_description = ("Check the scene BEFORE rendering it: the collections, the "
                      "ground, the origin, the size and the numbers. An error "
                      "stops the render; a warning does not")

    def execute(self, context):
        p = context.scene.simutrans
        findings = scenecheck.check(template.describe(bpy, p, rig))

        for f in findings:
            level = {scenecheck.ERROR: "ERROR",
                     scenecheck.WARNING: "WARNING"}.get(f.level, "INFO")
            say(self, {level}, "%s: %s" % (f.code, _(f.message)))

        errors = scenecheck.blocking(findings)
        if errors:
            say(self, {"ERROR"}, _("%d error(s) - fix these before rendering")
                % len(errors))
        elif len(findings) > 1:
            say(self, {"INFO"}, _("No errors. %d thing(s) to look at")
                % (len(findings) - 1))
        else:
            say(self, {"INFO"}, _("Nothing wrong that I can see from here"))
        return {"FINISHED"}


# What the operators have told the user. Blender's report() vanishes into the C
# layer and cannot be intercepted from Python, so without this there is no way to
# prove that a warning reached the PANEL rather than the console - and "it printed
# to the console" is precisely the bug being fixed. Kept short; it is a record of
# the last operator run, not a log.
REPORTS = []
_REPORT_LIMIT = 64


def say(operator, level, message):
    """Tell the user, and remember that we did."""
    del REPORTS[:-_REPORT_LIMIT + 1]
    REPORTS.append((set(level), message))
    operator.report(level, message)


class SIMUTRANS_OT_render_sheet(Operator):
    bl_idname = "simutrans.render_sheet"
    bl_label = "Render Sheet"
    bl_translation_context = CTX
    bl_description = "Render every heading, assemble the sprite sheet, write the .dat"

    def execute(self, context):
        p = context.scene.simutrans
        out, why = _out_dir(p)
        if out is None:
            say(self, {"ERROR"}, why)
            return {"CANCELLED"}

        mins, maxs = rig.scene_bounds(bpy)
        if maxs[2] <= mins[2]:
            say(self, {"ERROR"}, _("Nothing to render - the scene has no mesh"))
            return {"CANCELLED"}

        # Everything the rig complains about while it renders - the model running
        # off the edge of the cell, a stray pixel landing on a reserved colour -
        # used to go to the console and nowhere else. The panel said "Rendered" and
        # the artist, who does not have a console open, shipped a sprite with the
        # cab cut off. Whatever it says now, it says HERE.
        mark = rig.warning_mark()
        try:
            frames, sheet_png, dat_path = _render(p, out)
        except ValueError as e:
            # the rig refuses things that would compile and then be wrong - a
            # season with nothing in it, a way with no pieces modelled
            say(self, {"ERROR"}, str(e))
            return {"CANCELLED"}

        raised = rig.warnings_since(mark)
        return _report_render_result(self, p, out, frames, sheet_png, dat_path, raised)

    def invoke(self, context, event):
        # A click in the panel steps the VEHICLE render heading-by-heading, so the
        # panel can show progress and Esc can cancel it. Every other object type -
        # and every scripted call, bpy.ops...render_sheet() (EXEC, which the tests
        # use), goes to execute() unchanged: bpy.ops.render.render is itself
        # blocking, so a modal only buys an update-and-cancel point BETWEEN
        # headings, and only the vehicle path renders one still per heading.
        #
        # A cargo-variant wagon renders several sheets (empty + one per good), which
        # the modal does not step; it goes through execute() synchronously too.
        p = context.scene.simutrans
        if p.obj_type != "vehicle" or _names(p.freight_goods):
            return self.execute(context)
        return self._invoke_vehicle_modal(context)

    def _invoke_vehicle_modal(self, context):
        p = context.scene.simutrans
        out, why = _out_dir(p)
        if out is None:
            say(self, {"ERROR"}, why)
            return {"CANCELLED"}
        mins, maxs = rig.scene_bounds(bpy)
        if maxs[2] <= mins[2]:
            say(self, {"ERROR"}, _("Nothing to render - the scene has no mesh"))
            return {"CANCELLED"}

        self._out = out
        self._mark = rig.warning_mark()
        self._plan, self._codes = rig.prepare_directions(
            bpy, out, p.pakset, dirs=int(p.dirs), basename=p.basename,
            align_offset=tuple(p.align_offset))
        self._i = 0
        self._frames = []

        wm = context.window_manager
        wm.progress_begin(0, len(self._codes))
        self._timer = wm.event_timer_add(0.01, window=context.window)
        wm.modal_handler_add(self)
        context.workspace.status_text_set(
            _("Rendering %d headings - Esc to cancel") % len(self._codes))
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type == "ESC":
            self._teardown(context)
            # A cancelled render is left on disk but NOT recorded: half a sheet must
            # never stand in for a whole one, so Write .dat has nothing to build from.
            say(self, {"WARNING"}, _("Render cancelled at heading %d/%d")
                % (self._i, len(self._codes)))
            return {"CANCELLED"}
        if event.type != "TIMER":
            return {"RUNNING_MODAL"}

        if self._i < len(self._codes):
            self._frames.append(
                rig.render_one_step(bpy, self._plan, self._codes[self._i]))
            self._i += 1
            context.window_manager.progress_update(self._i)
            context.workspace.status_text_set(
                _("Rendering heading %d/%d - Esc to cancel")
                % (self._i, len(self._codes)))
            return {"RUNNING_MODAL"}

        return self._finish_vehicle_modal(context)

    def _finish_vehicle_modal(self, context):
        self._teardown(context)
        p = context.scene.simutrans
        rig.warn_if_clipped(self._frames, "vehicle")
        record = {"obj_type": "vehicle", "frames": self._frames}
        _LAST_RENDER[(self._out, p.basename)] = record
        raised = rig.warnings_since(self._mark)
        if p.write_dat:
            sheet_png, dat_path = _build_dat(p, self._out, record)
        else:
            sheet_png = dat_path = None
        return _report_render_result(self, p, self._out, self._frames,
                                     sheet_png, dat_path, raised)

    def _teardown(self, context):
        wm = context.window_manager
        if getattr(self, "_timer", None) is not None:
            wm.event_timer_remove(self._timer)
            self._timer = None
        wm.progress_end()
        context.workspace.status_text_set(None)


def _report_render_result(operator, p, out, frames, sheet_png, dat_path, raised):
    """Report a finished render into the panel: warnings, then lint, then the final
    line. Shared by the synchronous execute() and the modal vehicle render so both
    say exactly the same things. -> the operator return set."""
    for message in raised:
        say(operator, {"WARNING"}, message)

    if dat_path is None:
        say(operator, {"INFO"}, _("Rendered %d frames to %s") % (len(frames), out))
        return {"FINISHED"}

    if _report_lint(operator, dat_path):
        return {"FINISHED"}

    if raised:
        say(operator, {"WARNING"}, _("%s + %s, with %d warning(s) above")
            % (os.path.basename(sheet_png), os.path.basename(dat_path), len(raised)))
        return {"FINISHED"}

    say(operator, {"INFO"}, "%s + %s"
        % (os.path.basename(sheet_png), os.path.basename(dat_path)))
    return {"FINISHED"}


def _report_lint(operator, dat_path):
    """Lint the .dat and report every finding into the panel. -> did it find any?

    The artist gets this without knowing the linter exists, which is the point:
    the two worst .dat mistakes are silent.
    """
    with open(dat_path, encoding="utf-8") as f:
        findings = schema.lint(f.read())
    for finding in findings:
        print("%s:%d: %s: %s" % (dat_path, finding.line, finding.level,
                                 finding.message))
        say(operator, {"ERROR"} if finding.level == "error" else {"WARNING"},
            _(".dat line %d: %s") % (finding.line, finding.message))
    if findings:
        errors = sum(1 for f in findings if f.level == "error")
        say(operator, {"WARNING"}, _(".dat: %d error(s), %d warning(s)")
            % (errors, len(findings) - errors))
    return bool(findings)


class SIMUTRANS_OT_write_dat(Operator):
    bl_idname = "simutrans.write_dat"
    bl_label = "Write .dat"
    bl_translation_context = CTX
    bl_description = ("Rewrite the .dat from the last render, with the current "
                      "numbers - no re-rendering. Change power, cost, couplings and "
                      "press this instead of rendering every heading again")

    def execute(self, context):
        p = context.scene.simutrans
        out, why = _out_dir(p)
        if out is None:
            say(self, {"ERROR"}, why)
            return {"CANCELLED"}

        record = _LAST_RENDER.get((out, p.basename))
        if record is None:
            say(self, {"ERROR"},
                _("No render to build from - press Render Sheet first"))
            return {"CANCELLED"}
        if record["obj_type"] != p.obj_type:
            say(self, {"ERROR"},
                _("The last render of %r was a %s, not a %s")
                % (p.basename, record["obj_type"], p.obj_type))
            return {"CANCELLED"}

        _png, dat_path = _build_dat(p, out, record)
        if _report_lint(self, dat_path):
            return {"FINISHED"}
        say(self, {"INFO"}, _("Wrote %s (no re-render)")
            % os.path.basename(dat_path))
        return {"FINISHED"}


class SIMUTRANS_OT_check_colors(Operator):
    bl_idname = "simutrans.check_colors"
    bl_label = "Check Colours"
    bl_translation_context = CTX
    bl_description = ("Scan the sheet for Simutrans' reserved colours - the ones "
                      "the engine repaints in the company colour")

    def execute(self, context):
        p = context.scene.simutrans
        out, why = _out_dir(p)
        if out is None:
            self.report({"ERROR"}, why)
            return {"CANCELLED"}

        path = os.path.join(out, "%s.png" % p.basename)
        if not os.path.exists(path):
            self.report({"ERROR"}, _("No sheet yet - render one first"))
            return {"CANCELLED"}

        _width, _height, alpha, px = sheet.read_png(path)
        rgb = [(q[0], q[1], q[2]) for q in px if not (alpha and q[3] == 0)]
        hits = colors.scan(rgb)
        if not hits:
            self.report({"INFO"},
                        _("No reserved colours - nothing will be recoloured"))
            return {"FINISHED"}
        for line in colors.report(hits):
            self.report({"INFO"}, line)
        return {"FINISHED"}


class SIMUTRANS_OT_night_preview(Operator):
    bl_idname = "simutrans.night_preview"
    bl_label = "Night Preview"
    bl_translation_context = CTX
    bl_description = ("Show the sheet as the game will draw it after dark - the "
                      "engine's own day-to-night colour swap, not a filter")

    def execute(self, context):
        p = context.scene.simutrans
        out, why = _out_dir(p)
        if out is None:
            self.report({"ERROR"}, why)
            return {"CANCELLED"}

        path = os.path.join(out, "%s.png" % p.basename)
        if not os.path.exists(path):
            self.report({"ERROR"}, _("No sheet yet - render one first"))
            return {"CANCELLED"}

        dst = os.path.join(out, "%s_night.png" % p.basename)
        hits = night.preview(path, dst, night=p.night_level)

        # THE POINT OF THE BUTTON. A window only lights up if it hit the engine's
        # colour EXACTLY; miss by one count and it is ordinary paint, which gets
        # dark like everything else - and the game will never tell you. Saying "0"
        # here, before the pakset is built, is the whole reason this exists.
        if not hits:
            self.report({"WARNING"},
                        _("%s - but NOTHING lights up: no pixel carries one of the "
                          "engine's light colours, so this runs dark all night")
                        % os.path.basename(dst))
            return {"FINISHED"}

        for line in night.report(hits):
            self.report({"INFO"}, line)
        self.report({"INFO"}, _("%s - %d px will light up")
                    % (os.path.basename(dst), sum(hits.values())))
        return {"FINISHED"}


# The reserved materials, by the enum value the panel offers. Each is (the rgb the
# ARTIST paints, whether it is a reserved special colour). The colour is the one
# makeobj matches against - colors.LAMP_PURPLE is #FF017F, not the #E100E1 the game
# draws - which is the whole reason these go through one place.
_MATERIALS = {
    "window": (colors.WINDOW_DARK, True),
    "window_blue": (colors.WINDOW_LIGHT, True),
    "headlight": (colors.HEADLIGHT, True),
    "lamp_red": (colors.LAMP_RED, True),
    "lamp_green": (colors.LAMP_GREEN, True),
    "lamp_yellow": (colors.LAMP_YELLOW, True),
    "signal_purple": (colors.LAMP_PURPLE, True),
    # a mid shade of the blue ramp: the engine recolours the whole ramp per company,
    # and painting one shade is what marks the region as player-colour
    "player": (colors.PLAYER_RAMP_BLUE[3], True),
}


class SIMUTRANS_OT_apply_material(Operator):
    bl_idname = "simutrans.apply_material"
    bl_label = "Apply to selected"
    bl_translation_context = CTX
    bl_description = ("Give the selected objects a Simutrans material - a "
                      "player colour, a night light, or plain paint")

    def execute(self, context):
        p = context.scene.simutrans

        meshes = [ob for ob in context.selected_objects if ob.type == "MESH"]
        if not meshes:
            say(self, {"ERROR"}, _("Select a mesh object first"))
            return {"CANCELLED"}

        if p.material == "paint":
            rgb = tuple(int(round(c * 255)) for c in p.paint_color)
            mat = rig.make_paint_material(bpy, rgb)
        else:
            rgb, _reserved = _MATERIALS[p.material]
            mat = rig.make_special_color_material(bpy, rgb)

        for ob in meshes:
            if ob.data.materials:
                ob.data.materials[0] = mat
            else:
                ob.data.materials.append(mat)

        say(self, {"INFO"}, _("%s -> %d object(s)") % (mat.name, len(meshes)))
        return {"FINISHED"}


class SIMUTRANS_OT_compile_pak(Operator):
    bl_idname = "simutrans.compile_pak"
    bl_label = "Compile .pak"
    bl_translation_context = CTX
    bl_description = "Run makeobj on the .dat and produce a .pak the game can load"

    def execute(self, context):
        import shutil
        import subprocess

        p = context.scene.simutrans
        out, why = _out_dir(p)
        if out is None:
            self.report({"ERROR"}, why)
            return {"CANCELLED"}

        exe = bpy.path.abspath(p.makeobj_path) if p.makeobj_path else ""
        if not exe:
            self.report({"ERROR"}, _("Set the path to makeobj first"))
            return {"CANCELLED"}
        if not os.path.isfile(exe):
            self.report({"ERROR"}, _("makeobj not found: %s") % exe)
            return {"CANCELLED"}

        dat = os.path.join(out, "%s.dat" % p.basename)
        if not os.path.exists(dat):
            self.report({"ERROR"}, _("No .dat yet - render the sheet first"))
            return {"CANCELLED"}

        pak_name = "%s.pak" % p.basename
        # run IN the output dir: the .dat's image references are relative to it
        proc = subprocess.run(
            [exe, paksets.get(p.pakset).makeobj_arg, pak_name, os.path.basename(dat)],
            cwd=out, capture_output=True, text=True,
        )
        pak = os.path.join(out, pak_name)
        if proc.returncode != 0 or not os.path.exists(pak):
            tail = (proc.stdout + proc.stderr).strip().splitlines()
            self.report({"ERROR"}, _("makeobj failed: %s")
                        % (tail[-1] if tail else "exit %d" % proc.returncode))
            return {"CANCELLED"}

        size = os.path.getsize(pak)
        if not p.install_dir:
            self.report({"INFO"}, _("Compiled %s (%d bytes)") % (pak_name, size))
            return {"FINISHED"}

        dest = bpy.path.abspath(p.install_dir)
        try:
            os.makedirs(dest, exist_ok=True)
            shutil.copy2(pak, os.path.join(dest, pak_name))
        except OSError as e:
            self.report({"ERROR"}, _("Could not install the .pak: %s") % e)
            return {"CANCELLED"}

        self.report({"INFO"}, _("Compiled %s and installed it to %s")
                    % (pak_name, dest))
        return {"FINISHED"}


class SIMUTRANS_PT_panel(Panel):
    bl_label = "Simutrans"
    bl_translation_context = CTX
    bl_idname = "SIMUTRANS_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Simutrans"

    def draw(self, context):
        p = context.scene.simutrans
        pak = paksets.get(p.pakset)
        col = self.layout.column()

        # START. What you are making, then the two buttons that make a scene to
        # make it in. This box used to be called "Rig" and open with the camera,
        # which is the second thing an artist needs and the first thing the kit
        # offered - there was no first thing.
        box = col.box()
        box.label(text="Start", icon="ADD", text_ctxt=CTX)
        box.prop(p, "pakset")
        box.prop(p, "obj_type")
        box.label(text=_("%d px, ortho_scale %.4f")
                       % (pak.tile_px, pak.ortho_scale), text_ctxt=CTX)

        # What to model, for THIS kind of object. Two short lines rather than one
        # long one: at the sidebar's default width a long label is truncated in the
        # middle, and these are instructions, not decoration.
        for line in _MODEL_HINT[p.obj_type]:
            box.label(text=line, icon="INFO" if line is _MODEL_HINT[p.obj_type][0]
                      else "NONE", text_ctxt=CTX)
        box.operator("simutrans.create_template", icon="OUTLINER_COLLECTION")
        box.operator("simutrans.build_rig", icon="OUTLINER_OB_CAMERA")

        box = col.box()
        box.label(text="Materials", icon="MATERIAL", text_ctxt=CTX)
        box.prop(p, "material")
        if p.material == "paint":
            box.prop(p, "paint_color")
        box.operator("simutrans.apply_material", icon="BRUSH_DATA")

        box = col.box()
        box.label(text="Output", icon="RENDER_RESULT", text_ctxt=CTX)
        box.prop(p, "out_dir")

        out, why = _out_dir(p)
        if out is None:
            warn = box.column()
            warn.alert = True
            warn.label(text="Save the .blend, or use an", icon="ERROR", text_ctxt=CTX)
            warn.label(text="absolute Output path", text_ctxt=CTX)

        box.prop(p, "basename")
        if p.obj_type == "vehicle":
            box.prop(p, "dirs")
        box.prop(p, "align_offset")
        box.prop(p, "write_dat")

        acts = box.column()
        acts.enabled = out is not None
        # Validate sits ABOVE Render deliberately: it is the cheap step, and it is
        # the one that answers "is this worth rendering?". It does not need the
        # output path, so it stays enabled when the rest of the box is greyed out -
        # an unsaved .blend is one of the things it exists to tell you about.
        val = box.column()
        val.operator("simutrans.validate", icon="CHECKMARK")

        # Preview sits between Validate and Render: it is the render, of one
        # heading, so it is the cheap way to see what the expensive one will say.
        acts.operator("simutrans.preview", icon="SEQ_PREVIEW")
        if p.preview_fingerprint and workflow.is_stale(bpy, p,
                                                       p.preview_fingerprint):
            # Saying so is the whole difference between a preview and a guess. A
            # stale preview believed current is worse than none.
            stale = acts.column()
            stale.alert = True
            stale.label(text="The scene changed since that", icon="ERROR",
                        text_ctxt=CTX)
            stale.label(text="preview. It is out of date.", text_ctxt=CTX)

        acts.operator("simutrans.render_sheet", icon="RENDER_ANIMATION")
        acts.operator("simutrans.write_dat", icon="FILE_TEXT")
        acts.operator("simutrans.check_colors", icon="COLOR")
        acts.prop(p, "night_level")
        acts.operator("simutrans.night_preview", icon="LIGHT_SUN")

        box = col.box()
        box.label(text="Compile", icon="PACKAGE", text_ctxt=CTX)
        box.prop(p, "makeobj_path")
        box.prop(p, "install_dir")
        comp = box.column()
        comp.enabled = out is not None and bool(p.makeobj_path)
        comp.operator("simutrans.compile_pak", icon="EXPORT")


# The fields that mean something for each kind of object, in the order an artist
# would fill them in. A vehicle's engine_type on a road sign would be noise, and
# noise in a panel is how people stop reading panels.
_DAT_FIELDS = {
    "vehicle": ("obj_name", "author", "waytype", "engine_type", "speed", "power",
                "weight", "length", "freight", "payload", "freight_goods",
                "cost", "runningcost", "intro_year",
                "constraint_prev", "constraint_next"),
    "building": ("obj_name", "author", "btype", "waytype", "enables_pax",
                 "enables_post", "enables_ware", "size_x", "size_y", "layouts",
                 "level", "chance", "seasons", "phases", "intro_year"),
    "way": ("obj_name", "author", "waytype", "topspeed", "cost", "maintenance",
            "intro_year"),
    "wayobj": ("obj_name", "author", "waytype", "own_waytype", "topspeed", "cost",
               "maintenance", "intro_year"),
    "tunnel": ("obj_name", "author", "waytype", "topspeed", "cost", "maintenance",
               "intro_year", "tunnel_way"),
    "bridge": ("obj_name", "author", "waytype", "topspeed", "cost", "maintenance",
               "intro_year", "max_length", "max_height", "pillar_distance"),
    "factory": ("obj_name", "author", "size_x", "size_y", "level",
                "factory_mapcolor", "factory_location", "factory_productivity",
                "factory_output_good", "factory_output_capacity",
                "factory_input_good"),
    "roadsign": ("obj_name", "author", "waytype", "is_signal", "states", "cost",
                 "intro_year"),
}


class SIMUTRANS_PT_dat(Panel):
    bl_label = "Object (.dat)"
    bl_translation_context = CTX
    bl_idname = "SIMUTRANS_PT_dat"
    bl_parent_id = "SIMUTRANS_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Simutrans"

    def draw(self, context):
        p = context.scene.simutrans
        col = self.layout.column()
        for name in _DAT_FIELDS[p.obj_type]:
            col.prop(p, name)

        # THE THIRD SEASON IS NEVER DRAWN, and the artist has to hear it here, at
        # the moment they type the 3, and not from a linter afterwards.
        if p.obj_type == "building" and p.seasons == 3:
            warn = col.column()
            warn.alert = True
            warn.label(text="3 seasons: the engine NEVER", icon="ERROR",
                       text_ctxt=CTX)
            warn.label(text="draws the third. Use 2, 4 or 5.", text_ctxt=CTX)

        if p.obj_type == "roadsign" and p.is_signal and p.states < 2:
            warn = col.column()
            warn.alert = True
            warn.label(text="A signal needs 2 aspects.", icon="ERROR",
                       text_ctxt=CTX)
            warn.label(text="State 0 is RED.", text_ctxt=CTX)


def _vset(p):
    """The variant document, parsed. core/variants.py owns the format."""
    return variants.load(p.variants_json, p.obj_type)


def _save_vset(p, vset):
    p.variants_json = variants.dump(vset)


def _base_fields(p):
    """The panel's own values, as the dict a variant is a diff against."""
    return {name: getattr(p, name) for name in _DAT_FIELDS[p.obj_type]}


def _current(p):
    vset = _vset(p)
    if not vset.variants:
        return vset, None
    i = min(p.variant_index, len(vset.variants) - 1)
    return vset, vset.variants[i]


class SIMUTRANS_OT_variant_add(Operator):
    bl_idname = "simutrans.variant_add"
    bl_label = "Add Variant"
    bl_translation_context = CTX
    bl_description = ("Add a sibling object: the same model, a different name and "
                      "whatever numbers or paint you change. It gets its own .dat")
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        p = context.scene.simutrans
        vset = _vset(p)
        name = (p.variant_name or "").strip() or "%s_%d" % (
            p.obj_name or "Variant", len(vset.variants) + 1)
        mats = {}
        if p.variant_material.strip():
            mats[p.variant_material.strip()] = tuple(
                int(round(c * 255)) for c in p.variant_color)
        vset, v = variants.add(vset, name, materials=mats)
        _save_vset(p, vset)
        p.variant_index = len(vset.variants) - 1
        say(self, {"INFO"}, _("Variant %s added (%d in all)")
            % (v.name, len(vset.variants)))
        return {"FINISHED"}


class SIMUTRANS_OT_variant_duplicate(Operator):
    bl_idname = "simutrans.variant_duplicate"
    bl_label = "Duplicate"
    bl_translation_context = CTX
    bl_description = "Copy the selected variant, keeping what it changes"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        p = context.scene.simutrans
        vset, cur = _current(p)
        if cur is None:
            say(self, {"ERROR"}, _("No variant selected"))
            return {"CANCELLED"}
        vset, copy = variants.duplicate(vset, cur.key)
        _save_vset(p, vset)
        p.variant_index = len(vset.variants) - 1
        say(self, {"INFO"}, _("Variant %s added (%d in all)")
            % (copy.name, len(vset.variants)))
        return {"FINISHED"}


class SIMUTRANS_OT_variant_rename(Operator):
    bl_idname = "simutrans.variant_rename"
    bl_label = "Rename"
    bl_translation_context = CTX
    bl_description = ("Rename the selected variant. Its identity does not move, "
                      "so nothing it changes is lost")
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        p = context.scene.simutrans
        vset, cur = _current(p)
        if cur is None:
            say(self, {"ERROR"}, _("No variant selected"))
            return {"CANCELLED"}
        name = (p.variant_name or "").strip()
        if not name:
            say(self, {"ERROR"}, _("Type the new name first"))
            return {"CANCELLED"}
        _save_vset(p, variants.rename(vset, cur.key, name))
        say(self, {"INFO"}, _("%s is now %s") % (cur.name, name))
        return {"FINISHED"}


class SIMUTRANS_OT_variant_remove(Operator):
    bl_idname = "simutrans.variant_remove"
    bl_label = "Remove"
    bl_translation_context = CTX
    bl_description = "Delete the selected variant"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        p = context.scene.simutrans
        vset, cur = _current(p)
        if cur is None:
            say(self, {"ERROR"}, _("No variant selected"))
            return {"CANCELLED"}
        _save_vset(p, variants.remove(vset, cur.key))
        p.variant_index = max(0, p.variant_index - 1)
        say(self, {"INFO"}, _("Removed %s") % cur.name)
        return {"FINISHED"}


class SIMUTRANS_OT_variant_apply(Operator):
    bl_idname = "simutrans.variant_apply"
    bl_label = "Show in viewport"
    bl_translation_context = CTX
    bl_description = ("Make the scene look like this variant, so you can see it. "
                      "It changes the materials, not the geometry")
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        p = context.scene.simutrans
        _vs, cur = _current(p)
        if cur is None:
            say(self, {"ERROR"}, _("No variant selected"))
            return {"CANCELLED"}
        changed = workflow.apply_variant(bpy, cur, p.pakset)
        say(self, {"INFO"}, _("%s: %d material(s) repainted")
            % (cur.name, len(changed["materials"])))
        return {"FINISHED"}


class SIMUTRANS_OT_variant_check(Operator):
    bl_idname = "simutrans.variant_check"
    bl_label = "Check Variants"
    bl_translation_context = CTX
    bl_description = ("Duplicate names, broken references, and axes the engine "
                      "does not actually index")

    def execute(self, context):
        p = context.scene.simutrans
        vset = _vset(p)
        findings = variants.check(vset, _base_fields(p),
                                  collections=workflow.scene_collections(bpy),
                                  materials=workflow.scene_materials(bpy))
        for f in findings:
            level = {variants.ERROR: "ERROR",
                     variants.WARNING: "WARNING"}.get(f.level, "INFO")
            say(self, {level}, "%s: %s" % (f.code, _(f.message)))
        errs = variants.blocking(findings)
        if errs:
            say(self, {"ERROR"}, _("%d error(s) - fix these before rendering")
                % len(errs))
        else:
            say(self, {"INFO"}, _("%d variant(s), nothing wrong")
                % len(vset.variants))
        return {"FINISHED"}


class SIMUTRANS_OT_render_variants(Operator):
    bl_idname = "simutrans.render_variants"
    bl_label = "Render All Variants"
    bl_translation_context = CTX
    bl_description = ("Render every variant, each to its own sheet and .dat. The "
                      "geometry is rendered once per variant, never duplicated")

    def execute(self, context):
        p = context.scene.simutrans
        out, why = _out_dir(p)
        if out is None:
            say(self, {"ERROR"}, why)
            return {"CANCELLED"}

        vset = _vset(p)
        if not vset.variants:
            say(self, {"ERROR"}, _("No variants to render"))
            return {"CANCELLED"}

        base = _base_fields(p)
        errs = variants.blocking(variants.check(
            vset, base, collections=workflow.scene_collections(bpy),
            materials=workflow.scene_materials(bpy)))
        if errs:
            # Refused rather than half-done: N-1 correct .dat files and one wrong
            # one is worse than none, because the wrong one looks finished.
            for f in errs:
                say(self, {"ERROR"}, "%s: %s" % (f.code, _(f.message)))
            say(self, {"ERROR"}, _("%d error(s) - fix these before rendering")
                % len(errs))
            return {"CANCELLED"}

        made = []
        for v in vset.variants:
            workflow.apply_variant(bpy, v, p.pakset)
            fields = variants.resolve(v, base)
            frames = rig.render_directions(
                bpy, out, p.pakset, dirs=int(p.dirs), basename=v.name,
                align_offset=tuple(p.align_offset))
            _png, dat, _pl = rig.build_sheet_and_dat(
                frames, out, p.pakset, basename=v.name, cols=4,
                name=fields["obj_name"], author=fields.get("author", ""),
                waytype=fields.get("waytype", "track"),
                engine_type=fields.get("engine_type", "diesel"),
                speed=fields.get("speed", 100), power=fields.get("power", 0),
                weight=fields.get("weight", 20), length=fields.get("length", 8),
                payload=fields.get("payload", 0),
                freight=fields.get("freight", "None"),
                cost=fields.get("cost", 0),
                runningcost=fields.get("runningcost", 0),
                intro_year=fields.get("intro_year", 1900),
                constraint_prev=_names(fields.get("constraint_prev", "")),
                constraint_next=_names(fields.get("constraint_next", "")))
            made.append(os.path.basename(dat))
            _report_lint(self, dat)

        say(self, {"INFO"}, _("%d variant(s) rendered: %s")
            % (len(made), ", ".join(made)))
        return {"FINISHED"}


class SIMUTRANS_OT_refresh_components(Operator):
    bl_idname = "simutrans.refresh_components"
    bl_label = "Refresh"
    bl_translation_context = CTX
    bl_description = "Look again for components, here and in the project folder"

    def execute(self, context):
        p = context.scene.simutrans
        comps = library.catalogue(bpy)
        usable = components.usable(comps, p.pakset)
        for c in comps:
            for f in components.check(c, p.pakset):
                if f.level == components.ERROR:
                    say(self, {"WARNING"}, "%s: %s" % (c.key, _(f.message)))
        if not comps:
            say(self, {"INFO"},
                _("No components found. They live in a 'components' folder next "
                  "to your .blend"))
            return {"FINISHED"}
        say(self, {"INFO"}, _("%d component(s), %d usable: %s")
            % (len(comps), len(usable), ", ".join(c.key for c in usable)))
        return {"FINISHED"}


class SIMUTRANS_OT_insert_component(Operator):
    bl_idname = "simutrans.insert_component"
    bl_label = "Insert Component"
    bl_translation_context = CTX
    bl_description = ("Bring a component into this scene, at its own anchor and "
                      "the right size")
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        p = context.scene.simutrans
        key = (p.component_key or "").strip()
        if not key:
            say(self, {"ERROR"}, _("Type a component key - press Refresh to "
                                   "see what is available"))
            return {"CANCELLED"}
        comp = library.find(key, bpy)
        if comp is None:
            say(self, {"ERROR"}, _("No component called %r") % key)
            return {"CANCELLED"}
        try:
            col = library.insert(bpy, comp, p.component_mode,
                                 pakset_name=p.pakset)
        except ValueError as e:
            say(self, {"ERROR"}, str(e))
            return {"CANCELLED"}
        for f in components.check(comp, p.pakset):
            if f.level == components.WARNING:
                say(self, {"WARNING"}, _(f.message))
        say(self, {"INFO"}, _("%s inserted (%s), licence %s")
            % (comp.name or comp.key, p.component_mode, comp.license))
        return {"FINISHED"}


class SIMUTRANS_OT_preview(Operator):
    bl_idname = "simutrans.preview"
    bl_label = "Preview"
    bl_translation_context = CTX
    bl_description = ("Render ONE heading through the final render's own code "
                      "path, and check it. Not a second renderer - the same one, "
                      "fewer headings")

    def execute(self, context):
        p = context.scene.simutrans
        out, why = _out_dir(p)
        if out is None:
            say(self, {"ERROR"}, why)
            return {"CANCELLED"}
        mins, maxs = rig.scene_bounds(bpy)
        if maxs[2] <= mins[2]:
            say(self, {"ERROR"}, _("Nothing to render - the scene has no mesh"))
            return {"CANCELLED"}

        png, mark = workflow.preview(bpy, out, p)
        p.preview_fingerprint = mark
        for line in workflow.preview_report(bpy, png, p):
            say(self, {"INFO"}, line)
        say(self, {"INFO"}, _("%s - heading '%s', same camera as the final render")
            % (os.path.basename(png), workflow.PREVIEW_CODE))
        return {"FINISHED"}


class SIMUTRANS_OT_package(Operator):
    bl_idname = "simutrans.package"
    bl_label = "Build Package"
    bl_translation_context = CTX
    bl_description = ("Gather the .dat, the sprites, the licence and a manifest "
                      "into one zip. Nothing is uploaded")

    def execute(self, context):
        p = context.scene.simutrans
        out, why = _out_dir(p)
        if out is None:
            say(self, {"ERROR"}, why)
            return {"CANCELLED"}

        vset = _vset(p)
        objects = tuple(v.name for v in vset.variants) or (p.obj_name,)
        man = package.Manifest(
            name=p.obj_name, author=p.author, version=p.pkg_version,
            license=p.pkg_license, pakset=p.pakset, category=p.pkg_category,
            description=p.pkg_description, objects=objects)
        pkg = package.plan(out, man)

        for f in package.check(pkg):
            level = {package.ERROR: "ERROR",
                     package.WARNING: "WARNING"}.get(f.level, "INFO")
            say(self, {level}, "%s: %s" % (f.code, _(f.message)))

        errs = package.blocking(package.check(pkg))
        if errs:
            say(self, {"ERROR"}, _("%d error(s) - the package was NOT written")
                % len(errs))
            return {"CANCELLED"}

        dest = bpy.path.abspath(p.pkg_dir) if p.pkg_dir else out
        zip_path = os.path.join(dest, "%s.zip" % (p.obj_name or "package"))
        try:
            package.write(pkg, zip_path, prefix=p.obj_name or "")
        except (ValueError, OSError) as e:
            say(self, {"ERROR"}, str(e))
            return {"CANCELLED"}
        say(self, {"INFO"}, _("%s - %d file(s). Nothing was uploaded")
            % (os.path.basename(zip_path), len(pkg.files)))
        return {"FINISHED"}


class SIMUTRANS_PT_reference(Panel):
    """Reference photos. A sub-panel, closed by default, because an artist who
    has no photo should not have to scroll past six fields to reach Render."""
    bl_label = "Reference photos"
    bl_translation_context = CTX
    bl_idname = "SIMUTRANS_PT_reference"
    bl_parent_id = "SIMUTRANS_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Simutrans"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        p = context.scene.simutrans
        col = self.layout.column()
        col.prop(p, "ref_image")
        col.prop(p, "ref_side")
        col.prop(p, "ref_length_m")
        col.prop(p, "metres_per_tile")
        act = col.column()
        act.enabled = bool(p.ref_image)
        act.operator("simutrans.setup_reference", icon="IMAGE_REFERENCE")


class SIMUTRANS_PT_variants(Panel):
    """Sibling objects. Closed by default: a first object needs none of this."""
    bl_label = "Variants"
    bl_translation_context = CTX
    bl_idname = "SIMUTRANS_PT_variants"
    bl_parent_id = "SIMUTRANS_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Simutrans"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        p = context.scene.simutrans
        col = self.layout.column()
        vset, cur = _current(p)

        # THE thing an artist needs told, and the engine's own limit. A variant is
        # a separate object; it is not a livery slot, because there is no such
        # slot in base Simutrans.
        col.label(text="A variant is a separate object,", icon="INFO",
                  text_ctxt=CTX)
        col.label(text="with its own name and .dat.", text_ctxt=CTX)

        col.prop(p, "variant_name")
        col.prop(p, "variant_material")
        col.prop(p, "variant_color")
        row = col.row(align=True)
        row.operator("simutrans.variant_add", icon="ADD")
        row.operator("simutrans.variant_duplicate", icon="DUPLICATE")

        if not vset.variants:
            col.label(text="No variants yet.", text_ctxt=CTX)
            return

        col.separator()
        col.prop(p, "variant_index", slider=True)
        if cur is not None:
            box = col.box()
            box.label(text=cur.name, icon="OBJECT_DATA", text_ctxt=CTX)
            # What it INHERITS. An artist looking at a variant needs to know what
            # they are not looking at: a field they believe they set and did not
            # is how a whole family ships with one car's weight.
            n_over = len(cur.overrides or {}) + len(cur.materials or {})
            box.label(text=_("%d changed, the rest inherited") % n_over,
                      text_ctxt=CTX)
            row = box.row(align=True)
            row.operator("simutrans.variant_rename", icon="GREASEPENCIL")
            row.operator("simutrans.variant_remove", icon="X")
            box.operator("simutrans.variant_apply", icon="HIDE_OFF")

        col.separator()
        col.operator("simutrans.variant_check", icon="CHECKMARK")
        acts = col.column()
        acts.enabled = _out_dir(p)[0] is not None
        acts.operator("simutrans.render_variants", icon="RENDER_ANIMATION")


class SIMUTRANS_PT_components(Panel):
    bl_label = "Components"
    bl_translation_context = CTX
    bl_idname = "SIMUTRANS_PT_components"
    bl_parent_id = "SIMUTRANS_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Simutrans"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        p = context.scene.simutrans
        col = self.layout.column()
        col.prop(p, "component_key")
        col.prop(p, "component_mode")
        row = col.row(align=True)
        row.operator("simutrans.refresh_components", icon="FILE_REFRESH")
        row.operator("simutrans.insert_component", icon="IMPORT")


class SIMUTRANS_PT_publish(Panel):
    bl_label = "Publish"
    bl_translation_context = CTX
    bl_idname = "SIMUTRANS_PT_publish"
    bl_parent_id = "SIMUTRANS_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Simutrans"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        p = context.scene.simutrans
        col = self.layout.column()
        col.prop(p, "pkg_version")
        col.prop(p, "pkg_license")
        if not p.pkg_license.strip():
            warn = col.column()
            warn.alert = True
            warn.label(text="A licence is required. Without", icon="ERROR",
                       text_ctxt=CTX)
            warn.label(text="one nobody may ship your work.", text_ctxt=CTX)
        col.prop(p, "pkg_category")
        col.prop(p, "pkg_description")
        col.prop(p, "pkg_dir")
        acts = col.column()
        acts.enabled = _out_dir(p)[0] is not None
        acts.operator("simutrans.package", icon="PACKAGE")
        col.label(text="Nothing is uploaded.", icon="INFO", text_ctxt=CTX)


CLASSES = (SimutransProps, SIMUTRANS_OT_build_rig, SIMUTRANS_OT_create_template,
           SIMUTRANS_OT_setup_reference, SIMUTRANS_OT_validate,
           SIMUTRANS_OT_render_sheet,
           SIMUTRANS_OT_write_dat, SIMUTRANS_OT_check_colors,
           SIMUTRANS_OT_night_preview, SIMUTRANS_OT_apply_material,
           SIMUTRANS_OT_compile_pak,
           SIMUTRANS_OT_variant_add, SIMUTRANS_OT_variant_duplicate,
           SIMUTRANS_OT_variant_rename, SIMUTRANS_OT_variant_remove,
           SIMUTRANS_OT_variant_apply, SIMUTRANS_OT_variant_check,
           SIMUTRANS_OT_render_variants,
           SIMUTRANS_OT_refresh_components, SIMUTRANS_OT_insert_component,
           SIMUTRANS_OT_preview, SIMUTRANS_OT_package,
           SIMUTRANS_PT_panel, SIMUTRANS_PT_dat,
           SIMUTRANS_PT_reference, SIMUTRANS_PT_variants,
           SIMUTRANS_PT_components, SIMUTRANS_PT_publish)


_TRANSLATION_DOMAIN = "simutrans_blender_kit"


def register():
    # before the classes: their bl_label / property names are looked up as they
    # are registered
    bpy.app.translations.register(_TRANSLATION_DOMAIN,
                                  translations.as_blender_dict())
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.simutrans = bpy.props.PointerProperty(type=SimutransProps)


def unregister():
    del bpy.types.Scene.simutrans
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
    bpy.app.translations.unregister(_TRANSLATION_DOMAIN)
