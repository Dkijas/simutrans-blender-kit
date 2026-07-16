"""Say the train once; let the constraints fall out.

Read docs/constraints-in-simutrans.md first. The short version:

  * `can_follow(prev_veh)` returns true when prev_veh is NULL and the vehicle
    lists `none` - NULL is "nothing in front of me", i.e. the head.
  * `none` writes a NULL child; `any` is a real sentinel object. So `none` means
    ONLY AT THE HEAD and `any` means NEVER AT THE HEAD. They are opposites, and
    `any` is how you say "middle only".
  * No constraint at all means "couples to anything, anywhere".

THE CANONICAL SOURCE IS datgen
    core/datgen.py's vehicle_dat(constraint_prev=(), constraint_next=()) is what
    the .dat carries and therefore what the engine reads. This module GENERATES
    those two tuples and nothing else. It is not a second representation of
    coupling to be kept in step with the first - it computes the argument datgen
    already took before this phase existed. One place writes a constraint.

WHY A UNION
    A vehicle in two formations must accept every neighbour either one gives it.
    A metro motor car that sits behind a cab in the 4-car set and behind a trailer
    in the 6-car set needs BOTH in its Constraint[Prev]. Miss one and the game does
    not complain - it just refuses to let the player build that train in the depot,
    with no message saying why.

    That union, across formations, per vehicle, is the bookkeeping this module
    exists to do. Everything else here is in service of getting it right.

WHAT IS DELIBERATELY NOT MODELLED
    A "formation" is not an engine object. The engine has vehicles and pairwise
    coupling rules, and a convoy is whatever a player builds that satisfies them.
    So a consist here is an ARTIST'S STATEMENT of a train they intend, and its only
    output is constraints. It cannot promise the player will build exactly it -
    nothing in the engine can - and it does not pretend to.
"""

import re
from typing import NamedTuple

from . import scenecheck

# The two engine keywords. Not names - the writer and the pakset manager treat
# them specially, so a vehicle actually called "none" would be a catastrophe.
NONE = "none"
ANY = "any"
KEYWORDS = (NONE, ANY)

Finding = scenecheck.Finding
ERROR = scenecheck.ERROR
WARNING = scenecheck.WARNING
INFORMATION = scenecheck.INFORMATION
blocking = scenecheck.blocking

# Where a member may sit. Descriptive, and it drives the ends of the generated
# constraints - see docs/constraints-in-simutrans.md for the table.
ANYWHERE = "anywhere"      # no end constraint added
HEAD_ONLY = "head"         # Prev = none
TAIL_ONLY = "tail"         # Next = none
MIDDLE_ONLY = "middle"     # Prev = any, Next = any  <- the non-obvious one
PLACEMENTS = (ANYWHERE, HEAD_ONLY, TAIL_ONLY, MIDDLE_ONLY)

# makeobj matches names literally; '#' starts a comment at column 0 and a space
# ends an atoi(). Same rule as core/variants.py, and for the same reason.
_NAME_OK = re.compile(r"^[A-Za-z0-9_.\-+]+$")
_KEY_RE = re.compile(r"^c[0-9a-f]{8}$")


class Member(NamedTuple):
    """One position in a train.

    key          stable, never reused. Not the vehicle name - a member can be
                 repointed at a different vehicle and stay the same position.
    vehicle      the name= of the vehicle (or of a variant - a variant IS an
                 object, with its own name; see core/variants.py).
    min_count    how few of this member the formation may have. 0 = optional.
    max_count    how many. >1 makes it a repeatable section, and a repeatable
                 member may follow ITSELF - which is a constraint most people
                 forget to write.
    placement    ANYWHERE / HEAD_ONLY / TAIL_ONLY / MIDDLE_ONLY.
    articulated  the key of the member this one is welded to. An articulated pair
                 is inseparable: neither may appear without the other.
    """
    key: str
    vehicle: str
    min_count: int = 1
    max_count: int = 1
    placement: str = ANYWHERE
    articulated: str = ""
    note: str = ""

    @property
    def optional(self):
        return self.min_count == 0

    @property
    def repeatable(self):
        return self.max_count > 1


class Consist(NamedTuple):
    """A train the artist intends, front to back.

    reversible   the same set may run either way round. It does NOT mean the
                 engine reverses anything - it means the constraints must also
                 permit the mirrored order, so the union gains the reverse
                 neighbours.
    recommended  the artist's pick. Metadata; nothing computes with it.
    """
    key: str
    name: str
    members: tuple = ()
    reversible: bool = False
    recommended: bool = False
    note: str = ""


class ConsistSet(NamedTuple):
    """Every consist in one project, plus the counter that keeps keys unique.

    next_key is PERSISTED, exactly as in core/variants.py, and for exactly the
    same reason: deriving it from the live members reissues the key of a deleted
    consist, and then a reference held anywhere silently means a different train.
    core/variants.py shipped that bug and a test caught it; this module was
    written knowing.
    """
    consists: tuple = ()
    next_key: int = 0


def format_key(n):
    return "c%08x" % n


def _highest_used(consists):
    top = -1
    for c in consists or ():
        for k in (c.key,) + tuple(m.key for m in c.members):
            if k and _KEY_RE.match(k):
                try:
                    top = max(top, int(k[1:], 16))
                except ValueError:
                    pass
    return top


def new_key(cset):
    """The next key, and the set that has consumed it -> (ConsistSet, str)."""
    n = max(cset.next_key, _highest_used(cset.consists) + 1)
    return cset._replace(next_key=n + 1), format_key(n)


# --- editing -----------------------------------------------------------------

def add(cset, name, **kw):
    cset, key = new_key(cset)
    c = Consist(key=key, name=name, **kw)
    return cset._replace(consists=cset.consists + (c,)), c


def get(cset, key):
    for c in cset.consists:
        if c.key == key:
            return c
    return None


def rename(cset, key, name):
    return _replace_one(cset, key, lambda c: c._replace(name=name))


def remove(cset, key):
    return cset._replace(consists=tuple(c for c in cset.consists if c.key != key))


def duplicate(cset, key):
    """Copy a consist AND give every member a fresh key.

    Sharing member keys between two consists would make "move the third car of the
    6-car set" ambiguous - and the bug would look like the UI editing the wrong
    train.
    """
    src = get(cset, key)
    if src is None:
        return cset, None
    cset, fresh = new_key(cset)
    members, remap = [], {}
    for m in src.members:
        cset, mk = new_key(cset)
        remap[m.key] = mk
        members.append(m._replace(key=mk))
    # articulated pointers must follow their members into the copy
    members = [m._replace(articulated=remap.get(m.articulated, ""))
               if m.articulated else m for m in members]
    copy = src._replace(key=fresh, name=_unique_name(cset, src.name),
                        members=tuple(members), recommended=False)
    return cset._replace(consists=cset.consists + (copy,)), copy


def _unique_name(cset, base):
    taken = {c.name for c in cset.consists}
    if base not in taken:
        return base
    i = 2
    while "%s_%d" % (base, i) in taken:
        i += 1
    return "%s_%d" % (base, i)


def add_member(cset, consist_key, vehicle, at=None, **kw):
    """Put a vehicle in a train -> (ConsistSet, Member)."""
    c = get(cset, consist_key)
    if c is None:
        return cset, None
    cset, key = new_key(cset)
    m = Member(key=key, vehicle=vehicle, **kw)
    members = list(c.members)
    members.insert(len(members) if at is None else at, m)
    return _replace_one(cset, consist_key,
                        lambda x: x._replace(members=tuple(members))), m


def remove_member(cset, consist_key, member_key):
    c = get(cset, consist_key)
    if c is None:
        return cset
    kept = tuple(m for m in c.members if m.key != member_key)
    # anything welded to the removed member is no longer welded to anything
    kept = tuple(m._replace(articulated="") if m.articulated == member_key else m
                 for m in kept)
    return _replace_one(cset, consist_key, lambda x: x._replace(members=kept))


def move_member(cset, consist_key, member_key, delta):
    c = get(cset, consist_key)
    if c is None:
        return cset
    members = list(c.members)
    idx = next((i for i, m in enumerate(members) if m.key == member_key), None)
    if idx is None:
        return cset
    new = max(0, min(len(members) - 1, idx + delta))
    members.insert(new, members.pop(idx))
    return _replace_one(cset, consist_key,
                        lambda x: x._replace(members=tuple(members)))


def _replace_one(cset, key, fn):
    return cset._replace(consists=tuple(fn(c) if c.key == key else c
                                        for c in cset.consists))


# --- constraint generation ---------------------------------------------------

def neighbours(consist):
    """Who may sit next to whom in THIS train -> {vehicle: (prevs, nexts)}.

    Sets of vehicle names, before any keyword is added. Everything that makes this
    interesting - optional members, repeatable sections, reversibility - is here.
    """
    out = {}
    ms = list(consist.members)
    if not ms:
        return out

    def touch(v):
        out.setdefault(v, (set(), set()))
        return out[v]

    for m in ms:
        touch(m.vehicle)

    for i, m in enumerate(ms):
        # A repeatable member may follow itself. Forget this and a "3 to 6 middle
        # cars" section builds exactly one car, because the second one may not
        # couple to the first.
        if m.repeatable:
            touch(m.vehicle)[0].add(m.vehicle)
            touch(m.vehicle)[1].add(m.vehicle)

        # Who can come after m: the next member, and - if that one is optional -
        # the one after it, and so on. An optional member does not break the chain
        # around it; it opens a shortcut past it.
        for j in range(i + 1, len(ms)):
            nxt = ms[j]
            touch(m.vehicle)[1].add(nxt.vehicle)
            touch(nxt.vehicle)[0].add(m.vehicle)
            if not nxt.optional:
                break

    if consist.reversible:
        # The same set, the other way round. Not the engine reversing anything -
        # the constraints must simply also permit the mirrored order.
        rev = consist._replace(members=tuple(reversed(ms)), reversible=False)
        for v, (p, n) in neighbours(rev).items():
            touch(v)[0].update(p)
            touch(v)[1].update(n)

    return out


def ends(consist):
    """Which vehicles may lead and which may end THIS train -> (leads, tails)."""
    ms = [m for m in consist.members]
    if not ms:
        return set(), set()

    leads, tails = set(), set()
    # The first non-optional member leads; any optional members before it could
    # be absent, so the one after them leads instead.
    for m in ms:
        if m.placement not in (MIDDLE_ONLY, TAIL_ONLY):
            leads.add(m.vehicle)
        if not m.optional:
            break
    for m in reversed(ms):
        if m.placement not in (MIDDLE_ONLY, HEAD_ONLY):
            tails.add(m.vehicle)
        if not m.optional:
            break

    if consist.reversible:
        l2, t2 = ends(consist._replace(members=tuple(reversed(ms)),
                                       reversible=False))
        leads |= l2
        tails |= t2
    return leads, tails


def constraints(cset, only=None):
    """The .dat constraints for every vehicle -> {vehicle: (prev, next)}.

    Tuples of names, sorted, ready for datgen.vehicle_dat(). THE UNION across
    every consist: a vehicle in two formations must accept every neighbour either
    gives it.

    `only`: restrict to these consist keys (the panel's "what would this one do?").
    """
    prevs, nexts = {}, {}
    leads, tails = set(), set()
    placements = {}

    for c in cset.consists:
        if only is not None and c.key not in only:
            continue
        for v, (p, n) in neighbours(c).items():
            prevs.setdefault(v, set()).update(p)
            nexts.setdefault(v, set()).update(n)
        l, t = ends(c)
        leads |= l
        tails |= t
        for m in c.members:
            # MIDDLE_ONLY is sticky: if any formation says a car may never lead,
            # it may never lead. A vehicle cannot be middle-only here and a cab
            # there - it is one object with one .dat.
            if m.placement != ANYWHERE:
                placements.setdefault(m.vehicle, set()).add(m.placement)

    out = {}
    for v in sorted(set(prevs) | set(nexts)):
        p = set(prevs.get(v, ()))
        n = set(nexts.get(v, ()))
        pl = placements.get(v, set())

        if MIDDLE_ONLY in pl or HEAD_ONLY in pl or TAIL_ONLY in pl:
            if MIDDLE_ONLY in pl:
                p.add(ANY)
                n.add(ANY)
            if HEAD_ONLY in pl:
                p.add(NONE)
            if TAIL_ONLY in pl:
                n.add(NONE)
        if v in leads and MIDDLE_ONLY not in pl and TAIL_ONLY not in pl:
            p.add(NONE)
        if v in tails and MIDDLE_ONLY not in pl and HEAD_ONLY not in pl:
            n.add(NONE)

        out[v] = (tuple(_sorted_keywords(p)), tuple(_sorted_keywords(n)))
    return out


def _sorted_keywords(names):
    """Keywords first, then names. Cosmetic, but a stable order means a .dat that
    does not churn between runs - and a diff you can read."""
    kw = [k for k in KEYWORDS if k in names]
    return kw + sorted(n for n in names if n not in KEYWORDS)


def diff(cset, current):
    """What applying these constraints would do -> {vehicle: (added, removed, kept)}.

    `current`: {vehicle: (prev, next)} as things stand. The panel shows this
    BEFORE anything is written, because a tool that silently rewrites the coupling
    of every vehicle in a project is a tool nobody should press.
    """
    wanted = constraints(cset)
    out = {}
    for v in sorted(set(wanted) | set(current or {})):
        want_p, want_n = wanted.get(v, ((), ()))
        have_p, have_n = (current or {}).get(v, ((), ()))
        added = ([("prev", x) for x in want_p if x not in have_p]
                 + [("next", x) for x in want_n if x not in have_n])
        removed = ([("prev", x) for x in have_p if x not in want_p]
                   + [("next", x) for x in have_n if x not in want_n])
        kept = ([("prev", x) for x in want_p if x in have_p]
                + [("next", x) for x in want_n if x in have_n])
        out[v] = (tuple(added), tuple(removed), tuple(kept))
    return out


# --- validation --------------------------------------------------------------

def check(cset, known=None, exportable=None):
    """Everything wrong -> (Finding, ...), errors first.

    known:      vehicle names that exist (variants + base objects). None = do not check.
    exportable: names that will actually be rendered. None = do not check.
    """
    out = list(_check_set(cset))
    for c in cset.consists:
        out.extend(_check_consist(c, cset, known, exportable))
    out.extend(_check_constraints(cset))
    return tuple(sorted(out, key=lambda f: scenecheck._ORDER[f.level]))


def _check_set(cset):
    names, keys = {}, {}
    for c in cset.consists:
        if not _KEY_RE.match(c.key or ""):
            yield Finding(ERROR, "unstable-key",
                          "Consist %r has no stable key" % (c.name,))
        if c.key in keys:
            yield Finding(ERROR, "duplicate-key",
                          "Two consists share the key %r" % (c.key,))
        keys[c.key] = c
        if not (c.name or "").strip():
            yield Finding(ERROR, "no-name", "A consist has no name")
        elif c.name in names:
            yield Finding(ERROR, "duplicate-name",
                          "Two consists are called %r" % (c.name,))
        names[c.name] = c


def _check_consist(c, cset, known, exportable):
    if not c.members:
        yield Finding(WARNING, "empty-consist",
                      "%r has no vehicles in it" % (c.name,))
        return

    seen = {}
    for m in c.members:
        if not _KEY_RE.match(m.key or ""):
            yield Finding(ERROR, "unstable-member-key",
                          "A member of %r has no stable key" % (c.name,))
        if m.key in seen:
            yield Finding(ERROR, "duplicate-member-key",
                          "%r has two members with the key %r" % (c.name, m.key))
        seen[m.key] = m

        if not (m.vehicle or "").strip():
            yield Finding(ERROR, "no-vehicle",
                          "A position in %r names no vehicle" % (c.name,))
            continue
        if m.vehicle in KEYWORDS:
            # A vehicle actually called "none" or "any" would be read by the
            # writer as the keyword, and the artist would never find out why.
            yield Finding(ERROR, "reserved-name",
                          "%r is a reserved word in a .dat - a vehicle cannot be "
                          "called that" % (m.vehicle,))
        elif not _NAME_OK.match(m.vehicle):
            yield Finding(ERROR, "bad-name",
                          "%r is not a usable vehicle name. The writers match "
                          "names literally" % (m.vehicle,))
        elif known is not None and m.vehicle not in known:
            yield Finding(ERROR, "unknown-vehicle",
                          "%r is in %r but there is no such vehicle"
                          % (m.vehicle, c.name))
        elif exportable is not None and m.vehicle not in exportable:
            yield Finding(WARNING, "not-exportable",
                          "%r is in %r but nothing renders it, so its .dat will "
                          "never exist" % (m.vehicle, c.name))

        if m.placement not in PLACEMENTS:
            yield Finding(ERROR, "bad-placement",
                          "%r is not a placement (%s)"
                          % (m.placement, ", ".join(PLACEMENTS)))
        if m.min_count < 0 or m.max_count < 1:
            yield Finding(ERROR, "bad-count",
                          "%r in %r may repeat %d..%d times, which is not a range"
                          % (m.vehicle, c.name, m.min_count, m.max_count))
        elif m.min_count > m.max_count:
            yield Finding(ERROR, "bad-count",
                          "%r in %r has a minimum (%d) above its maximum (%d)"
                          % (m.vehicle, c.name, m.min_count, m.max_count))

    for m in c.members:
        if not m.articulated:
            continue
        other = seen.get(m.articulated)
        if other is None:
            yield Finding(ERROR, "broken-articulation",
                          "%r is welded to a position that is not in %r"
                          % (m.vehicle, c.name))
        elif other.articulated != m.key:
            # One-way welding is how an "inseparable" pair ships separable.
            yield Finding(ERROR, "one-sided-articulation",
                          "%r says it is welded to %r, but %r does not say so "
                          "back" % (m.vehicle, other.vehicle, other.vehicle))
        elif other.min_count != m.min_count or other.max_count != m.max_count:
            yield Finding(ERROR, "articulation-mismatch",
                          "%r and %r are welded together but may appear a "
                          "different number of times" % (m.vehicle, other.vehicle))

    leads, tails = ends(c)
    if not leads:
        yield Finding(ERROR, "no-head",
                      "Nothing may lead %r - every position is middle-only or "
                      "tail-only, so the game can never build it" % (c.name,))
    if not tails:
        yield Finding(ERROR, "no-tail",
                      "Nothing may end %r - so the game can never build it"
                      % (c.name,))

    if len(c.members) == 1 and c.members[0].placement == MIDDLE_ONLY:
        yield Finding(ERROR, "impossible",
                      "%r is one middle-only vehicle, which cannot exist: it may "
                      "neither lead nor end, and there is nothing else in it"
                      % (c.name,))


def _check_constraints(cset):
    """What only shows up once the union is computed."""
    gen = constraints(cset)
    for v, (p, n) in sorted(gen.items()):
        if NONE in p and ANY in p:
            yield Finding(ERROR, "contradictory",
                          "%r must be at the head (none) and must never be at "
                          "the head (any) at once" % (v,))
        if NONE in n and ANY in n:
            yield Finding(ERROR, "contradictory",
                          "%r must be at the tail and must never be at the tail "
                          "at once" % (v,))
        if v in p or v in n:
            # Legal and normal for a repeatable section - a rake of identical
            # carriages is exactly this. Only worth a word.
            yield Finding(INFORMATION, "self-coupling",
                          "%r may couple to itself, so it can form a rake" % (v,))

    # A vehicle that appears in no consist at all still gets rendered; it simply
    # has no constraints, which means it couples to anything. Say so once.
    for c in cset.consists:
        for m in c.members:
            if m.vehicle not in gen:
                yield Finding(WARNING, "isolated",
                              "%r is in %r but ended up with no constraints"
                              % (m.vehicle, c.name))


# --- the summary -------------------------------------------------------------

# What a summary can say, and what it must refuse to say.
CONFIRMED = "confirmed"        # read from the vehicle's own fields
COMPUTED = "computed"          # arithmetic over confirmed values
UNAVAILABLE = "unavailable"    # nobody told us


class Figure(NamedTuple):
    value: object
    kind: str
    note: str = ""


def summary(consist, vehicles):
    """What this train adds up to -> {field: Figure}.

    `vehicles`: {name: {field: value}} - the panel's numbers per vehicle.

    NOTHING IS INVENTED. A field missing from any member makes the total
    UNAVAILABLE rather than a sum over the ones that happened to have it: a weight
    that silently omits two cars is worse than no weight, because it looks like an
    answer.
    """
    out = {}
    if not consist.members:
        return out

    rows = []
    missing = set()
    for m in consist.members:
        v = (vehicles or {}).get(m.vehicle)
        if v is None:
            missing.add(m.vehicle)
        else:
            rows.append((m, v))

    out["cars"] = Figure(len(consist.members), COMPUTED)
    if missing:
        out["_missing"] = Figure(tuple(sorted(missing)), UNAVAILABLE,
                                 "no figures for these vehicles")

    def total(field):
        if missing or not rows:
            return Figure(None, UNAVAILABLE, "not every vehicle has a %s" % field)
        vals = [r[1].get(field) for r in rows]
        if any(x is None for x in vals):
            return Figure(None, UNAVAILABLE, "not every vehicle has a %s" % field)
        return Figure(sum(v * r[0].min_count for v, r in zip(vals, rows)), COMPUTED)

    for field in ("length", "payload", "power", "weight", "cost", "runningcost"):
        out[field] = total(field)

    if rows and not missing:
        speeds = [r[1].get("speed") for r in rows]
        if all(s is not None for s in speeds):
            slowest = min(speeds)
            out["speed"] = Figure(slowest, COMPUTED,
                                  "the slowest car limits the whole train")
        ways = {r[1].get("waytype") for r in rows}
        out["waytype"] = (Figure(ways.pop(), CONFIRMED) if len(ways) == 1
                          else Figure(None, UNAVAILABLE,
                                      "the cars disagree about the waytype"))
        engines = {r[1].get("engine_type") for r in rows if r[1].get("power")}
        out["electric"] = Figure(engines == {"electric"} if engines else None,
                                 CONFIRMED if engines else UNAVAILABLE)
        intro = [r[1].get("intro_year") for r in rows]
        out["intro_year"] = (Figure(max(intro), COMPUTED,
                                    "the whole train exists once its last car does")
                             if all(i is not None for i in intro)
                             else Figure(None, UNAVAILABLE))
    return out
