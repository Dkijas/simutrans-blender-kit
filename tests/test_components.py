"""The component catalogue, without Blender.

    python tests/test_components.py

A component library is a thing that copies other people's work into other
people's projects. That is the whole point of it, and it is why the licence and
the author are ERRORS here rather than warnings: the moment a component is
inserted it is in somebody's pakset, and "may we ship this?" has no answer and
nobody to ask. Both halves are tested - the unlicensed one refused, the licensed
one let through.

The other error is an absolute path, which is refused rather than normalised: it
means the catalogue works only on the machine that wrote it, and the failure - a
component that vanishes on a colleague's checkout - looks like a bug in the tool
rather than in the data.
"""

import json
import os
import shutil
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core import components as C                                # noqa: E402

FAILED = []


def check(name, cond, detail=""):
    if cond:
        print("  ok   %s" % name)
    else:
        print("  FAIL %s  %s" % (name, detail))
        FAILED.append(name)


def codes(findings):
    return [f.code for f in findings]


GOOD = {"key": "bogie_y25", "name": "Y25 bogie", "category": "bogie",
        "author": "victor_18993", "license": "MIT", "version": "1.0.0",
        "blend": "bogie_y25.blend", "collection": "bogie",
        "anchor": [0.0, 0.0, 0.45], "pakset": ""}


def _library(*comps):
    """A catalogue on disk. Each comp is a dict; its .blend is made unless the
    test wants it missing."""
    root = tempfile.mkdtemp(prefix="bkitlib")
    for raw in comps:
        d = os.path.join(root, raw.get("key", "x"))
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, C.SIDECAR), "w", encoding="utf-8") as f:
            json.dump(raw, f)
        blend = raw.get("blend", "")
        if blend and not raw.pop("_no_blend", False) and "/" not in blend \
                and not blend.startswith(("C:", "/")):
            open(os.path.join(d, blend), "wb").write(b"BLENDER-fake")
    return root


# --- reading -----------------------------------------------------------------

def test_a_catalogue_is_read_from_disk():
    root = _library(GOOD, dict(GOOD, key="panto_ac", category="pantograph",
                               blend="panto_ac.blend", collection="panto"))
    try:
        comps = C.catalogue(root)
        check("both components found", len(comps) == 2, str([c.key for c in comps]))
        check("sorted by key", [c.key for c in comps] == ["bogie_y25", "panto_ac"])
        check("metadata survives", comps[0].name == "Y25 bogie")
        check("the anchor is a tuple of floats",
              comps[0].anchor == (0.0, 0.0, 0.45))
        check("and it knows where it came from", comps[0].source.endswith("bogie_y25"))
    finally:
        shutil.rmtree(root)


def test_a_directory_with_no_sidecar_is_not_a_component():
    root = tempfile.mkdtemp(prefix="bkitlib")
    try:
        os.makedirs(os.path.join(root, "just_a_folder"))
        check("it is ignored, not an error", C.catalogue(root) == ())
    finally:
        shutil.rmtree(root)


def test_a_broken_sidecar_does_not_take_the_catalogue_down():
    root = _library(GOOD)
    try:
        d = os.path.join(root, "broken")
        os.makedirs(d)
        open(os.path.join(d, C.SIDECAR), "w").write("{ not json")
        comps = C.catalogue(root)
        check("the good one still loads", [c.key for c in comps] == ["bogie_y25"])
    finally:
        shutil.rmtree(root)


def test_a_local_component_shadows_a_shared_one():
    """The useful direction: a project's override should not need permission from
    the library it overrides."""
    shared = _library(dict(GOOD, name="Shared Y25"))
    local = _library(dict(GOOD, name="My Y25"))
    try:
        comps = C.catalogue(local, shared)
        check("one component, not two", len(comps) == 1)
        check("and it is the local one", comps[0].name == "My Y25")
        # and the other way round, to prove order is what decides it
        comps = C.catalogue(shared, local)
        check("order is what decides", comps[0].name == "Shared Y25")
    finally:
        shutil.rmtree(shared)
        shutil.rmtree(local)


def test_a_missing_root_is_not_an_error():
    check("a catalogue over nothing is empty",
          C.catalogue("/no/such/place", "", None) == ())


def test_by_category_groups():
    root = _library(GOOD, dict(GOOD, key="panto_ac", category="pantograph",
                               blend="panto_ac.blend"))
    try:
        groups = C.by_category(C.catalogue(root))
        check("two categories", sorted(groups) == ["bogie", "pantograph"])
        check("each with its component", len(groups["bogie"]) == 1)
    finally:
        shutil.rmtree(root)


# --- licence, the reason this module is careful ------------------------------

def test_an_unlicensed_component_is_refused():
    root = _library(dict(GOOD, license=""))
    try:
        c = C.catalogue(root)[0]
        f = C.check(c)
        check("no licence is an error", "no-license" in codes(f))
        check("and it blocks", "no-license" in codes(C.blocking(f)))
        check("so the panel will not offer it", C.usable(C.catalogue(root)) == ())
    finally:
        shutil.rmtree(root)


def test_an_unattributed_component_is_refused():
    root = _library(dict(GOOD, author=""))
    try:
        f = C.check(C.catalogue(root)[0])
        check("no author is an error", "no-author" in codes(f))
        check("because a licence with nobody behind it grants nothing",
              any("grants nothing" in x.message for x in f))
    finally:
        shutil.rmtree(root)


def test_a_properly_licensed_component_is_offered():
    root = _library(GOOD)
    try:
        comps = C.catalogue(root)
        check("a good component raises no error", C.blocking(C.check(comps[0])) == (),
              str(codes(C.check(comps[0]))))
        check("and the panel offers it", len(C.usable(comps)) == 1)
    finally:
        shutil.rmtree(root)


# --- paths -------------------------------------------------------------------

def test_an_absolute_path_is_refused():
    for bad in ("C:/Users/somebody/bogie.blend", "/home/somebody/bogie.blend",
                "//server/share/bogie.blend"):
        root = _library(dict(GOOD, blend=bad))
        try:
            f = C.check(C.catalogue(root)[0])
            check("%r is refused" % bad[:28], "absolute-path" in codes(f))
        finally:
            shutil.rmtree(root)


def test_a_relative_path_resolves_against_the_sidecar():
    root = _library(GOOD)
    try:
        c = C.catalogue(root)[0]
        check("blend_path finds the file", os.path.isfile(c.blend_path()),
              str(c.blend_path()))
        check("and it is not an absolute path in the data",
              not os.path.isabs(c.blend))
    finally:
        shutil.rmtree(root)


def test_a_missing_blend_is_caught():
    root = _library(GOOD)
    try:
        os.remove(os.path.join(root, "bogie_y25", "bogie_y25.blend"))
        f = C.check(C.catalogue(root)[0])
        check("a component whose .blend is gone is an error",
              "missing-blend" in codes(f))
    finally:
        shutil.rmtree(root)


def test_a_climbing_path_is_a_warning():
    root = _library(dict(GOOD, blend="../elsewhere/bogie.blend"))
    try:
        f = C.check(C.catalogue(root)[0])
        check("reaching outside its own folder is reported",
              "climbing-path" in codes(f))
    finally:
        shutil.rmtree(root)


# --- the rest ----------------------------------------------------------------

def test_a_component_with_no_collection_is_refused():
    root = _library(dict(GOOD, collection=""))
    try:
        check("not saying what to bring over is an error",
              "no-collection" in codes(C.check(C.catalogue(root)[0])))
    finally:
        shutil.rmtree(root)


def test_a_bad_key_is_refused():
    # A key is internal - it never reaches the .dat - so the rule is only what it
    # needs to be: no spaces (it goes in a UI list), no case (two keys differing
    # by case would be two components on a case-insensitive filesystem and one on
    # a case-sensitive one), no separators.
    for bad in ("", "Has Space", "UPPER", "sla/sh", "dot.ted", "back\\slash"):
        c = C.parse(dict(GOOD, key=bad))
        check("%r is not a usable key" % bad, "bad-key" in codes(C.check(c)))
    # `4wheel` is fine and an earlier version of this test said it was not - it
    # demanded a rule nothing had stated and nothing needed.
    for good in ("bogie_y25", "panto-ac", "x", "a1", "4wheel"):
        c = C.parse(dict(GOOD, key=good))
        check("%r is a fine key" % good, "bad-key" not in codes(C.check(c)))


def test_two_components_sharing_a_key_are_refused():
    a = C.parse(GOOD, source="x")
    check("a duplicate key is an error",
          "duplicate-key" in codes(C.check_catalogue((a, a))))


def test_another_paksets_component_is_a_warning_not_an_error():
    """tile_world is 2.0 in every shipped profile, so a pak64 bogie is the right
    SIZE in pak128. What differs is the pixel count it was drawn for - which is a
    judgement about the art, so the artist makes it."""
    root = _library(dict(GOOD, pakset="pak64"))
    try:
        c = C.catalogue(root)[0]
        f = C.check(c, pakset="pak128")
        check("it is reported", "other-pakset" in codes(f))
        check("as a WARNING, not an error",
              "other-pakset" not in codes(C.blocking(f)))
        check("and the message says the size is fine",
              any("right size" in x.message for x in f))
        check("the matching pakset says nothing",
              "other-pakset" not in codes(C.check(c, pakset="pak64")))
        check("and a component with no pakset fits anywhere",
              "other-pakset" not in codes(
                  C.check(C.parse(GOOD, source="x"), pakset="pak128")))
    finally:
        shutil.rmtree(root)


def test_an_unknown_category_is_a_warning():
    c = C.parse(dict(GOOD, category="doohickey"))
    f = C.check(c)
    check("it is reported", "unknown-category" in codes(f))
    check("but it still works", "unknown-category" not in codes(C.blocking(f)))


def test_a_garbled_sidecar_field_does_not_raise():
    for raw in (dict(GOOD, anchor="nonsense"), dict(GOOD, anchor=[1, 2]),
                dict(GOOD, anchor=None), dict(GOOD, anchor=["a", "b", "c"])):
        try:
            c = C.parse(raw)
            ok = c is not None and len(c.anchor) == 3
        except Exception as e:                                   # noqa: BLE001
            ok = False
            print("      %s" % e)
        check("anchor=%r survives parsing" % (raw["anchor"],), ok)
    check("a non-dict is not a component", C.parse("hello") is None)


def test_the_modes_are_the_three_blender_really_has():
    check("append, link and instance", set(C.MODES) == {"append", "link", "instance"})


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            print("\n%s" % name)
            fn()
    print()
    if FAILED:
        print("COMPONENT_TESTS_FAILED: %d" % len(FAILED))
        for f in FAILED:
            print("  - %s" % f)
        sys.exit(1)
    print("COMPONENT_TESTS_OK")


if __name__ == "__main__":
    main()
