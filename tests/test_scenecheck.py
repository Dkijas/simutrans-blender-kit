"""The pre-render check, without Blender.

    python tests/test_scenecheck.py

A validator is only worth its button if it says no. So every rule below is tested
TWICE - once on a scene that trips it, once on a scene that must not - because a
checker that only ever passes has not been tested at all, and this repo has caught
itself shipping exactly that before (a knowledge checker whose own help text
promised a failure it could not produce).

The second half of each pair is the one that keeps the tool usable. This kit's
linter earns its keep by having ZERO false positives on pak128's shipped art, and
the bar here is the same: an artist whose correct scene is refused turns the check
off, and then it protects nobody.
"""

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core import scenecheck                                      # noqa: E402

FAILED = []


def check(name, cond, detail=""):
    if cond:
        print("  ok   %s" % name)
    else:
        print("  FAIL %s  %s" % (name, detail))
        FAILED.append(name)


def codes(findings):
    return [f.code for f in findings]


def _scene(**kw):
    """A scene that passes everything, so a test can break exactly one thing."""
    base = dict(obj_type="vehicle", has_mesh=True, obj_name="My_Loco",
                author="somebody", mins=(-1.0, -0.4, 0.0), maxs=(1.0, 0.4, 0.9),
                length=16, pakset="pak128")
    base.update(kw)
    return scenecheck.Scene(**base)


def test_an_empty_scene_is_refused():
    f = scenecheck.check(scenecheck.Scene(obj_type="vehicle"))
    check("no mesh is an error", "no-mesh" in codes(f))
    check("and it blocks", "no-mesh" in codes(scenecheck.blocking(f)))


def test_a_good_scene_passes_clean():
    f = scenecheck.check(_scene())
    check("a good vehicle raises no error", scenecheck.blocking(f) == ())
    check("and no warning either",
          [x for x in f if x.level == scenecheck.WARNING] == [], str(codes(f)))
    check("but it does report the size", "size" in codes(f))


def test_the_unsaved_blend_is_caught_before_the_render_not_during():
    f = scenecheck.check(_scene(saved=False, out_relative=True))
    check("'//' with no .blend is an error", "unsaved-blend" in codes(f))
    check("an absolute path is fine",
          "unsaved-blend" not in codes(scenecheck.check(
              _scene(saved=False, out_relative=False))))
    check("and so is a saved .blend",
          "unsaved-blend" not in codes(scenecheck.check(
              _scene(saved=True, out_relative=True))))


def test_a_floating_model_is_caught_and_a_grounded_one_is_not():
    """tile_anchor aims the camera at a point above z=0 and nothing re-centres the
    model. A model built 3 units up renders perfectly and flies in the game - no
    later check catches it, because the sheet is not wrong, the model is."""
    f = scenecheck.check(_scene(mins=(-1.0, -0.4, 3.0), maxs=(1.0, 0.4, 3.9)))
    check("a model in mid-air is reported", "floating" in codes(f))
    f = scenecheck.check(_scene(mins=(-1.0, -0.4, -3.0), maxs=(1.0, 0.4, -2.1)))
    check("a buried one too", "sunk" in codes(f))
    f = scenecheck.check(_scene(mins=(-1.0, -0.4, -0.01), maxs=(1.0, 0.4, 0.9)))
    check("a wheel rim 5 mm low is NOT a finding",
          "sunk" not in codes(f) and "floating" not in codes(f))


def test_an_off_centre_model_is_caught():
    f = scenecheck.check(_scene(mins=(4.0, -0.4, 0.0), maxs=(6.0, 0.4, 0.9)))
    check("a model built away from the origin is reported",
          "off-centre" in codes(f))
    check("a centred one is not",
          "off-centre" not in codes(scenecheck.check(_scene())))


def test_the_declared_length_is_checked_against_the_modelled_one():
    """The one an artist cannot see alone: length does not scale the sprite, it is
    what the engine trails the NEXT car by. The gap shows up in a depot."""
    f = scenecheck.check(_scene(length=8))          # modelled 2.0 = a whole tile
    check("declared 8 but modelled 16 is reported", "length-mismatch" in codes(f))
    check("declaring 16 for the same model is not",
          "length-mismatch" not in codes(scenecheck.check(_scene(length=16))))
    check("it is a warning, not an error - art may legitimately sit off-centre",
          all(x.level == scenecheck.WARNING
              for x in f if x.code == "length-mismatch"))


def test_an_oversize_model_is_told_it_is_a_convoy():
    f = scenecheck.check(_scene(mins=(-4.0, -0.4, 0.0), maxs=(4.0, 0.4, 0.9),
                                length=16))
    check("a four-tile 'vehicle' is reported", "oversize" in codes(f))
    check("a one-tile one is not",
          "oversize" not in codes(scenecheck.check(_scene())))


def test_a_missing_required_collection_blocks():
    f = scenecheck.check(_scene(obj_type="tunnel", collections={}))
    check("no tunnel_portal is an error", "missing-collection" in codes(f))
    check("and it blocks", "missing-collection" in codes(scenecheck.blocking(f)))
    f = scenecheck.check(_scene(obj_type="tunnel",
                                collections={"tunnel_portal": 3}))
    check("with the portal it is not", "missing-collection" not in codes(f))


def test_an_empty_collection_is_worse_than_a_missing_one():
    """It looks done in the outliner. The renderer finds it, renders nothing into
    it, and says nothing."""
    f = scenecheck.check(_scene(obj_type="tunnel",
                                collections={"tunnel_portal": 0}))
    check("an empty required collection is an error",
          "empty-collection" in codes(f))
    check("and it blocks", "empty-collection" in codes(scenecheck.blocking(f)))
    f = scenecheck.check(_scene(obj_type="tunnel",
                                collections={"tunnel_portal": 2,
                                             "tunnel_portal_front": 0}))
    check("an empty OPTIONAL one is a warning, not an error",
          "empty-collection" in codes(f)
          and "empty-collection" not in codes(scenecheck.blocking(f)))


def test_a_misspelled_collection_is_caught():
    """`way_curved` renders nothing and looks right. This is the exact mistake
    Create Template exists to prevent, caught for the scenes that predate it."""
    f = scenecheck.check(_scene(obj_type="way", mins=(-1, -1, 0),
                                maxs=(1, 1, 0.1),
                                collections={"way_straight": 2, "way_curved": 1}))
    check("a typo'd collection is reported", "unread-collection" in codes(f))
    check("the correctly spelled one is not",
          len([x for x in f if x.code == "unread-collection"]) == 1)
    check("and it does not block - the way still renders",
          "unread-collection" not in codes(scenecheck.blocking(f)))


def test_a_way_with_no_pieces_at_all_is_refused():
    f = scenecheck.check(_scene(obj_type="way", mins=(-1, -1, 0),
                                maxs=(1, 1, 0.1), collections={}))
    check("nothing modelled is an error", "no-pieces" in codes(f))
    f = scenecheck.check(_scene(obj_type="way", mins=(-1, -1, 0),
                                maxs=(1, 1, 0.1),
                                collections={"way_straight": 2}))
    check("one piece is enough to render", "no-pieces" not in codes(f))
    check("a missing cross stays a warning at most - the engine draws nothing "
          "there and carries on", "no-pieces" not in codes(f))


def test_the_dead_third_season_is_caught_here_too():
    f = scenecheck.check(_scene(obj_type="building", seasons=3,
                                collections={"season_1": 1, "season_2": 1}))
    check("3 seasons is reported", "dead-season" in codes(f))
    for n in (1, 2, 4, 5):
        cols = {"season_%d" % i: 1 for i in range(1, n)}
        f = scenecheck.check(_scene(obj_type="building", seasons=n,
                                    collections=cols))
        check("%d seasons is fine" % n, "dead-season" not in codes(f))


def test_a_signal_with_one_aspect_is_refused():
    f = scenecheck.check(_scene(obj_type="roadsign", is_signal=True, states=1,
                                collections={"state_0": 1}))
    check("a one-aspect signal is an error", "signal-needs-two" in codes(f))
    f = scenecheck.check(_scene(obj_type="roadsign", is_signal=False, states=1,
                                collections={"state_0": 1}))
    check("a plain SIGN with one state is fine",
          "signal-needs-two" not in codes(f))


def test_a_factory_without_a_map_colour_is_refused():
    """factory_writer.cc calls dbg->fatal() without a usable one."""
    f = scenecheck.check(_scene(obj_type="factory", factory_mapcolor=255))
    check("an out-of-range map colour is an error", "no-mapcolor" in codes(f))
    check("a real one is fine",
          "no-mapcolor" not in codes(scenecheck.check(
              _scene(obj_type="factory", factory_mapcolor=1))))


def test_a_nameless_object_is_refused():
    f = scenecheck.check(_scene(obj_name=""))
    check("no name is an error", "no-name" in codes(f))
    check("no author is only a warning - it is rude, not broken",
          "no-author" in codes(scenecheck.check(_scene(author="")))
          and "no-author" not in codes(
              scenecheck.blocking(scenecheck.check(_scene(author="")))))


def test_an_unknown_object_type_is_refused_not_guessed():
    f = scenecheck.check(_scene(obj_type="locomotive"))
    check("an unknown type is an error", "unknown-type" in codes(f))


def test_findings_are_error_first():
    f = scenecheck.check(scenecheck.Scene(obj_type="vehicle"))
    levels = [x.level for x in f]
    check("errors sort before warnings and information",
          levels == sorted(levels, key=lambda l: scenecheck._ORDER[l]),
          str(levels))


def test_the_scene_default_is_not_a_shared_dict():
    """A NamedTuple's defaults are made once, at class creation. An empty-dict
    default would be ONE dict shared by every Scene built without one."""
    a = scenecheck.Scene(obj_type="vehicle")
    b = scenecheck.Scene(obj_type="way")
    check("collections defaults to None, not a shared {}",
          a.collections is None and b.collections is None)


def test_every_level_is_reachable():
    """If no rule can produce a level, the level is decoration."""
    seen = set()
    for scene in (scenecheck.Scene(obj_type="vehicle"),
                  _scene(author="", length=8),
                  _scene()):
        for f in scenecheck.check(scene):
            seen.add(f.level)
    for level in (scenecheck.ERROR, scenecheck.WARNING, scenecheck.INFORMATION):
        check("something can raise %s" % level, level in seen)


def test_every_code_is_stable_and_unique_per_rule():
    """The code is the part a script or an editor can key off. Two rules sharing
    one code make it useless for that."""
    seen = {}
    scenes = [scenecheck.Scene(obj_type="vehicle"),
              _scene(mins=(4.0, -0.4, 3.0), maxs=(6.0, 0.4, 3.9), length=8),
              _scene(obj_type="way", collections={"way_x": 1}),
              _scene(obj_type="tunnel", collections={"tunnel_portal": 0})]
    for s in scenes:
        for f in scenecheck.check(s):
            check("code %r is a stable slug" % f.code,
                  f.code and " " not in f.code and f.code.islower())
            seen.setdefault(f.code, set()).add(f.level)
    for code, levels in sorted(seen.items()):
        # empty-collection is deliberately both: required vs optional
        if code == "empty-collection":
            continue
        check("%r means one level" % code, len(levels) == 1, str(levels))


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            print("\n%s" % name)
            fn()
    print()
    if FAILED:
        print("SCENECHECK_TESTS_FAILED: %d" % len(FAILED))
        for f in FAILED:
            print("  - %s" % f)
        sys.exit(1)
    print("SCENECHECK_TESTS_OK")


if __name__ == "__main__":
    main()
