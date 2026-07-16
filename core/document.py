"""The one persisted document: variants, consists, and what the preview knows.

Phase 2 stored variants as JSON in a single Blender string property, because a
CollectionProperty would have put the format in bpy where it could be neither
migrated nor tested without Blender. Phase 3 adds consists, and the rule stands:
ONE document, one property, one place the format lives.

    {
      "schema_version": 2,
      "variants": { ... }          <- core/variants.py owns this section
      "consists": { ... }          <- core/consists.py owns this section
      "preview":  { ... }
    }

WHY A SEPARATE MODULE
    variants.py should not have to know consists exist, and vice versa. Each owns
    its own section and nothing else; this composes them. The alternative - growing
    variants.py's document to swallow consists - would make "the variant format"
    and "the file format" the same thing, and the next section would have to go
    through variants.py too.

MIGRATION IS A LADDER, NOT A GUESS
    v0  no version at all. Also what an EMPTY property looks like, so v0 must
        always mean "nothing to lose".
    v1  phase 2: variants only, at the TOP LEVEL of the document.
    v2  phase 3: variants moved into their own section; consists and preview added.

    A v1 document is a real thing that exists in real .blend files, so the step
    from it is a real migration and is tested against a literal v1 document -
    not against one this module produced.

A FUTURE DOCUMENT IS NOT REINTERPRETED
    A document claiming a version we do not have is handed back untouched, with a
    finding, and nothing is written over it. Guessing at a newer format is how an
    old kit eats a project made with a newer one - and the artist finds out when
    their variants are gone.
"""

import json

from . import consists as _consists
from . import scenecheck
from . import variants as _variants

SCHEMA_VERSION = 2

Finding = scenecheck.Finding
ERROR = scenecheck.ERROR
WARNING = scenecheck.WARNING
INFORMATION = scenecheck.INFORMATION
blocking = scenecheck.blocking


class Document:
    """Everything a project persists. A plain holder - the sections do the work.

    `unknown` keeps whatever we did not recognise. A future kit's extra section
    survives a round trip through this one rather than being silently dropped,
    which is the difference between an old kit that cannot read a new file and an
    old kit that destroys it.
    """

    __slots__ = ("variants", "consists", "preview", "unknown", "version_seen")

    def __init__(self, variants=None, consists=None, preview=None,
                 unknown=None, version_seen=SCHEMA_VERSION):
        self.variants = variants if variants is not None else \
            _variants.VariantSet(obj_type="vehicle")
        self.consists = consists if consists is not None else \
            _consists.ConsistSet()
        self.preview = dict(preview or {})
        self.unknown = dict(unknown or {})
        self.version_seen = version_seen

    def __eq__(self, other):
        return (isinstance(other, Document)
                and self.variants == other.variants
                and self.consists == other.consists
                and self.preview == other.preview
                and self.unknown == other.unknown)

    def __repr__(self):
        return "Document(v=%d, %d variants, %d consists)" % (
            self.version_seen, len(self.variants.variants),
            len(self.consists.consists))

    @property
    def from_the_future(self):
        return self.version_seen > SCHEMA_VERSION


_KNOWN_KEYS = {"schema_version", "variants", "consists", "preview", "obj_type",
               "axes", "next_key"}


def load(text, obj_type="vehicle"):
    """Parse, migrating forward -> Document. Never raises.

    A .blend whose property is empty, truncated, or from a kit that predates any
    of this is a .blend with no variants and no consists - not one that fails to
    open. Refusing to guess is the point; refusing to OPEN is not an option.
    """
    if not text or not str(text).strip():
        return Document()
    try:
        raw = json.loads(text)
    except (ValueError, TypeError):
        return Document()
    if not isinstance(raw, dict):
        return Document()

    version = raw.get("schema_version", 0)
    if not isinstance(version, int) or isinstance(version, bool) or version < 0:
        version = 0

    if version > SCHEMA_VERSION:
        # Hand it back whole, marked. write() will refuse to overwrite it.
        return Document(unknown=dict(raw), version_seen=version)

    raw = migrate(dict(raw), version, obj_type)

    return Document(
        variants=_variants.load(json.dumps(raw.get("variants") or {}), obj_type),
        consists=_load_consists(raw.get("consists")),
        preview=raw.get("preview") if isinstance(raw.get("preview"), dict) else {},
        unknown={k: v for k, v in raw.items() if k not in _KNOWN_KEYS},
        version_seen=SCHEMA_VERSION,
    )


def dump(doc):
    """Serialise -> str. Stable, so a .blend saved twice is the same bytes.

    A document from the future is written back EXACTLY as it came in. We could not
    read it, so we have nothing to say about it, and saying it anyway would mean
    truncating somebody's work to the subset this version understands.
    """
    if doc.from_the_future:
        return json.dumps(doc.unknown, indent=1, sort_keys=False)

    out = {"schema_version": SCHEMA_VERSION}
    out.update({k: v for k, v in sorted(doc.unknown.items())})
    out["variants"] = json.loads(_variants.dump(doc.variants))
    out["consists"] = _dump_consists(doc.consists)
    out["preview"] = dict(sorted(doc.preview.items()))
    return json.dumps(out, indent=1, sort_keys=False)


# --- the consists section ----------------------------------------------------

def _load_consists(raw):
    if not isinstance(raw, dict):
        return _consists.ConsistSet()
    out = []
    stored = raw.get("consists")
    for item in stored if isinstance(stored, list) else ():
        if not isinstance(item, dict):
            continue
        members = []
        ms = item.get("members")
        for m in ms if isinstance(ms, list) else ():
            if not isinstance(m, dict):
                continue
            members.append(_consists.Member(
                key=str(m.get("key", "")),
                vehicle=str(m.get("vehicle", "")),
                min_count=_int(m.get("min_count"), 1),
                max_count=_int(m.get("max_count"), 1),
                placement=str(m.get("placement", _consists.ANYWHERE)),
                articulated=str(m.get("articulated", "")),
                note=str(m.get("note", "")),
            ))
        out.append(_consists.Consist(
            key=str(item.get("key", "")),
            name=str(item.get("name", "")),
            members=tuple(members),
            reversible=bool(item.get("reversible", False)),
            recommended=bool(item.get("recommended", False)),
            note=str(item.get("note", "")),
        ))
    cset = _consists.ConsistSet(consists=tuple(out),
                               next_key=_int(raw.get("next_key"), 0))
    # A counter below a live key would hand that key out again - the bug
    # core/variants.py shipped and a test caught. Lift it, always.
    return cset._replace(
        next_key=max(cset.next_key, _consists._highest_used(cset.consists) + 1))


def _dump_consists(cset):
    return {
        "next_key": max(cset.next_key,
                        _consists._highest_used(cset.consists) + 1),
        "consists": [
            {
                "key": c.key, "name": c.name,
                "reversible": c.reversible, "recommended": c.recommended,
                "note": c.note,
                "members": [
                    {"key": m.key, "vehicle": m.vehicle,
                     "min_count": m.min_count, "max_count": m.max_count,
                     "placement": m.placement, "articulated": m.articulated,
                     "note": m.note}
                    for m in c.members
                ],
            }
            for c in cset.consists
        ],
    }


def _int(v, default):
    if isinstance(v, bool) or not isinstance(v, int):
        return default
    return v


# --- migrations --------------------------------------------------------------

def _migrate_0_to_1(raw, obj_type):
    """v0: no version. Also an empty property, so it must lose nothing."""
    raw.setdefault("variants", [])
    raw.setdefault("axes", {})
    return raw


def _migrate_1_to_2(raw, obj_type):
    """v1 (phase 2) kept the variant fields at the TOP LEVEL:

        {"schema_version": 1, "obj_type": ..., "axes": ..., "next_key": ...,
         "variants": [ ... ]}

    v2 moves them into their own section so consists can have one too. This is a
    real migration against files that really exist - .blend files saved by 0.9.0 -
    so it is tested against a literal v1 document, not one this module made.
    """
    section = {
        "schema_version": _variants.SCHEMA_VERSION,
        "obj_type": raw.pop("obj_type", obj_type),
        "axes": raw.pop("axes", {}),
        "next_key": raw.pop("next_key", 0),
        "variants": raw.pop("variants", []),
    }
    raw["variants"] = section
    raw.setdefault("consists", {})
    raw.setdefault("preview", {})
    return raw


_MIGRATIONS = {0: _migrate_0_to_1, 1: _migrate_1_to_2}


def migrate(raw, version, obj_type="vehicle"):
    while version < SCHEMA_VERSION:
        step = _MIGRATIONS.get(version)
        if step is None:
            break                       # a gap in the ladder: do not guess
        raw = step(raw, obj_type)
        version += 1
    raw["schema_version"] = SCHEMA_VERSION
    return raw


def check(doc):
    """Anything wrong with the document itself -> (Finding, ...)."""
    out = []
    if doc.from_the_future:
        out.append(Finding(
            ERROR, "future-document",
            "This project was saved by a newer version of the kit (document "
            "version %d; this one understands %d). It has been left exactly as "
            "it is and nothing will be written over it - update the add-on"
            % (doc.version_seen, SCHEMA_VERSION)))
    return tuple(out)
