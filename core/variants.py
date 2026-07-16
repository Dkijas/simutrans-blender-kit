"""One scene, many objects.

Read docs/variants-in-simutrans.md first. The short version, because it decides
the whole shape of this module:

THE ENGINE KNOWS TWO KINDS OF VARIANT AND ONLY ONE OF THEM IS A VARIANT.

  * AXIS variants are indexed inside one object, by the image key the writer
    builds with sprintf. Whatever indices that key has ARE the axes and there are
    no others. A vehicle's widest key is `freightimage[%d][%s]`: cargo, and
    nothing else. No season. No state. No livery.

  * SIBLING objects are everything else - a livery, a family member, a class with
    a different engine. Separate name=, separate .dat, separate .pak. The engine
    has no idea they are related.

Merging the two would give the artist a tool that lies. Ask for a "winter livery"
as an axis and the engine has nowhere to put it; the .pak compiles, the game
loads, and the second sprite is never drawn. So AXES below says which axes each
type really has, and everything else is a sibling.

There are NO liveries in base Simutrans. The string `livery` does not occur in
the engine outside the word "delivery". They are a Simutrans Extended feature.
A green loco and a red loco are two objects.

WHAT THIS MODULE IS FOR
    Sibling objects are the repetitive work nothing addressed. Five cars is five
    .dat files; three liveries is three more. Today that is: edit the panel by
    hand, press Render, repeat - with the fields that must differ sitting next to
    the fields that must not, and no record of which was which.

    A VariantSet is that record. One base, N variants, each a set of OVERRIDES.
    Geometry is never duplicated: a variant is a dict and a material swap.

PERSISTENCE
    JSON, with a schema_version, carried in ONE Blender string property. Not a
    CollectionProperty - that would put the format in bpy, where it cannot be
    migrated without Blender and cannot be tested without it either. This way the
    whole format lives here, `load()` migrates old documents forward, and a .blend
    from an older kit opens without losing its variants.
"""

import json
import re
from typing import NamedTuple

from . import scenecheck

# Bump when the stored shape changes, and add a step to _MIGRATIONS. A document
# with no version at all is a v0 document - which is also what an EMPTY property
# looks like, so v0 must always mean "nothing to lose".
SCHEMA_VERSION = 1

# --- the axes, read off the engine's own writers -----------------------------
#
# Not retyped from a tutorial: each is the index list of the widest image key
# that type's writer builds. tests/test_variants.py checks these against
# core/dat_schema.json, which tools/extract_dat_schema.py pulls out of the
# engine's writers and tests/test_schema_drift.py holds to them.
#
# The empty tuples are the point of the table. A way-object's key is
# `backimage[%s]` and stops - a seasonal catenary is not a thing you can model.
AXES = {
    "vehicle": ("freight",),
    "building": ("phase", "season"),
    "factory": ("phase", "season"),
    "way": ("season",),
    "wayobj": (),
    "roadsign": ("state",),
    "tunnel": ("season",),
    "bridge": (),
}

# The collection prefix each axis is modelled in. templates owns the spellings;
# this only says which axis uses which.
AXIS_PREFIX = {
    "freight": "freight_",
    "phase": "phase_",
    "season": "season_",
    "state": "state_",
}

# What an artist may sensibly ask for that the engine will NOT index. Each maps
# to the reason, which is a fact about the engine and not an opinion.
NOT_AN_AXIS = {
    "livery": "base Simutrans has no liveries - that is a Simutrans Extended "
              "feature. A second livery is a separate object with its own name",
    "night": "the engine does day and night itself, from the reserved colours in "
             "the sprite you already rendered (simview.cc hours2night[]). There "
             "is nothing to model twice",
    "day": "see 'night' - there is one sprite, and the engine darkens it",
}

# The fields a sibling object MUST NOT share with its base, because they are what
# makes it a different object at all.
MUST_DIFFER = ("obj_name",)

# The fields that are the object's identity as a TYPE. Overriding these does not
# make a livery, it makes a different vehicle - which is legal, and worth saying
# out loud rather than refusing.
IDENTITY_FIELDS = ("waytype", "obj_type")

_KEY_RE = re.compile(r"^v[0-9a-f]{8}$")


class Variant(NamedTuple):
    """One sibling object, as a diff against the base.

    key       stable, allocated once, never reused. NOT the name - see below.
    name      what goes in the .dat as name=, and what the artist reads.
    overrides panel field -> value. Only what DIFFERS from the base.
    materials material slot name -> (r, g, b). The livery, in practice.
    show/hide collections to force on or off for this variant.
    note      the artist's own words. Never read by anything.

    The key is not the name because the name will change - `Loco_Green` becomes
    `RENFE_269_Green` the day they learn the class number. Keying by name would
    make a rename silently create a new variant and abandon the old one's
    overrides, and the artist would find out much later, if at all.
    """
    key: str
    name: str
    overrides: dict = None
    materials: dict = None
    show: tuple = ()
    hide: tuple = ()
    note: str = ""


class VariantSet(NamedTuple):
    """Every sibling of one base object, plus the axes it uses.

    next_key is PERSISTED, and it has to be. The obvious implementation - scan the
    live variants and take the lowest free number - reuses the key of a deleted
    variant, so a reference held anywhere (a saved package, a note, an undo step)
    silently comes to mean somebody else's variant. The first version of this
    module did exactly that while its own docstring claimed keys are never reused;
    a test caught it. A counter that only ever goes up cannot.
    """
    obj_type: str
    variants: tuple = ()
    axes: dict = None          # axis name -> how many, e.g. {"season": 4}
    next_key: int = 0


def format_key(n):
    return "v%08x" % n


def new_key(vset):
    """The next key, and the set that has consumed it -> (VariantSet, str).

    Deterministic: core/ must not reach for a clock or an RNG, or a .blend saved
    twice would differ. A counter is enough - as long as it is the SET's counter
    and not a scan of its members. See VariantSet.next_key.
    """
    n = max(vset.next_key, _highest_used(vset.variants) + 1)
    return vset._replace(next_key=n + 1), format_key(n)


def _highest_used(variants):
    """The largest key number in use, or -1.

    Belt and braces for a document whose counter is missing or has been rewound
    by hand: a counter BELOW a live key would hand out that key again.
    """
    top = -1
    for v in variants or ():
        if _KEY_RE.match(v.key or ""):
            try:
                top = max(top, int(v.key[1:], 16))
            except ValueError:
                pass
    return top


# --- persistence -------------------------------------------------------------

def load(text, obj_type="vehicle"):
    """Parse the stored document, migrating it forward -> VariantSet.

    Never raises on rubbish. A .blend whose property is empty, truncated, or from
    a kit that predates this module is a .blend with no variants - not a .blend
    that fails to open. Losing the panel is not an acceptable outcome for a
    document we cannot read; refusing to guess at its contents is.
    """
    if not text or not text.strip():
        return VariantSet(obj_type=obj_type, variants=(), axes={})
    try:
        raw = json.loads(text)
    except (ValueError, TypeError):
        return VariantSet(obj_type=obj_type, variants=(), axes={})
    if not isinstance(raw, dict):
        return VariantSet(obj_type=obj_type, variants=(), axes={})

    version = raw.get("schema_version", 0)
    if not isinstance(version, int) or version < 0:
        version = 0
    raw = migrate(raw, version)

    variants = []
    orphans = []
    # `variants` may be anything at all - this is a document a human could have
    # edited, and "never raises on rubbish" is only true if every field is
    # treated as untrusted, not just the ones that looked risky.
    stored = raw.get("variants")
    for item in stored if isinstance(stored, list) else ():
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        if not isinstance(key, str) or not _KEY_RE.match(key):
            # Give it one AFTER the loop, from the counter - allocating here from
            # a scan of what we have read so far is the reuse bug all over again.
            key = None
            orphans.append(len(variants))
        variants.append(Variant(
            key=key,
            name=str(item.get("name", "")),
            overrides=_dict_of(item.get("overrides")),
            materials={k: tuple(v)
                       for k, v in _dict_of(item.get("materials")).items()
                       if isinstance(v, (list, tuple)) and len(v) == 3},
            show=_strs_of(item.get("show")),
            hide=_strs_of(item.get("hide")),
            note=str(item.get("note", "")),
        ))
    vset = VariantSet(
        obj_type=str(raw.get("obj_type", obj_type)),
        variants=tuple(variants),
        axes={str(k): int(v) for k, v in _dict_of(raw.get("axes")).items()
              if (isinstance(v, int) and not isinstance(v, bool))
              or (isinstance(v, str) and v.isdigit())},
        # A document with no counter (v0, or one hand-edited) gets one ABOVE
        # every key it already carries, never below.
        next_key=_counter_of(raw, variants),
    )
    for i in orphans:
        vset, key = new_key(vset)
        fixed = list(vset.variants)
        fixed[i] = fixed[i]._replace(key=key)
        vset = vset._replace(variants=tuple(fixed))
    return vset


def _counter_of(raw, variants):
    stored = raw.get("next_key")
    # bool is an int in Python, and `"next_key": true` must not become 1
    if not isinstance(stored, int) or isinstance(stored, bool) or stored < 0:
        stored = 0
    return max(stored, _highest_used(variants) + 1)


def _dict_of(v):
    """A dict, whatever we were handed."""
    return dict(v) if isinstance(v, dict) else {}


def _strs_of(v):
    """A tuple of strings, whatever we were handed."""
    if not isinstance(v, (list, tuple)):
        return ()
    return tuple(str(x) for x in v if isinstance(x, str))


def dump(vset):
    """Serialise -> str. Stable key order, so a .blend saved twice is the same."""
    return json.dumps({
        "schema_version": SCHEMA_VERSION,
        "obj_type": vset.obj_type,
        # Persisted so a deleted variant's key is never handed out again.
        "next_key": max(vset.next_key, _highest_used(vset.variants) + 1),
        "axes": dict(sorted((vset.axes or {}).items())),
        "variants": [
            {
                "key": v.key,
                "name": v.name,
                "overrides": dict(sorted((v.overrides or {}).items())),
                "materials": {k: list(rgb)
                              for k, rgb in sorted((v.materials or {}).items())},
                "show": list(v.show),
                "hide": list(v.hide),
                "note": v.note,
            }
            for v in vset.variants
        ],
    }, indent=1, sort_keys=False)


def _migrate_0_to_1(raw):
    """v0 is any document without a version, which includes the empty property.

    There has never been a released format before this one, so there is nothing to
    convert: the step exists so the LADDER exists, and so the next one is an edit
    rather than an argument about where migrations go.
    """
    raw.setdefault("variants", [])
    raw.setdefault("axes", {})
    return raw


_MIGRATIONS = {0: _migrate_0_to_1}


def migrate(raw, version):
    """Walk a document up to SCHEMA_VERSION, one step at a time."""
    while version < SCHEMA_VERSION:
        step = _MIGRATIONS.get(version)
        if step is None:
            # A gap in the ladder. Do not guess - hand back what we have and let
            # check() report it, rather than silently reinterpreting the file.
            break
        raw = step(raw)
        version += 1
    raw["schema_version"] = SCHEMA_VERSION
    return raw


# --- editing -----------------------------------------------------------------

def add(vset, name, **kw):
    """A new variant with a fresh key -> (VariantSet, Variant)."""
    vset, key = new_key(vset)
    v = Variant(key=key, name=name,
                overrides=dict(kw.pop("overrides", {}) or {}),
                materials=dict(kw.pop("materials", {}) or {}), **kw)
    return vset._replace(variants=vset.variants + (v,)), v


def duplicate(vset, key):
    """Copy a variant, keeping its overrides and taking a NEW key.

    The copy's name gets a suffix rather than being left identical: two variants
    with one name are two .dat files with one name=, and the pakset loader takes
    whichever it read last. check() catches it, but a tool that creates the
    problem and then complains about it is a tool doing half a job.
    """
    src = get(vset, key)
    if src is None:
        return vset, None
    name = _unique_name(vset, src.name)
    vset, fresh = new_key(vset)
    copy = src._replace(key=fresh, name=name)
    return vset._replace(variants=vset.variants + (copy,)), copy


def _unique_name(vset, base):
    taken = {v.name for v in vset.variants}
    if base not in taken:
        return base
    i = 2
    while "%s_%d" % (base, i) in taken:
        i += 1
    return "%s_%d" % (base, i)


def rename(vset, key, name):
    """Rename in place. The KEY does not move, which is the whole point of it."""
    return _replace_one(vset, key, lambda v: v._replace(name=name))


def remove(vset, key):
    return vset._replace(variants=tuple(v for v in vset.variants if v.key != key))


def get(vset, key):
    for v in vset.variants:
        if v.key == key:
            return v
    return None


def _replace_one(vset, key, fn):
    out = []
    for v in vset.variants:
        out.append(fn(v) if v.key == key else v)
    return vset._replace(variants=tuple(out))


# --- resolving ---------------------------------------------------------------

def resolve(variant, base):
    """The final field values for this variant -> dict.

    base is the panel's fields as a plain dict. An override wins; everything else
    is inherited, which is what makes this a diff and not a copy.
    """
    out = dict(base)
    out.update(variant.overrides or {})
    out["obj_name"] = variant.name
    return out


def inherited(variant, base):
    """What this variant takes from the base, unchanged -> {field: value}.

    The panel shows this. An artist looking at a variant needs to know what they
    are NOT looking at: a field they believe they set, and did not, is how a whole
    family ships with one car's weight.
    """
    ov = variant.overrides or {}
    return {k: v for k, v in base.items() if k not in ov}


# --- validation --------------------------------------------------------------
#
# scenecheck's Finding, ERROR/WARNING/INFORMATION and blocking() are reused
# wholesale. A second finding type with the same three levels would be a second
# thing for the panel to render and a second thing to keep in step.

Finding = scenecheck.Finding
ERROR = scenecheck.ERROR
WARNING = scenecheck.WARNING
INFORMATION = scenecheck.INFORMATION
blocking = scenecheck.blocking

# makeobj reads name= as a token. A name with a space or a '#' is not a name the
# writers can carry: '#' starts a comment at column 0 and the pakset's own
# cross-references (Constraint[Next], freight, way) are matched literally.
_NAME_OK = re.compile(r"^[A-Za-z0-9_.\-+]+$")


def check(vset, base=None, collections=None, materials=None):
    """Everything wrong with this variant set -> (Finding, ...), errors first."""
    out = []
    out.extend(_check_axes(vset))
    out.extend(_check_variants(vset, base or {}, collections or {},
                              materials or ()))
    return tuple(sorted(out, key=lambda f: scenecheck._ORDER[f.level]))


def _check_axes(vset):
    allowed = AXES.get(vset.obj_type)
    if allowed is None:
        yield Finding(ERROR, "unknown-type",
                      "Unknown object type %r" % (vset.obj_type,))
        return
    for axis, count in sorted((vset.axes or {}).items()):
        if axis in NOT_AN_AXIS:
            yield Finding(ERROR, "not-an-axis",
                          "%r is not something the engine indexes: %s"
                          % (axis, NOT_AN_AXIS[axis]))
        elif axis not in allowed:
            yield Finding(ERROR, "wrong-axis",
                          "A %s has no %r axis - the widest image key its writer "
                          "builds does not index one. It would compile and never "
                          "be drawn. A %s that differs by %s is a separate object"
                          % (vset.obj_type, axis, vset.obj_type, axis))
        elif count < 1:
            yield Finding(WARNING, "empty-axis",
                          "Axis %r is set to %d" % (axis, count))


def _check_variants(vset, base, collections, materials):
    seen_names = {}
    seen_keys = {}
    for v in vset.variants:
        if not _KEY_RE.match(v.key or ""):
            yield Finding(ERROR, "unstable-key",
                          "Variant %r has no stable key. Renaming it would "
                          "orphan its overrides" % (v.name,))
        if v.key in seen_keys:
            yield Finding(ERROR, "duplicate-key",
                          "Two variants share the key %r - one of them will be "
                          "lost on the next save" % (v.key,))
        seen_keys[v.key] = v

        if not (v.name or "").strip():
            yield Finding(ERROR, "no-name", "A variant has no name")
        elif not _NAME_OK.match(v.name):
            # The .dat's silent killer, from the other end: a name with a space
            # in it is read whole, and every cross-reference to it then fails to
            # resolve at pakset load - long after makeobj said nothing.
            yield Finding(ERROR, "bad-name",
                          "%r is not a usable name=. Letters, digits, _ . - + "
                          "only: the writers match names literally and a space "
                          "or a '#' breaks every reference to it" % (v.name,))
        elif v.name in seen_names:
            yield Finding(ERROR, "duplicate-name",
                          "Two variants are called %r. They are two .dat files "
                          "with one name=, and the pakset keeps whichever it "
                          "read last" % (v.name,))
        else:
            seen_names[v.name] = v

        if base and v.name == base.get("obj_name"):
            yield Finding(ERROR, "shadows-base",
                          "Variant %r has the same name as the base object"
                          % (v.name,))

        for field in v.overrides or {}:
            if base and field not in base:
                yield Finding(WARNING, "unknown-field",
                              "Variant %r overrides %r, which is not a field of "
                              "this object" % (v.name, field))
            if field in MUST_DIFFER:
                yield Finding(WARNING, "name-override",
                              "Variant %r overrides %r. Set the variant's name "
                              "instead - that is what it is for"
                              % (v.name, field))
            elif field in IDENTITY_FIELDS:
                # Legal, and possibly deliberate. NOT an error: an artist may
                # genuinely want the same body on road and rail.
                yield Finding(INFORMATION, "identity-override",
                              "Variant %r changes %r. That is a different kind "
                              "of object, not a repaint - which is allowed, but "
                              "check it is what you meant" % (v.name, field))

        for name in sorted(v.materials or {}):
            if materials and name not in materials:
                yield Finding(ERROR, "missing-material",
                              "Variant %r repaints material %r, which is not in "
                              "this file" % (v.name, name))
        for name in tuple(v.show) + tuple(v.hide):
            if collections and name not in collections:
                yield Finding(ERROR, "missing-collection",
                              "Variant %r refers to collection %r, which is not "
                              "in this file" % (v.name, name))
        for name in set(v.show) & set(v.hide):
            yield Finding(ERROR, "show-and-hide",
                          "Variant %r both shows and hides %r"
                          % (v.name, name))

        if not (v.overrides or v.materials or v.show or v.hide):
            # Not an error: a variant that only renames is a legitimate thing to
            # want (two catalogue entries, one body).
            yield Finding(WARNING, "empty-variant",
                          "Variant %r changes nothing about the base but its "
                          "name" % (v.name,))
