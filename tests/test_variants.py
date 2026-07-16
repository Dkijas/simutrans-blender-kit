"""Variants, without Blender.

    python tests/test_variants.py

The load-bearing test in this file is test_the_axes_match_the_engines_own_writers.
Everything else guards the bookkeeping; that one guards the CLAIM - that a
vehicle has no season, that a way-object has no variant axis at all, and that
there is no such thing as a livery in base Simutrans. If AXES ever drifts from
what the writers index, this tool starts confidently offering variants that
compile and are never drawn, which is worse than not offering them.

Every rule is tested with a case that trips it and one that must not.
"""

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core import schema, variants as V                          # noqa: E402

FAILED = []


def check(name, cond, detail=""):
    if cond:
        print("  ok   %s" % name)
    else:
        print("  FAIL %s  %s" % (name, detail))
        FAILED.append(name)


def codes(findings):
    return [f.code for f in findings]


BASE = {"obj_name": "Loco", "author": "me", "waytype": "track", "power": 500,
        "weight": 20, "length": 8, "obj_type": "vehicle"}


def _set(*names, **kw):
    vs = V.VariantSet(obj_type=kw.pop("obj_type", "vehicle"), **kw)
    for n in names:
        vs, _v = V.add(vs, n, materials={"Body": (1, 2, 3)})
    return vs


# --- the claim ---------------------------------------------------------------

def test_the_axes_match_the_engines_own_writers():
    """AXES is not a list from a tutorial. Each entry must be justified by the
    image keys the type's writer actually builds, per core/dat_schema.json, which
    tools/extract_dat_schema.py pulls out of the engine and test_schema_drift.py
    holds to it."""
    # obj_type in the panel -> obj= in the .dat
    engine_name = {"vehicle": "vehicle", "building": "building", "way": "way",
                   "wayobj": "way-object", "roadsign": "roadsign",
                   "tunnel": "tunnel", "bridge": "bridge", "factory": "factory"}
    for ours, theirs in sorted(engine_name.items()):
        d = schema.OBJ_TYPES.get(theirs)
        check("the schema knows what a %s is" % theirs, d is not None)
        if not d:
            continue
        pats = [p for p in d.get("patterns", []) if "image" in p.lower()]
        widest = max((p.count("[") for p in pats), default=0)
        axes = V.AXES[ours]
        if axes:
            # every axis needs somewhere to be indexed: direction/ribi plus the
            # axes themselves
            check("a %s indexes enough to carry %d axis/axes"
                  % (ours, len(axes)), widest >= len(axes),
                  "widest key has %d indices, axes=%s" % (widest, axes))

    # The three specific claims the docs make, checked rather than asserted.
    veh = [p for p in schema.OBJ_TYPES["vehicle"]["patterns"] if "image" in p]
    check("a vehicle's only indexed variant is freight",
          any("freightimage[%d]" in p for p in veh), str(veh))
    check("and it has no season/state key at all",
          not any(p.startswith("image[%s][") for p in veh), str(veh))

    wayobj = [p for p in schema.OBJ_TYPES["way-object"]["patterns"]
              if p.startswith(("backimage", "frontimage"))]
    check("a way-object indexes ribi and nothing else",
          all(p.count("[") == 1 for p in wayobj), str(wayobj))
    check("so AXES gives it no axes", V.AXES["wayobj"] == ())


def test_a_livery_is_refused_with_the_reason():
    vs = V.VariantSet(obj_type="vehicle", axes={"livery": 2})
    f = V.check(vs)
    check("asking for a livery axis is an error", "not-an-axis" in codes(f))
    check("and it blocks", "not-an-axis" in codes(V.blocking(f)))
    check("the message says liveries are an Extended feature",
          any("Extended" in x.message for x in f))


def test_a_night_variant_is_refused_because_the_engine_does_it():
    for axis in ("night", "day"):
        f = V.check(V.VariantSet(obj_type="vehicle", axes={axis: 2}))
        check("a %r axis is refused" % axis, "not-an-axis" in codes(f))
    check("and the reason names the engine's own table",
          any("hours2night" in x.message
              for x in V.check(V.VariantSet(obj_type="vehicle",
                                            axes={"night": 2}))))


def test_an_axis_the_type_does_not_have_is_refused():
    f = V.check(V.VariantSet(obj_type="wayobj", axes={"season": 4}))
    check("a seasonal catenary is an error", "wrong-axis" in codes(f))
    f = V.check(V.VariantSet(obj_type="vehicle", axes={"season": 4}))
    check("a seasonal vehicle is an error", "wrong-axis" in codes(f))
    # and the ones that ARE real must pass
    for obj_type, axis in (("building", "season"), ("building", "phase"),
                           ("way", "season"), ("roadsign", "state"),
                           ("vehicle", "freight"), ("tunnel", "season")):
        f = V.check(V.VariantSet(obj_type=obj_type, axes={axis: 2}))
        check("a %s CAN have a %s axis" % (obj_type, axis),
              "wrong-axis" not in codes(f) and "not-an-axis" not in codes(f),
              str(codes(f)))


# --- editing -----------------------------------------------------------------

def test_create_duplicate_rename_delete():
    vs = V.VariantSet(obj_type="vehicle")
    vs, a = V.add(vs, "Green", materials={"Body": (0, 120, 0)})
    vs, b = V.add(vs, "Red", overrides={"power": 800})
    check("two variants", len(vs.variants) == 2)
    check("distinct keys", a.key != b.key)

    vs, dup = V.duplicate(vs, a.key)
    check("a duplicate gets a NEW key", dup.key not in (a.key, b.key))
    check("and keeps the overrides", dup.materials == a.materials)
    check("and does NOT reuse the name", dup.name != a.name, dup.name)

    vs = V.rename(vs, a.key, "RENFE_269")
    check("rename changes the name", V.get(vs, a.key).name == "RENFE_269")
    check("and does NOT move the key", V.get(vs, a.key).key == a.key)
    check("and keeps the overrides",
          V.get(vs, a.key).materials == {"Body": (0, 120, 0)})

    vs = V.remove(vs, b.key)
    check("remove takes one out", len(vs.variants) == 2)
    check("the right one", V.get(vs, b.key) is None)
    check("and leaves the others", V.get(vs, a.key) is not None)


def test_a_key_is_never_reused():
    """The bug this test was written for and found.

    The first implementation scanned the live variants and took the lowest free
    number, so deleting v00000000 and adding a variant handed out v00000000 again
    - and any reference held anywhere silently came to mean a different variant.
    The docstring claimed keys were never reused while the code reused them.
    """
    vs = V.VariantSet(obj_type="vehicle")
    vs, a = V.add(vs, "A")
    vs, b = V.add(vs, "B")
    vs = V.remove(vs, a.key)
    vs, c = V.add(vs, "C")
    check("a new variant does not take a dead key", c.key != a.key,
          "%s vs %s" % (c.key, a.key))
    check("nor a live one", c.key != b.key)


def test_the_key_counter_survives_a_save_and_load():
    """Which is the half that matters: a counter held only in memory is a counter
    that resets every time the .blend is reopened, and then the reuse is back."""
    vs = V.VariantSet(obj_type="vehicle")
    vs, a = V.add(vs, "A")
    vs, b = V.add(vs, "B")
    vs = V.remove(vs, a.key)
    vs = V.remove(vs, b.key)
    check("the counter is written out", '"next_key": 2' in V.dump(vs))

    reopened = V.load(V.dump(vs))
    reopened, c = V.add(reopened, "C")
    check("a reopened file does not reissue a dead key",
          c.key not in (a.key, b.key), "%s in %s" % (c.key, (a.key, b.key)))


def test_a_hand_edited_counter_cannot_hand_out_a_live_key():
    """Somebody rewinds next_key in a text editor. The live keys must still win."""
    doc = ('{"schema_version": 1, "next_key": 0, "variants": ['
           '{"key": "v00000005", "name": "Live"}]}')
    vs = V.load(doc)
    vs, fresh = V.add(vs, "New")
    check("the counter is lifted above every live key", fresh.key != "v00000005")
    check("and above, not merely away from, it",
          int(fresh.key[1:], 16) > 5, fresh.key)


def test_removing_something_that_is_not_there_is_not_a_crash():
    vs = _set("A")
    check("remove of an unknown key is a no-op", len(V.remove(vs, "v0000dead").variants) == 1)
    check("duplicate of an unknown key returns None",
          V.duplicate(vs, "v0000dead")[1] is None)


# --- persistence -------------------------------------------------------------

def test_round_trip_is_lossless_and_stable():
    vs = _set("Green", "Red")
    vs, _v = V.add(vs, "Blue", overrides={"power": 900}, materials={"Roof": (1, 1, 1)},
                   show=("extra",), hide=("plain",), note="the odd one")
    text = V.dump(vs)
    back = V.load(text)
    check("everything survives a round trip", back.variants == vs.variants)
    check("serialising twice gives the same bytes", V.dump(back) == text)
    check("the version is stamped", '"schema_version": 1' in text)


def test_an_empty_or_broken_document_loses_nothing_it_had():
    """A .blend whose property is empty, truncated or from an older kit must open
    with no variants - not fail to open."""
    for text in ("", "   ", "not json at all", "[]", "null", "42", '"a string"',
                 '{"variants": 3}', '{"variants": "no"}', '{"variants": {}}',
                 '{"schema_version": "banana"}', '{"variants": [1, 2, "x"]}',
                 '{"schema_version": -1, "variants": null}',
                 '{"variants": [], "axes": 7}', '{"variants": [], "axes": "x"}',
                 '{"next_key": true, "variants": []}',
                 '{"next_key": -5, "variants": []}'):
        try:
            vs = V.load(text)
            ok = isinstance(vs, V.VariantSet) and vs.variants == ()
            why = ""
        except Exception as e:                                   # noqa: BLE001
            # "never raises on rubbish" is the docstring's promise, and the first
            # version of load() broke it on {"variants": 3} - `for item in 3`.
            ok, why = False, "raised %s: %s" % (type(e).__name__, e)
        check("%r loads as an empty set" % (text[:24],), ok, why)


def test_a_variant_whose_fields_are_the_wrong_type_is_survived():
    """Every field of a stored document is untrusted - a human can edit it."""
    doc = ('{"schema_version": 1, "variants": [{"key": "v00000000", '
           '"name": 42, "overrides": "no", "materials": [1,2], '
           '"show": "notalist", "hide": 9, "note": null}]}')
    try:
        vs = V.load(doc)
        ok = len(vs.variants) == 1
        v = vs.variants[0]
        check("it loads", ok)
        check("the bad fields become empty, not exceptions",
              v.overrides == {} and v.materials == {} and v.show == ()
              and v.hide == ())
        check("and it still round-trips", V.load(V.dump(vs)).variants == vs.variants)
    except Exception as e:                                       # noqa: BLE001
        check("a document with wrong-typed fields does not raise", False,
              "%s: %s" % (type(e).__name__, e))


def test_a_document_from_before_this_module_migrates():
    """v0 is any document without a version - which is also what an empty
    property looks like, so v0 must always mean 'nothing to lose'."""
    old = '{"variants": [{"key": "v00000000", "name": "Old"}]}'
    vs = V.load(old)
    check("a versionless document still loads", len(vs.variants) == 1)
    check("and keeps its variant", vs.variants[0].name == "Old")
    check("and is stamped current on the way out",
          '"schema_version": %d' % V.SCHEMA_VERSION in V.dump(vs))


def test_a_variant_with_no_key_is_given_one():
    """Rather than dropped. The artist's overrides are worth more than our
    bookkeeping."""
    vs = V.load('{"schema_version": 1, "variants": [{"name": "Nameless"}]}')
    check("it survives", len(vs.variants) == 1)
    check("with a fresh, valid key",
          V._KEY_RE.match(vs.variants[0].key) is not None, vs.variants[0].key)


def test_migrate_stops_rather_than_guessing_at_a_gap():
    """A document from a FUTURE version, or one whose ladder has a hole, must not
    be reinterpreted."""
    raw = {"schema_version": 99, "variants": []}
    out = V.migrate(dict(raw), 99)
    check("a future document is not mangled", out.get("variants") == [])


# --- validation --------------------------------------------------------------

def test_duplicate_names_are_refused():
    vs = V.VariantSet(obj_type="vehicle")
    vs, _a = V.add(vs, "Same", materials={"B": (1, 1, 1)})
    vs, _b = V.add(vs, "Same", materials={"B": (2, 2, 2)})
    f = V.check(vs, BASE)
    check("two variants with one name is an error", "duplicate-name" in codes(f))
    check("and it blocks", "duplicate-name" in codes(V.blocking(f)))
    check("distinct names are fine",
          "duplicate-name" not in codes(V.check(_set("A", "B"), BASE)))


def test_a_variant_may_not_shadow_the_base():
    vs = _set("Loco")
    check("same name as the base is an error",
          "shadows-base" in codes(V.check(vs, BASE)))
    check("a different name is not",
          "shadows-base" not in codes(V.check(_set("Loco_2"), BASE)))


def test_a_name_the_writers_cannot_carry_is_refused():
    """The .dat's silent killer from the other end: names are matched literally,
    so a space or a '#' breaks every cross-reference to it - long after makeobj
    said nothing."""
    for bad in ("has space", "hash#es", "semi;colon", "", "   ", "tab\tchar"):
        vs = V.VariantSet(obj_type="vehicle")
        vs, _v = V.add(vs, bad, materials={"B": (1, 1, 1)})
        f = codes(V.check(vs, BASE))
        check("%r is refused as a name=" % bad,
              "bad-name" in f or "no-name" in f, str(f))
    for good in ("Loco", "RENFE_269", "BR-52", "cls.101", "a+b", "X9"):
        vs = V.VariantSet(obj_type="vehicle")
        vs, _v = V.add(vs, good, materials={"B": (1, 1, 1)})
        check("%r is a fine name=" % good, "bad-name" not in codes(V.check(vs, BASE)))


def test_an_unstable_key_is_reported():
    vs = V.VariantSet(obj_type="vehicle",
                      variants=(V.Variant(key="", name="A", materials={"B": (1, 1, 1)}),))
    check("a variant with no key is an error", "unstable-key" in codes(V.check(vs, BASE)))
    vs = V.VariantSet(obj_type="vehicle",
                      variants=(V.Variant(key="Green", name="A", materials={"B": (1, 1, 1)}),))
    check("a key that is really a name is an error",
          "unstable-key" in codes(V.check(vs, BASE)))


def test_two_variants_sharing_a_key_are_refused():
    v = V.Variant(key="v00000000", name="A", materials={"B": (1, 1, 1)})
    vs = V.VariantSet(obj_type="vehicle", variants=(v, v._replace(name="B")))
    check("a shared key is an error", "duplicate-key" in codes(V.check(vs, BASE)))


def test_broken_references_are_caught():
    vs = V.VariantSet(obj_type="vehicle")
    vs, _v = V.add(vs, "Ghost", materials={"NoSuchMaterial": (1, 2, 3)})
    f = V.check(vs, BASE, materials=("Body", "Roof"))
    check("repainting a material that is not there is an error",
          "missing-material" in codes(f))
    check("repainting one that IS there is fine",
          "missing-material" not in codes(
              V.check(_set("Ok"), BASE, materials=("Body",))))

    vs = V.VariantSet(obj_type="vehicle")
    vs, _v = V.add(vs, "Ghost2", show=("no_such_collection",))
    f = V.check(vs, BASE, collections={"real": 1})
    check("showing a collection that is not there is an error",
          "missing-collection" in codes(f))


def test_showing_and_hiding_the_same_thing_is_refused():
    vs = V.VariantSet(obj_type="vehicle")
    vs, _v = V.add(vs, "Confused", show=("x",), hide=("x",))
    check("show and hide of one collection is an error",
          "show-and-hide" in codes(V.check(vs, BASE, collections={"x": 1})))


def test_an_override_of_a_field_that_does_not_exist_is_a_warning():
    vs = V.VariantSet(obj_type="vehicle")
    vs, _v = V.add(vs, "Odd", overrides={"nonsense": 1})
    f = V.check(vs, BASE)
    check("it is reported", "unknown-field" in codes(f))
    check("but it does NOT block - the base may simply be a different type",
          "unknown-field" not in codes(V.blocking(f)))


def test_changing_the_waytype_is_information_not_an_error():
    """An artist may genuinely want the same body on road and rail. Refusing that
    would be the tool having an opinion about their work."""
    vs = V.VariantSet(obj_type="vehicle")
    vs, _v = V.add(vs, "OnRoad", overrides={"waytype": "road"})
    f = V.check(vs, BASE)
    check("it is mentioned", "identity-override" in codes(f))
    check("as INFORMATION",
          all(x.level == V.INFORMATION for x in f if x.code == "identity-override"))
    check("and it does not block", "identity-override" not in codes(V.blocking(f)))


def test_a_variant_that_changes_nothing_is_a_warning():
    vs = V.VariantSet(obj_type="vehicle")
    vs, _v = V.add(vs, "JustARename")
    f = V.check(vs, BASE)
    check("an empty variant is reported", "empty-variant" in codes(f))
    check("but allowed - two catalogue entries with one body is legitimate",
          "empty-variant" not in codes(V.blocking(f)))


def test_a_clean_set_says_nothing_alarming():
    """The half that keeps the tool usable."""
    vs = V.VariantSet(obj_type="vehicle")
    vs, _a = V.add(vs, "Loco_Green", materials={"Body": (0, 120, 0)})
    vs, _b = V.add(vs, "Loco_Red", materials={"Body": (180, 0, 0)},
                   overrides={"power": 800})
    f = V.check(vs, BASE, materials=("Body",))
    check("a good set raises no error", V.blocking(f) == (), str(codes(f)))
    check("and no warning either",
          [x for x in f if x.level == V.WARNING] == [], str(codes(f)))


# --- resolving ---------------------------------------------------------------

def test_resolve_is_a_diff_not_a_copy():
    v = V.Variant(key="v00000000", name="Red", overrides={"power": 800})
    out = V.resolve(v, BASE)
    check("the override wins", out["power"] == 800)
    check("the name comes from the variant", out["obj_name"] == "Red")
    check("everything else is inherited", out["waytype"] == "track"
          and out["weight"] == 20)
    check("the base is not mutated", BASE["power"] == 500)


def test_inherited_says_what_you_are_not_looking_at():
    v = V.Variant(key="v00000000", name="Red", overrides={"power": 800})
    inh = V.inherited(v, BASE)
    check("the overridden field is not listed as inherited", "power" not in inh)
    check("the rest is", inh["weight"] == 20 and inh["waytype"] == "track")


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            print("\n%s" % name)
            fn()
    print()
    if FAILED:
        print("VARIANT_TESTS_FAILED: %d" % len(FAILED))
        for f in FAILED:
            print("  - %s" % f)
        sys.exit(1)
    print("VARIANT_TESTS_OK")


if __name__ == "__main__":
    main()
