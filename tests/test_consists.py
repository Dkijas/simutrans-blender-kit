"""Consists and the one persisted document, without Blender.

    python tests/test_consists.py

The load-bearing test is test_it_reproduces_the_shipped_civia. Everything else
guards bookkeeping; that one guards the CLAIM - that the generated constraints are
the ones a real, working, five-car pak128 unit already ships. If the generator
ever stops agreeing with art the game demonstrably runs, it is the generator that
is wrong.

Every rule is tested with a case that trips it and one that must not.
"""

import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core import consists as K, datgen, document, schema, variants  # noqa: E402

FAILED = []


def check(name, cond, detail=""):
    if cond:
        print("  ok   %s" % name)
    else:
        print("  FAIL %s  %s" % (name, detail))
        FAILED.append(name)


def codes(findings):
    return [f.code for f in findings]


def _civia():
    """The shipped five-car unit, said declaratively."""
    cs = K.ConsistSet()
    cs, c = K.add(cs, "Civia_465")
    for v, pl in (("CiviaS465_CabA", K.HEAD_ONLY),
                  ("CiviaS465_Int1", K.ANYWHERE),
                  ("CiviaS465_Panto", K.ANYWHERE),
                  ("CiviaS465_Int3", K.ANYWHERE),
                  ("CiviaS465_CabB", K.TAIL_ONLY)):
        cs, _m = K.add_member(cs, c.key, v, placement=pl)
    return cs, c


def _metro():
    """A 4-car and a 6-car sharing three vehicles - the union."""
    cs = K.ConsistSet()
    cs, c4 = K.add(cs, "Metro_4car")
    for v, pl in (("M_CabA", K.HEAD_ONLY), ("M_Mot", K.ANYWHERE),
                  ("M_Trl", K.ANYWHERE), ("M_CabB", K.TAIL_ONLY)):
        cs, _ = K.add_member(cs, c4.key, v, placement=pl)
    cs, c6 = K.add(cs, "Metro_6car", recommended=True)
    for v, pl in (("M_CabA", K.HEAD_ONLY), ("M_Trl", K.ANYWHERE),
                  ("M_Mot", K.ANYWHERE), ("M_Mot", K.ANYWHERE),
                  ("M_Trl", K.ANYWHERE), ("M_CabB", K.TAIL_ONLY)):
        cs, _ = K.add_member(cs, c6.key, v, placement=pl)
    return cs, c4, c6


# --- the claim ---------------------------------------------------------------

def test_it_reproduces_the_shipped_civia():
    """assets/civia_465 is a real unit that really runs in a real pak128 game -
    tests/scenarios has it assembling and moving. Its .dat constraints are
    therefore ground truth, and the generator has to land on them."""
    cs, _c = _civia()
    gen = K.constraints(cs)

    check("the cab leads, and nothing may precede it",
          gen["CiviaS465_CabA"][0] == ("none",), str(gen["CiviaS465_CabA"]))
    check("and Int1 follows it - the shipped Constraint[Next][0]",
          gen["CiviaS465_CabA"][1] == ("CiviaS465_Int1",))
    check("the tail cab ends it",
          gen["CiviaS465_CabB"][1] == ("none",), str(gen["CiviaS465_CabB"]))
    check("and Int3 precedes it",
          gen["CiviaS465_CabB"][0] == ("CiviaS465_Int3",))
    check("the middle cars are chained, in order",
          gen["CiviaS465_Int1"] == (("CiviaS465_CabA",), ("CiviaS465_Panto",)))
    check("no middle car is allowed to lead",
          "none" not in gen["CiviaS465_Panto"][0])
    check("every car got constraints", len(gen) == 5)


def test_the_generated_dat_lints_clean_against_the_engine_schema():
    """The generator's output has to survive the linter that reads the engine's
    own writers - which is what catches a Constraint the writer never reads."""
    cs, _c = _civia()
    gen = K.constraints(cs)
    images = datgen.image_block("civia465_cab_a",
                               {c: (0, i) for i, c in enumerate("s w sw se n e ne nw".split())})
    for veh, (p, n) in gen.items():
        text = datgen.vehicle_dat(name=veh, images=images, waytype="track",
                                  author="tests", constraint_prev=p,
                                  constraint_next=n)
        findings = schema.lint(text)
        check("%s: the generated .dat lints clean" % veh, not findings,
              str(findings))
        for i, x in enumerate(p):
            check("%s: Constraint[Prev][%d]=%s is in the .dat" % (veh, i, x),
                  "Constraint[Prev][%d]=%s" % (i, x) in text)


def test_datgen_is_the_only_place_a_constraint_is_written():
    """The canonical-source rule: consists.py must not FORMAT a .dat line, it
    computes the tuples datgen already took.

    The first version of this test grepped the whole file for "Constraint[" and
    failed - on the module's own docstring, which explains the union in prose.
    That is the same mistake phase 1's prefix test made: searching the source for
    a word when the claim is about the CODE. Documentation naming a thing is not
    an implementation of it, so the strings are read out of the AST, where a
    docstring is identifiable and a comment does not exist at all.
    """
    import ast
    path = os.path.join(_ROOT, "core", "consists.py")
    with open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read())

    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            d = ast.get_docstring(node, clean=False)
            if d is not None:
                docstrings.add(d)

    offenders = [n.value for n in ast.walk(tree)
                 if isinstance(n, ast.Constant) and isinstance(n.value, str)
                 and n.value not in docstrings and "Constraint[" in n.value]
    check("core/consists.py formats no Constraint[ line", offenders == [],
          "string literals that emit one: %s" % (offenders,))

    src = open(path, encoding="utf-8").read()
    check("and it does not import datgen - the flow is one-way",
          "import datgen" not in src)
    dat = open(os.path.join(_ROOT, "core", "datgen.py"), encoding="utf-8").read()
    check("datgen still is the place that writes it",
          'Constraint[%s][%d]=%s' in dat)


# --- the union ---------------------------------------------------------------

def test_a_vehicle_in_two_formations_gets_both_sets_of_neighbours():
    """The whole reason a manager beats a formatter. Miss one and the game simply
    refuses to let the player build that train, with no message."""
    cs, _c4, _c6 = _metro()
    gen = K.constraints(cs)

    check("the motor car may follow the cab (4-car)",
          "M_CabA" in gen["M_Mot"][0], str(gen["M_Mot"][0]))
    check("and the trailer (6-car)", "M_Trl" in gen["M_Mot"][0])
    check("and itself - two motors are adjacent in the 6-car",
          "M_Mot" in gen["M_Mot"][0])
    check("the cab may be followed by either",
          set(gen["M_CabA"][1]) == {"M_Mot", "M_Trl"}, str(gen["M_CabA"][1]))
    check("only the cabs may lead", gen["M_CabA"][0] == ("none",)
          and "none" not in gen["M_Mot"][0])


def test_only_the_named_consist_when_asked():
    cs, c4, _c6 = _metro()
    only4 = K.constraints(cs, only={c4.key})
    check("restricted to the 4-car, the motor follows only the cab",
          only4["M_Mot"][0] == ("M_CabA",), str(only4["M_Mot"][0]))
    check("and the union still has both",
          set(K.constraints(cs)["M_Mot"][0]) > set(only4["M_Mot"][0]))


# --- placements --------------------------------------------------------------

def test_middle_only_is_any_on_both_sides():
    """The non-obvious one. `any` does not mean "anything at all" - it means "any
    REAL vehicle", and real excludes the head, because the head's prev_veh is NULL
    and can_follow guards on prev_veh!=NULL."""
    cs = K.ConsistSet()
    cs, c = K.add(cs, "T")
    cs, _ = K.add_member(cs, c.key, "Cab", placement=K.HEAD_ONLY)
    cs, _ = K.add_member(cs, c.key, "Mid", placement=K.MIDDLE_ONLY)
    cs, _ = K.add_member(cs, c.key, "CabB", placement=K.TAIL_ONLY)
    gen = K.constraints(cs)
    check("a middle-only car may never lead", "any" in gen["Mid"][0], str(gen["Mid"]))
    check("nor end", "any" in gen["Mid"][1])
    check("and it is NOT told it may lead", "none" not in gen["Mid"][0])
    check("the head-only car is", gen["Cab"][0][0] == "none")


def test_head_and_tail_only():
    cs = K.ConsistSet()
    cs, c = K.add(cs, "T")
    cs, _ = K.add_member(cs, c.key, "A", placement=K.HEAD_ONLY)
    cs, _ = K.add_member(cs, c.key, "B", placement=K.TAIL_ONLY)
    gen = K.constraints(cs)
    check("head-only gets none in Prev", "none" in gen["A"][0])
    check("and not in Next", "none" not in gen["A"][1])
    check("tail-only gets none in Next", "none" in gen["B"][1])
    check("and not in Prev", "none" not in gen["B"][0])


def test_a_repeatable_member_may_follow_itself():
    """Forget this and a "3 to 6 middle cars" section builds exactly one car,
    because the second may not couple to the first."""
    cs = K.ConsistSet()
    cs, c = K.add(cs, "Rake")
    cs, _ = K.add_member(cs, c.key, "Loco", placement=K.HEAD_ONLY)
    cs, _ = K.add_member(cs, c.key, "Coach", min_count=1, max_count=6)
    gen = K.constraints(cs)
    check("the coach may follow a coach", "Coach" in gen["Coach"][0])
    check("and be followed by one", "Coach" in gen["Coach"][1])
    check("a non-repeatable car may not follow itself",
          "Loco" not in gen["Loco"][0])


def test_an_optional_member_opens_a_shortcut_past_itself():
    cs = K.ConsistSet()
    cs, c = K.add(cs, "T")
    cs, _ = K.add_member(cs, c.key, "A", placement=K.HEAD_ONLY)
    cs, _ = K.add_member(cs, c.key, "Opt", min_count=0, max_count=1)
    cs, _ = K.add_member(cs, c.key, "B", placement=K.TAIL_ONLY)
    gen = K.constraints(cs)
    check("A may be followed by the optional car", "Opt" in gen["A"][1])
    check("and, if it is left out, by B directly", "B" in gen["A"][1],
          str(gen["A"][1]))
    check("B may follow either", set(gen["B"][0]) == {"A", "Opt"},
          str(gen["B"][0]))


def test_a_reversible_train_permits_the_mirror():
    cs = K.ConsistSet()
    cs, c = K.add(cs, "Tram", reversible=True)
    cs, _ = K.add_member(cs, c.key, "A")
    cs, _ = K.add_member(cs, c.key, "B")
    gen = K.constraints(cs)
    check("A may precede B", "B" in gen["A"][1])
    check("and B may precede A - the mirror", "A" in gen["B"][1], str(gen["B"]))
    check("both may lead", "none" in gen["A"][0] and "none" in gen["B"][0])

    cs2 = K.ConsistSet()
    cs2, c2 = K.add(cs2, "OneWay", reversible=False)
    cs2, _ = K.add_member(cs2, c2.key, "A")
    cs2, _ = K.add_member(cs2, c2.key, "B")
    g2 = K.constraints(cs2)
    check("a one-way train does NOT permit the mirror", "A" not in g2["B"][1],
          str(g2["B"]))


# --- editing -----------------------------------------------------------------

def test_create_duplicate_rename_delete():
    cs = K.ConsistSet()
    cs, a = K.add(cs, "Four")
    cs, b = K.add(cs, "Six")
    check("two consists", len(cs.consists) == 2)
    check("distinct keys", a.key != b.key)

    cs, _m = K.add_member(cs, a.key, "Car1")
    cs, dup = K.duplicate(cs, a.key)
    check("a duplicate gets a new key", dup.key not in (a.key, b.key))
    check("and a new name", dup.name != "Four", dup.name)
    check("and FRESH member keys - shared ones would make 'move car 3' ambiguous",
          dup.members[0].key != K.get(cs, a.key).members[0].key)
    check("a duplicate is not automatically recommended", not dup.recommended)

    cs = K.rename(cs, a.key, "Four_car")
    check("rename changes the name", K.get(cs, a.key).name == "Four_car")
    check("and not the key", K.get(cs, a.key).key == a.key)

    cs = K.remove(cs, b.key)
    check("remove takes it out", K.get(cs, b.key) is None)
    check("and leaves the rest", K.get(cs, a.key) is not None)


def test_a_key_is_never_reused_even_across_a_save():
    """core/variants.py shipped this bug and a test caught it. This module was
    written knowing, so the test exists to keep it that way.

    DELETING THE HIGHEST KEY IS THE CASE THAT MATTERS, and the first version of
    this test missed it. It deleted the LOWEST and passed even with the counter
    broken to `highest_used + 1` - because with the lowest gone, the highest is
    still there and the next number is still safe. The bug only bites when the
    top key goes. Caught by breaking consists.py on purpose and watching this
    stay green: the test had been copied from the variants one, which was chasing
    a different bug (scan for the first free number), so its shape was right and
    its coverage was not.
    """
    cs = K.ConsistSet()
    cs, a = K.add(cs, "A")
    cs, b = K.add(cs, "B")

    # delete the LOWEST
    cs = K.remove(cs, a.key)
    cs, c = K.add(cs, "C")
    check("a dead low key is not reissued", c.key != a.key,
          "%s vs %s" % (c.key, a.key))

    # delete the HIGHEST - the one a naive counter reissues
    cs = K.remove(cs, c.key)
    cs, d = K.add(cs, "D")
    check("a dead HIGH key is not reissued either", d.key != c.key,
          "%s vs %s" % (d.key, c.key))
    check("nor any other dead one", d.key != a.key)

    # and again, so a counter that merely skipped one is caught too
    cs = K.remove(cs, d.key)
    cs = K.remove(cs, b.key)
    cs, e = K.add(cs, "E")
    check("emptying the set does not rewind the counter",
          e.key not in (a.key, b.key, c.key, d.key),
          "%s in %s" % (e.key, (a.key, b.key, c.key, d.key)))

    doc = document.Document(consists=cs)
    back = document.load(document.dump(doc)).consists
    back, f = K.add(back, "F")
    check("nor after a save and reload",
          f.key not in (a.key, b.key, c.key, d.key, e.key))

    # the member keys share the counter, so they must be safe from the same thing
    back, g = K.add(back, "G")
    back, m1 = K.add_member(back, g.key, "V1")
    back = K.remove_member(back, g.key, m1.key)
    back, m2 = K.add_member(back, g.key, "V2")
    check("a dead MEMBER key is not reissued", m2.key != m1.key,
          "%s vs %s" % (m2.key, m1.key))


def test_members_and_consists_share_one_counter():
    """A member key and a consist key must not collide - they live in the same
    document and a lookup that found the wrong one would be silent."""
    cs = K.ConsistSet()
    cs, c = K.add(cs, "T")
    cs, m1 = K.add_member(cs, c.key, "A")
    cs, m2 = K.add_member(cs, c.key, "B")
    keys = [c.key, m1.key, m2.key]
    check("every key is distinct", len(set(keys)) == 3, str(keys))


def test_add_remove_and_move_members():
    cs = K.ConsistSet()
    cs, c = K.add(cs, "T")
    for v in ("A", "B", "C"):
        cs, _ = K.add_member(cs, c.key, v)
    check("three in order",
          [m.vehicle for m in K.get(cs, c.key).members] == ["A", "B", "C"])

    cs = K.move_member(cs, c.key, K.get(cs, c.key).members[2].key, -1)
    check("moving C up",
          [m.vehicle for m in K.get(cs, c.key).members] == ["A", "C", "B"])
    cs = K.move_member(cs, c.key, K.get(cs, c.key).members[0].key, -1)
    check("moving past the front is clamped, not wrapped",
          [m.vehicle for m in K.get(cs, c.key).members] == ["A", "C", "B"])

    cs = K.remove_member(cs, c.key, K.get(cs, c.key).members[1].key)
    check("removing the middle",
          [m.vehicle for m in K.get(cs, c.key).members] == ["A", "B"])

    cs, at = K.add_member(cs, c.key, "Z", at=0)
    check("inserting at a position",
          [m.vehicle for m in K.get(cs, c.key).members] == ["Z", "A", "B"])


def test_editing_something_that_is_not_there_is_not_a_crash():
    cs = K.ConsistSet()
    cs, c = K.add(cs, "T")
    check("add_member to an unknown consist returns None",
          K.add_member(cs, "c0000dead", "X")[1] is None)
    check("duplicate of an unknown key returns None",
          K.duplicate(cs, "c0000dead")[1] is None)
    check("remove of an unknown key is a no-op",
          len(K.remove(cs, "c0000dead").consists) == 1)
    check("move in an unknown consist is a no-op",
          K.move_member(cs, "c0000dead", "x", 1) is not None)


# --- articulation ------------------------------------------------------------

def test_articulated_pairs_must_agree():
    cs = K.ConsistSet()
    cs, c = K.add(cs, "Tram")
    cs, a = K.add_member(cs, c.key, "A")
    cs, b = K.add_member(cs, c.key, "B")
    cs = K.ConsistSet(consists=(K.get(cs, c.key)._replace(members=(
        a._replace(articulated=b.key), b._replace(articulated=a.key))),),
        next_key=cs.next_key)
    check("a properly welded pair is fine",
          "one-sided-articulation" not in codes(K.check(cs)))

    one_sided = K.ConsistSet(consists=(K.get(cs, c.key)._replace(members=(
        a._replace(articulated=b.key), b)),), next_key=cs.next_key)
    check("one-way welding is an error - it ships an 'inseparable' pair separable",
          "one-sided-articulation" in codes(K.check(one_sided)))

    broken = K.ConsistSet(consists=(K.get(cs, c.key)._replace(members=(
        a._replace(articulated="c0000dead"), b._replace(articulated="c0000dead")),),),
        next_key=cs.next_key)
    check("welding to a position that does not exist is an error",
          "broken-articulation" in codes(K.check(broken)))


def test_removing_a_member_unwelds_its_partner():
    cs = K.ConsistSet()
    cs, c = K.add(cs, "T")
    cs, a = K.add_member(cs, c.key, "A")
    cs, b = K.add_member(cs, c.key, "B")
    cs = _replace_members(cs, c.key, (a._replace(articulated=b.key),
                                      b._replace(articulated=a.key)))
    cs = K.remove_member(cs, c.key, b.key)
    left = K.get(cs, c.key).members[0]
    check("the survivor is not left welded to a ghost", left.articulated == "",
          left.articulated)


def _replace_members(cs, key, members):
    return cs._replace(consists=tuple(
        c._replace(members=members) if c.key == key else c for c in cs.consists))


# --- validation --------------------------------------------------------------

def test_a_good_set_says_nothing_alarming():
    cs, _c4, _c6 = _metro()
    known = {"M_CabA", "M_CabB", "M_Mot", "M_Trl"}
    f = K.check(cs, known=known, exportable=known)
    check("no error", K.blocking(f) == (), str(codes(f)))
    check("no warning either",
          [x for x in f if x.level == K.WARNING] == [], str(codes(f)))


def test_an_impossible_formation_is_refused():
    cs = K.ConsistSet()
    cs, c = K.add(cs, "Nope")
    cs, _ = K.add_member(cs, c.key, "Mid", placement=K.MIDDLE_ONLY)
    f = K.check(cs)
    check("one middle-only vehicle cannot exist", "impossible" in codes(f))
    check("and it blocks", "impossible" in codes(K.blocking(f)))


def test_a_train_nothing_may_lead_is_refused():
    cs = K.ConsistSet()
    cs, c = K.add(cs, "Headless")
    cs, _ = K.add_member(cs, c.key, "A", placement=K.MIDDLE_ONLY)
    cs, _ = K.add_member(cs, c.key, "B", placement=K.TAIL_ONLY)
    f = K.check(cs)
    check("nothing may lead it - the game can never build it",
          "no-head" in codes(f))
    cs2 = K.ConsistSet()
    cs2, c2 = K.add(cs2, "Tailless")
    cs2, _ = K.add_member(cs2, c2.key, "A", placement=K.HEAD_ONLY)
    cs2, _ = K.add_member(cs2, c2.key, "B", placement=K.MIDDLE_ONLY)
    check("nor end it", "no-tail" in codes(K.check(cs2)))


def test_a_contradictory_vehicle_is_refused():
    """Head-only in one formation and middle-only in another. It is ONE object
    with ONE .dat; it cannot be both."""
    cs = K.ConsistSet()
    cs, a = K.add(cs, "A")
    cs, _ = K.add_member(cs, a.key, "X", placement=K.HEAD_ONLY)
    cs, _ = K.add_member(cs, a.key, "Y", placement=K.TAIL_ONLY)
    cs, b = K.add(cs, "B")
    cs, _ = K.add_member(cs, b.key, "W", placement=K.HEAD_ONLY)
    cs, _ = K.add_member(cs, b.key, "X", placement=K.MIDDLE_ONLY)
    cs, _ = K.add_member(cs, b.key, "Z", placement=K.TAIL_ONLY)
    f = K.check(cs)
    check("a vehicle that must and must not lead is an error",
          "contradictory" in codes(f), str(codes(f)))


def test_broken_references_are_caught():
    cs, _c = _civia()
    f = K.check(cs, known={"CiviaS465_CabA"})
    check("a vehicle that does not exist is an error",
          "unknown-vehicle" in codes(f))
    check("and it blocks", "unknown-vehicle" in codes(K.blocking(f)))
    check("all present, no complaint",
          "unknown-vehicle" not in codes(K.check(cs, known={
              "CiviaS465_CabA", "CiviaS465_CabB", "CiviaS465_Int1",
              "CiviaS465_Int3", "CiviaS465_Panto"})))


def test_a_vehicle_nothing_renders_is_a_warning_not_an_error():
    cs, _c = _civia()
    known = {"CiviaS465_CabA", "CiviaS465_CabB", "CiviaS465_Int1",
             "CiviaS465_Int3", "CiviaS465_Panto"}
    f = K.check(cs, known=known, exportable=known - {"CiviaS465_Panto"})
    check("it is reported", "not-exportable" in codes(f))
    check("but does not block - the artist may render it elsewhere",
          "not-exportable" not in codes(K.blocking(f)))


def test_a_reserved_word_as_a_vehicle_name_is_refused():
    for bad in ("none", "any"):
        cs = K.ConsistSet()
        cs, c = K.add(cs, "T")
        cs, _ = K.add_member(cs, c.key, bad)
        check("a vehicle called %r is an error" % bad,
              "reserved-name" in codes(K.check(cs)))


def test_a_name_the_writers_cannot_carry_is_refused():
    for bad in ("has space", "hash#es", ""):
        cs = K.ConsistSet()
        cs, c = K.add(cs, "T")
        cs, _ = K.add_member(cs, c.key, bad)
        f = codes(K.check(cs))
        check("%r is refused" % bad, "bad-name" in f or "no-vehicle" in f, str(f))
    cs = K.ConsistSet()
    cs, c = K.add(cs, "T")
    cs, _ = K.add_member(cs, c.key, "RENFE_269-1")
    check("a real name is fine", "bad-name" not in codes(K.check(cs)))


def test_bad_counts_are_refused():
    cs = K.ConsistSet()
    cs, c = K.add(cs, "T")
    cs, _ = K.add_member(cs, c.key, "A", min_count=3, max_count=1)
    check("a minimum above the maximum is an error", "bad-count" in codes(K.check(cs)))
    cs2 = K.ConsistSet()
    cs2, c2 = K.add(cs2, "T")
    cs2, _ = K.add_member(cs2, c2.key, "A", min_count=1, max_count=0)
    check("a maximum below one is an error", "bad-count" in codes(K.check(cs2)))


def test_an_empty_consist_is_a_warning():
    cs = K.ConsistSet()
    cs, _c = K.add(cs, "Empty")
    f = K.check(cs)
    check("it is reported", "empty-consist" in codes(f))
    check("but not refused - it is a train being written",
          "empty-consist" not in codes(K.blocking(f)))


def test_duplicate_names_and_keys_are_refused():
    cs = K.ConsistSet()
    cs, _a = K.add(cs, "Same")
    cs, _b = K.add(cs, "Same")
    check("two consists with one name", "duplicate-name" in codes(K.check(cs)))
    c = K.Consist(key="c00000000", name="X")
    check("two consists with one key",
          "duplicate-key" in codes(K.check(K.ConsistSet(consists=(c, c._replace(name="Y"))))))


def test_self_coupling_is_information_not_a_warning():
    """A rake of identical carriages is exactly this. It is normal."""
    cs = K.ConsistSet()
    cs, c = K.add(cs, "Rake")
    cs, _ = K.add_member(cs, c.key, "Loco", placement=K.HEAD_ONLY)
    cs, _ = K.add_member(cs, c.key, "Coach", max_count=8)
    f = K.check(cs)
    check("it is mentioned", "self-coupling" in codes(f))
    check("as INFORMATION",
          all(x.level == K.INFORMATION for x in f if x.code == "self-coupling"))


# --- the diff ----------------------------------------------------------------

def test_the_diff_says_what_would_change_before_anything_is_written():
    cs, _c = _civia()
    current = {"CiviaS465_CabA": (("none",), ("WRONG",)),
               "CiviaS465_Int1": ((), ())}
    d = K.diff(cs, current)
    added, removed, kept = d["CiviaS465_CabA"]
    check("it keeps what was already right", ("prev", "none") in kept)
    check("it adds what is missing", ("next", "CiviaS465_Int1") in added)
    check("it removes what is wrong", ("next", "WRONG") in removed)
    added, _r, _k = d["CiviaS465_Int1"]
    check("a vehicle with no constraints gets them all as additions",
          len(added) == 2, str(added))


def test_the_diff_covers_vehicles_that_would_lose_their_constraints():
    cs, _c = _civia()
    current = {"Orphan": (("X",), ("Y",))}
    d = K.diff(cs, current)
    check("a vehicle no consist mentions is in the diff", "Orphan" in d)
    _a, removed, _k = d["Orphan"]
    check("with everything marked for removal", len(removed) == 2, str(removed))


# --- the summary -------------------------------------------------------------

def test_the_summary_adds_up_what_it_has():
    cs, c = _civia()
    veh = {m.vehicle: {"length": 8, "payload": 50, "power": 100, "weight": 30,
                       "cost": 1000, "runningcost": 10, "speed": 120,
                       "waytype": "track", "engine_type": "electric",
                       "intro_year": 2004}
           for m in K.get(cs, c.key).members}
    s = K.summary(K.get(cs, c.key), veh)
    check("five cars", s["cars"].value == 5)
    check("length totals", s["length"].value == 40)
    check("payload totals", s["payload"].value == 250)
    check("and it is marked COMPUTED", s["length"].kind == K.COMPUTED)
    check("the waytype is CONFIRMED, not computed",
          s["waytype"].kind == K.CONFIRMED and s["waytype"].value == "track")
    check("it is electric", s["electric"].value is True)


def test_the_summary_refuses_to_invent_a_total():
    """A weight that silently omits two cars is worse than no weight - it looks
    like an answer."""
    cs, c = _civia()
    veh = {"CiviaS465_CabA": {"length": 8, "weight": 34}}
    s = K.summary(K.get(cs, c.key), veh)
    check("with four cars unknown, the weight is UNAVAILABLE",
          s["weight"].kind == K.UNAVAILABLE and s["weight"].value is None)
    check("and it names what is missing", "_missing" in s)
    check("the car count is still computable", s["cars"].value == 5)


def test_the_slowest_car_limits_the_train():
    cs = K.ConsistSet()
    cs, c = K.add(cs, "T")
    cs, _ = K.add_member(cs, c.key, "Fast", placement=K.HEAD_ONLY)
    cs, _ = K.add_member(cs, c.key, "Slow", placement=K.TAIL_ONLY)
    base = {"length": 8, "payload": 0, "power": 0, "weight": 10, "cost": 1,
            "runningcost": 1, "waytype": "track", "engine_type": "diesel",
            "intro_year": 1950}
    s = K.summary(K.get(cs, c.key),
                  {"Fast": dict(base, speed=160), "Slow": dict(base, speed=80)})
    check("the train's speed is the slowest car's", s["speed"].value == 80)
    check("and it says why", "slowest" in s["speed"].note)


def test_a_train_whose_cars_disagree_about_the_waytype():
    cs = K.ConsistSet()
    cs, c = K.add(cs, "T")
    cs, _ = K.add_member(cs, c.key, "Rail", placement=K.HEAD_ONLY)
    cs, _ = K.add_member(cs, c.key, "Road", placement=K.TAIL_ONLY)
    base = {"length": 8, "payload": 0, "power": 0, "weight": 10, "cost": 1,
            "runningcost": 1, "speed": 100, "engine_type": "diesel",
            "intro_year": 1950}
    s = K.summary(K.get(cs, c.key), {"Rail": dict(base, waytype="track"),
                                     "Road": dict(base, waytype="road")})
    check("the waytype is UNAVAILABLE, not a guess",
          s["waytype"].kind == K.UNAVAILABLE)
    check("and it says why", "disagree" in s["waytype"].note)


# --- the document ------------------------------------------------------------

def test_one_document_holds_variants_and_consists():
    doc = document.Document()
    doc.variants, _v = variants.add(doc.variants, "Green",
                                    materials={"Body": (0, 120, 0)})
    doc.consists, c = K.add(doc.consists, "Four")
    doc.consists, _m = K.add_member(doc.consists, c.key, "CabA",
                                    placement=K.HEAD_ONLY)

    text = document.dump(doc)
    back = document.load(text)
    check("the variants survive", len(back.variants.variants) == 1)
    check("the consists survive", len(back.consists.consists) == 1)
    check("with their members", len(back.consists.consists[0].members) == 1)
    check("and their placements",
          back.consists.consists[0].members[0].placement == K.HEAD_ONLY)
    check("the round trip is stable", document.dump(back) == text)
    check("the version is stamped", '"schema_version": 2' in text)


def test_a_phase_2_document_migrates():
    """A real v1 document - the shape 0.9.0 actually saved into .blend files, with
    the variant fields at the TOP LEVEL. Written here as a literal, not produced by
    this module, because that is what makes it a migration test."""
    v1 = json.dumps({
        "schema_version": 1,
        "obj_type": "vehicle",
        "next_key": 2,
        "axes": {"freight": 2},
        "variants": [
            {"key": "v00000000", "name": "Green",
             "overrides": {"power": 500}, "materials": {"Body": [0, 120, 0]},
             "show": [], "hide": [], "note": ""},
            {"key": "v00000001", "name": "Red", "overrides": {},
             "materials": {}, "show": [], "hide": [], "note": ""},
        ],
    })
    doc = document.load(v1)
    check("a phase-2 document loads", len(doc.variants.variants) == 2)
    check("the variants keep their keys", doc.variants.variants[0].key == "v00000000")
    check("and their overrides",
          doc.variants.variants[0].overrides == {"power": 500})
    check("and their materials",
          doc.variants.variants[0].materials == {"Body": (0, 120, 0)})
    check("the axes survive", doc.variants.axes == {"freight": 2})
    check("the counter survives - or a dead key comes back",
          doc.variants.next_key >= 2)
    check("it gains an empty consist set", doc.consists.consists == ())
    check("and is written back at the current version",
          '"schema_version": 2' in document.dump(doc))


def test_a_versionless_document_migrates():
    doc = document.load('{"variants": [{"key": "v00000000", "name": "Old"}]}')
    check("a v0 document loads", len(doc.variants.variants) == 1)
    check("and keeps its variant", doc.variants.variants[0].name == "Old")


def test_a_document_from_the_future_is_not_reinterpreted():
    """The one that protects somebody's work. Guessing at a newer format is how an
    old kit eats a project made with a newer one."""
    future = json.dumps({"schema_version": 99, "variants": {"variants": []},
                         "something_new": {"we": "cannot read this"}})
    doc = document.load(future)
    check("it is marked as from the future", doc.from_the_future)
    check("check() reports it", "future-document" in codes(document.check(doc)))
    check("and it BLOCKS", "future-document" in codes(document.blocking(
        document.check(doc))))
    check("dumping it gives back exactly what came in, not a truncation",
          json.loads(document.dump(doc)) == json.loads(future))
    check("a current document is not from the future",
          not document.load(document.dump(document.Document())).from_the_future)


def test_an_unknown_section_survives_a_round_trip():
    """An old kit that drops a new kit's data is an old kit that destroys files."""
    doc = document.load(json.dumps({
        "schema_version": 2, "variants": {"variants": []}, "consists": {},
        "a_future_section": {"keep": "me"}}))
    check("the unknown section is kept", doc.unknown.get("a_future_section")
          == {"keep": "me"})
    check("and written back", "a_future_section" in document.dump(doc))


def test_a_broken_document_loses_nothing_it_had():
    for text in ("", "   ", "not json", "[]", "null", "42",
                 '{"consists": 3}', '{"consists": {"consists": "no"}}',
                 '{"schema_version": true}', '{"schema_version": -1}',
                 '{"consists": {"consists": [1, "x", null]}}',
                 '{"consists": {"consists": [{"members": 7}]}}'):
        try:
            doc = document.load(text)
            ok = isinstance(doc, document.Document)
            why = ""
        except Exception as e:                                   # noqa: BLE001
            ok, why = False, "raised %s: %s" % (type(e).__name__, e)
        check("%r loads" % (text[:26],), ok, why)


def test_a_hand_edited_counter_cannot_reissue_a_live_key():
    doc = document.load(json.dumps({
        "schema_version": 2,
        "consists": {"next_key": 0,
                     "consists": [{"key": "c00000009", "name": "Live",
                                   "members": []}]}}))
    cs, fresh = K.new_key(doc.consists)
    check("the counter is lifted above every live key",
          int(fresh[1:], 16) > 9, fresh)


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            print("\n%s" % name)
            fn()
    print()
    if FAILED:
        print("CONSIST_TESTS_FAILED: %d" % len(FAILED))
        for f in FAILED:
            print("  - %s" % f)
        sys.exit(1)
    print("CONSIST_TESTS_OK")


if __name__ == "__main__":
    main()
