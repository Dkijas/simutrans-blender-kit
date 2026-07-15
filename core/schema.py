"""The .dat schema, taken from the engine, and a linter that uses it.

The schema in dat_schema.json is GENERATED from src/simutrans/descriptor/writer/*.cc
by tools/extract_dat_schema.py - see there for why. tests/test_core.py re-extracts
it and fails if the two have drifted apart.

What the linter is for
----------------------
makeobj will happily compile a .dat that the game then cannot use, and the .dat
format has two failure modes that are completely SILENT:

  * An end-of-line comment is not a comment. tabfile_t::read_line() drops a line
    only when it STARTS with '#'; a '#' after a value is part of the value. So
    `freight=None  # a note` sets freight to "None  # a note" and the pakset
    loader dies with `Cannot resolve 'GOOD-None  # a note'`. Numeric keys hide it,
    because atoi() stops at the space.

  * An INDENTED line is not a key. read_line() also drops any line starting with
    a space. Indent `power=600` to line it up prettily and the engine never sees
    it - your locomotive just quietly has no engine.

Both of these bit us. Neither produces a warning from makeobj.
"""

import json
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCHEMA_PATH = os.path.join(_HERE, "dat_schema.json")

with open(_SCHEMA_PATH, encoding="utf-8") as _f:
    SCHEMA = json.load(_f)

ENGINE_VERSION = SCHEMA["engine_version"]
COMMON_KEYS = SCHEMA["common_keys"]
OBJ_TYPES = SCHEMA["obj_types"]

TOP_LEVEL = sorted(k for k, v in OBJ_TYPES.items() if v["top_level"])


# printf conversions that turn up in the writers' key formats. %i is NOT a typo for
# %d and not an alias we can ignore: roadsign_writer.cc:45 builds its keys with
# sprintf(buf, "image[%s][%i]", ...), so a translator that only knew %d and %s
# recognised NONE of a signal's keys and reported every one of them as unknown.
# NOTE THE STAR ON %s. A printf %s can expand to the EMPTY string, and the writers
# lean on that constantly:
#
#     way_writer.cc:35   static const char* const image_type[]    = { "", "front" };
#     way_writer.cc:33   static const char *slope_heights[2]      = { "", "2" };
#     way_writer.cc:191  sprintf(buf, "%simageup%s[%s][%d]", image_type[b],
#                                slope_heights[h], slope_names[d], season);
#
# so that one format produces `imageup[n][0]` as well as `frontimageup2[n][0]`.
# With a + instead of a *, the linter recognised none of the plain ones and cried
# wolf on 1307 way keys in pak128 alone.
_CONV = {
    "d": r"\d+", "i": r"\d+", "u": r"\d+", "x": r"[0-9a-f]+",
    "s": r"[^\[\]]*",
}


def _pattern_re(fmt):
    """'emptyimage[%s]' -> a regex that matches emptyimage[sw] and friends."""
    out = []
    for part in re.split(r"(%[a-z])", fmt):
        if len(part) == 2 and part[0] == "%":
            if part[1] not in _CONV:
                raise ValueError("core/dat_schema.json has a key format this "
                                 "linter cannot read: %r (conversion %r)"
                                 % (fmt, part))
            out.append(_CONV[part[1]])
        else:
            out.append(re.escape(part))
    return re.compile("^" + "".join(out) + "$")


_PATTERNS = {name: [_pattern_re(f) for f in t["patterns"]]
             for name, t in OBJ_TYPES.items()}


def known_key(obj_type, key):
    """Does the engine read this key for this obj= type?"""
    key = key.lower()
    if key in COMMON_KEYS:
        return True
    t = OBJ_TYPES.get(obj_type)
    if t is None:
        return False
    if key in t["keys"]:
        return True
    return any(p.match(key) for p in _PATTERNS[obj_type])


# HOW the engine reads a key decides whether a stray '#' matters - see _comment_
# finding(). obj.get() hands back the raw text; obj.get_int() and friends run it
# through atoi(), which stops at the first thing that is not a digit.
_TEXT_READERS = ("get", "get_string")


def reader_of(obj_type, key):
    """'get' / 'get_int' / ... , or None if the key is only matched by a pattern.

    A pattern key is an image reference, and image references are the one place the
    engine EXPLICITLY allows a trailing comment (image_writer.cc:340: "after the
    dots also spaces and comments are allowed").
    """
    key = key.lower()
    info = COMMON_KEYS.get(key)
    if info is None:
        t = OBJ_TYPES.get(obj_type)
        info = t["keys"].get(key) if t else None
    return info["reader"] if info else None


# --- tabfile's parameter expansion -------------------------------------------
#
# A .dat key can be a whole FAMILY of keys. tabfile_t::find_parameter_expansion
# treats any bracket group holding a ',' or a '-' as a parameter:
#
#     Image[n,e,s,w][0-1] = classic_signals.0.<4*$1 + $0>
#
# is EIGHT keys, and the value is an arithmetic expression over the parameters.
# Real paksets lean on this constantly - pak128's signals are written exactly like
# that - and a linter that does not expand it reports every one of them as unknown.
# Ours did: 33 warnings on pak128's rail signals alone, all of them wrong.
#
# The one subtlety is the leading dash. The engine's test is `(*s == ',' || *s ==
# '-') && *(s-1) != '['`, so `image[-]` - the ribi for "connects to nothing" - is a
# literal, not a range. Miss that and every way in the pakset explodes into
# nonsense.
_GROUP = re.compile(r"\[([^\]]*)\]")


def _values_of(content):
    """The concrete texts one bracket group stands for.

    Malformed input must not crash the linter. `image[0-]` is a real thing a person
    types by accident, and its range half `0-` has no upper bound: int("") threw
    ValueError and took down the whole pakset scan with it. A group we cannot parse
    is returned UNEXPANDED - as the single literal it is - so the scan survives.

    (The literal `image[0-]` then flows on and, because it starts with `image[`, is
    accepted as an image-reference pattern rather than reported. Catching a
    malformed image index is a separate rule this does not add; the point here is
    only that one bad line no longer kills the lint of every file after it.)
    """
    if content[:1].isdigit():
        # numeric: '0-3' is a range, '0,2,5' is a list, and both can be mixed
        out = []
        for token in content.split(","):
            if "-" in token[1:]:
                a, b = token.split("-", 1)
                try:
                    out.extend(str(v) for v in range(int(a), int(b) + 1))
                except ValueError:
                    return [content]        # e.g. '0-': not a range, leave it whole
            else:
                out.append(token)
        return out
    return content.split(",")          # names: n, e, s, w


def expand_key(key):
    """'image[n,e,s,w][0-1]' -> the eight keys the engine will actually look for."""
    parts = _GROUP.split(key)          # [before, group, between, group, ..., after]
    out = [parts[0]]
    for i in range(1, len(parts), 2):
        content, tail = parts[i], parts[i + 1]
        is_param = "," in content or "-" in content[1:]
        values = _values_of(content) if is_param else [content]
        out = [p + "[" + v + "]" + tail for p in out for v in values]
        if len(out) > 4096:            # a runaway range; the engine caps at 256 too
            return [key]
    return out


def types_reading(key):
    """Which obj= types DO read this key? Turns 'unknown key' into a hint."""
    key = key.lower()
    return sorted(name for name, t in OBJ_TYPES.items()
                  if t["top_level"] and (key in t["keys"]
                                         or any(p.match(key) for p in _PATTERNS[name])))


class Finding:
    def __init__(self, level, line, message, code="", path=None):
        self.level, self.line, self.message = level, line, message
        self.code = code              # a stable rule id, for suppression and --json
        self.path = path              # set by the cross-file passes; else None

    def __repr__(self):
        tag = " [%s]" % self.code if self.code else ""
        return "%s:%d: %s%s: %s" % (self.path or "dat", self.line, self.level,
                                    tag, self.message)

    def as_dict(self):
        return {"file": self.path, "line": self.line, "level": self.level,
                "code": self.code, "message": self.message}


# BackImage[l][y][x][h][phase][season] - the six-index form
_SEASON_KEY = re.compile(r"^(?:back|front)image"
                         r"\[\d+\]\[\d+\]\[\d+\]\[\d+\]\[\d+\]\[(\d+)\]$")


def _season_findings(seasons_seen):
    """The engine's effective_season table wastes some counts. Say so.

    obj/gebaeude.cc indexes effective_season[seasons-1][...], and the row for
    THREE images is a byte-for-byte copy of the row for two. A third season image
    is therefore never drawn - the artist's work is simply thrown away, and
    makeobj does not say a word.
    """
    out = []
    for line, count in sorted(seasons_seen.items()):
        if count == 3:
            out.append(Finding("warning", line,
                               "3 season images: the engine NEVER draws the third "
                               "(obj/gebaeude.cc effective_season - the row for 3 "
                               "is a copy of the row for 2). Use 2 (all-year + "
                               "snow) or 4/5 (the real seasons).", code="season-waste"))
        elif count > 5:
            out.append(Finding("error", line,
                               "%d season images, but the engine's table only goes "
                               "up to 5" % count, code="season-count"))
    return out


# NO ICON, NO TOOL, NO OBJECT.
#
# Every one of these registers its build tool behind the same line - the wording
# is identical in all five files:
#
#     if( desc->get_cursor()->get_image_id(1) != IMG_EMPTY ) { ...make the tool... }
#     else                                                   { desc->set_builder(NULL); }
#
#     builder/wegbauer.cc:123      obj/wayobj.cc:558      obj/roadsign.cc:753
#     builder/brueckenbauer.cc     builder/tunnelbauer.cc
#
# Image 1 of the cursor skin is the icon. Leave it out and the object still loads,
# still shows up in the pakset, still passes makeobj without a murmur - and has no
# button, appears in no list, and CANNOT BE BUILT BY ANYONE. It is the quietest
# way to ship an object that does not exist.
NEEDS_ICON = ("way", "way-object", "roadsign", "bridge", "tunnel")


# The only waytype spellings the engine accepts - descriptor/writer/get_waytype.cc,
# which ends with
#
#     dbg->fatal("get_waytype()", "invalid waytype \"%s\"\n", waytype);
#
# so this one is not a silent failure, it is a dead build. Worth catching before you
# start makeobj rather than after: the names are not the obvious ones. It is
# monorail_track, not monorail. tram_track, not tram. And "electrified_track" is
# what catenary GRANTS, spelled quite unlike anything else in the list.
WAYTYPES = ("none", "road", "track", "electrified_track", "maglev_track",
            "monorail_track", "narrowgauge_track", "water", "air",
            "schiene_tram", "tram_track", "power", "decoration")
WAYTYPE_KEYS = ("waytype", "own_waytype")

# The readers that run the value through atoi() - i.e. the key is a NUMBER.
# get_koord/get_color/get_ints parse several numbers with their own grammar, so
# they are deliberately left out of this simple "is it one integer?" check.
_INT_READERS = ("get_int", "get_int64", "get_int_clamped")

# atoi's idea of an integer: optional surrounding space, optional sign, digits.
_INTEGER = re.compile(r"[+-]?\d+\Z")


def _atoi(text):
    """What the engine's atoi() would make of this string. Never raises."""
    m = re.match(r"\s*([+-]?\d+)", text)
    return int(m.group(1)) if m else 0


def _icon_findings(icon_blocks):
    """[[obj_type, line of the obj= key, saw an icon?], ...] -> [Finding].

    ONE ENTRY PER OBJECT, not per type. This was keyed by obj_type, so two
    obj=way in one file shared a slot: give the first an icon and the second, with
    none, inherited it and its missing-icon error vanished. A .dat routinely holds
    several ways, and the second unbuildable one is exactly the one you would miss.
    """
    out = []
    for obj_type, line, has_icon in icon_blocks:
        if obj_type in NEEDS_ICON and not has_icon:
            out.append(Finding("error", line,
                               "obj=%s with no icon=. The engine only builds a tool "
                               "for it if the icon exists, so it will load, take up "
                               "space, and be IMPOSSIBLE TO BUILD - no button, no "
                               "list, nothing. makeobj will not warn you." % obj_type, code="no-icon"))
    return out


def _comment_findings(obj_type, keys, value, line):
    """A '#' after a value. Whether that is fatal depends on WHO reads the value.

    tabfile drops a line only when it STARTS with '#' (tabfile.cc read_line), so a
    '#' further along is part of the value, always. What differs is what happens to
    it next:

      * A TEXT value keeps it. `freight=None  # a note` really does set freight to
        "None  # a note", and the pakset loader dies with
        "Cannot resolve 'GOOD-None  # a note'". This one cost us an evening.

      * A NUMBER swallows it, because atoi() stops at the first non-digit. Sloppy,
        harmless, and not worth a word from a linter.

      * An IMAGE reference is EXPLICITLY allowed to have one. image_writer.cc:340,
        the engine's own comment: "after the dots also spaces and comments are
        allowed". pak128's menu files are full of them, on purpose.

    Our first version called all three an error, and reported 97 of them on pak128 -
    every single one a false alarm. A linter that cries wolf gets turned off.
    """
    if "#" not in value:
        return []
    readers = {reader_of(obj_type, k) for k in keys}
    if not any(r in _TEXT_READERS for r in readers):
        return []                      # a number, or an image: the engine copes
    return [Finding("error", line,
                    "end-of-line comment: a .dat has none. The engine reads %r as "
                    "TEXT, so its value becomes %r - comment and all - and the "
                    "pakset loader will fail to resolve it. Put the comment on its "
                    "own line. (An image reference may have one; text may not.)"
                    % (keys[0], value.strip()), code="value-comment")]


# --- coupling chains --------------------------------------------------------
#
# Vehicles in a forced chain (a Constraint[Next] naming exactly one successor) that
# do not share a length need their ART drawn off-centre, or the joint between them
# opens - see core/convoy.py, which has the arithmetic and the measurement.
#
# THIS IS NOT A LINTER RULE, and it was nearly one. A .dat cannot tell you where the
# artist put the ink inside the cell, so "different lengths" is not a defect: it is a
# question the .dat cannot answer. Run it as a warning and it fires on 56 vehicles of
# pak128 - the articulated trolleybuses, the trams, every steam engine and tender -
# all of which are correct, because their authors did compensate. So it lives in
# tools/lint_dat.py as an opt-in REPORT that hands you the offset to use, and the
# linter itself stays quiet.
_LENGTH_DEFAULT = 8              # vehicle_writer.cc:166  obj.get_int("length", 8)

_CONSTRAINT = re.compile(r"^constraint\[(prev|next)\]\[(\d+)\]$")


class Vehicle:
    """One obj=vehicle, reduced to what a coupling check needs."""

    def __init__(self, line, path=None):
        self.line = line             # the obj=vehicle line
        self.path = path
        self.name = None
        self.length = _LENGTH_DEFAULT
        self.length_line = line      # where to point when the length is the problem
        self.next = []               # concrete successors, 'none' dropped
        self.next_line = line


def vehicles_in(text, path=None):
    """-> [Vehicle], one per obj=vehicle block in a .dat."""
    out = []
    v = None
    for n, raw in enumerate(text.splitlines(), 1):
        if raw.startswith("#") or not raw.strip() or raw[0] in " \t":
            continue
        if raw.lstrip().startswith("-"):
            v = None
            continue
        if "=" not in raw:
            continue

        key, value = raw.split("=", 1)
        key = re.sub(r"\s+(?=[^\[]*\])", "", key.strip().lower())
        value = value.strip()

        if key == "obj":
            v = Vehicle(n, path) if value.lower() == "vehicle" else None
            if v is not None:
                out.append(v)
            continue
        if v is None:
            continue

        if key == "name":
            v.name = value
        elif key == "length":
            try:
                v.length = int(value.split()[0])
            except (ValueError, IndexError):
                pass                 # not our job: the value is read by atoi anyway
            v.length_line = n
        else:
            m = _CONSTRAINT.match(key)
            if m and m.group(1) == "next" and value.lower() != "none":
                v.next.append(value)
                v.next_line = n
    return out


def chains(vehicles):
    """Follow every forced chain to its end. -> [[Vehicle, ...]]

    A forced chain is what the depot auto-completes: tool/simtool.cc case 'a' keeps
    appending while a vehicle's Constraint[Next] names exactly ONE real successor,
    which is how a fixed unit is built from one click. A vehicle that may take many
    followers ends the chain - what comes next is then the player's choice, not the
    artist's, and nothing about it can be checked ahead of time.
    """
    by_name = {v.name: v for v in vehicles if v.name}
    successor = {}
    has_forced_leader = set()
    for v in vehicles:
        if len(v.next) == 1 and v.next[0] in by_name:
            successor[v.name] = by_name[v.next[0]]
            has_forced_leader.add(v.next[0])

    out = []
    for v in vehicles:
        if not v.name or v.name in has_forced_leader or v.name not in successor:
            continue                          # not the head of a forced chain
        chain, seen = [v], {v.name}
        while chain[-1].name in successor:
            nxt = successor[chain[-1].name]
            if nxt.name in seen:              # a ring; stop rather than spin
                break
            seen.add(nxt.name)
            chain.append(nxt)
        out.append(chain)
    return out


def lint_files(files):
    """Lint each file. files: [(path, text)] -> [Finding], each with .path set."""
    out = []
    for path, text in files:
        for f in lint(text):
            f.path = path
            out.append(f)
    return out


# A file-level opt-out. `# bkit: ignore=no-icon, dup-key` anywhere in the file
# silences those rule codes for the whole file - the "I know, stop telling me"
# escape a linter needs so people do not turn the whole thing off over one finding.
# File-level rather than per-line because a .dat cannot carry a trailing comment on
# most of its lines (that is itself a rule), so there is nowhere to hang a per-line
# pragma without inventing a second comment syntax.
_SUPPRESS = re.compile(r"#\s*bkit:\s*ignore\s*=\s*([\w\-, ]+)", re.I)


def _suppressed_codes(text):
    codes = set()
    for m in _SUPPRESS.finditer(text):
        codes.update(c.strip() for c in m.group(1).split(",") if c.strip())
    return codes


def lint(text):
    """-> [Finding]. level is 'error' (the game will misbehave) or 'warning'."""
    out = []
    obj_type = None
    seasons = {}          # {first line of the group: how many season images}
    icon_blocks = []      # one [obj_type, obj= line, saw an icon?] PER OBJECT
    unknown_types = {}    # {bad obj= value: [first line, how many]}
    seen = {}             # {key: (line, value)} for THIS object - see below

    for n, raw in enumerate(text.splitlines(), 1):
        if raw.startswith("#") or not raw.strip():
            continue

        if raw.lstrip().startswith("-") and not raw.startswith(" "):
            obj_type = None                       # object separator
            seen = {}
            continue

        # tabfile.cc:523 - a line starting with a space is thrown away, silently
        if raw[0] in " \t" and "=" in raw:
            out.append(Finding("error", n,
                               "indented line: the engine DROPS any line starting "
                               "with a space, so this key is silently ignored. "
                               "Move it to column 0.", code="dropped-indent"))
            continue

        if "=" not in raw:
            continue

        key, value = raw.split("=", 1)
        # format_key(): trim the right, lowercase, and drop spaces inside brackets
        key = re.sub(r"\s+(?=[^\[]*\])", "", key.strip().lower())

        if key == "obj":
            seen = {}
            obj_type = value.strip().lower()
            if obj_type not in OBJ_TYPES:
                # one finding per unknown type per file, not one per object: a text
                # file full of them is one mistake, not twenty-four
                #
                # NOT `seen`, which is the duplicate-key dict two lines up. Binding a
                # list to that name left the dict shadowed until the next obj=, and
                # `key in [line, count]` is a perfectly legal question with a useless
                # answer - so it would not have crashed, it would have lied.
                tally = unknown_types.setdefault(obj_type, [n, 0])
                tally[1] += 1
                obj_type = None
            elif not OBJ_TYPES[obj_type]["top_level"]:
                out.append(Finding("error", n, "obj=%s is an internal writer, not "
                                   "something a .dat may declare" % obj_type, code="internal-obj"))
                obj_type = None
            else:
                icon_blocks.append([obj_type, n, False])
            continue

        if obj_type is None:
            continue                              # no type yet, or an unknown one

        # A KEY SAID TWICE IS A KEY SAID ONCE. tabfileobj_t::put() (tabfile.cc:74)
        # keeps the FIRST value and drops the second on the floor:
        #
        #     if(objinfo.get(key).str) { return false; }    <- already there: give up
        #
        # so the second line is dead text. Nothing reads it, makeobj says nothing, and
        # if you go back and edit it - which is the natural thing to do - the object
        # does not change and you have no idea why.
        #
        # It is not academic: pak128's own horses.dat says waytype=road on line 10 and
        # waytype=bio on line 16. `bio` is not a waytype (get_waytype.cc fatals on
        # anything it does not know) and the horses work perfectly, because the engine
        # never sees that line. We called it an error, and had to be shown otherwise by
        # makeobj: it compiles horses.dat with exit 0.
        #
        # So a repeated key is reported HERE, once, as what it is - a dead line - and
        # its value is NOT validated, because the engine will not read it either.
        dup_keys = [k for k in expand_key(key) if k in seen]
        if dup_keys:
            first_line, first_value = seen[dup_keys[0]]
            out.append(Finding("warning", n,
                               "%r is already set on line %d (=%r). The engine keeps "
                               "the FIRST value and silently ignores this one "
                               "(tabfile.cc put()), so this line does nothing - "
                               "including if you edit it."
                               % (dup_keys[0], first_line, first_value), code="dup-key"))
            continue
        for k in expand_key(key):
            seen[k] = (n, value.strip())

        if key == "icon" and value.strip() and icon_blocks:
            icon_blocks[-1][2] = True          # THIS object saw its icon

        if key in WAYTYPE_KEYS:
            got = value.strip().lower()
            if got and got not in WAYTYPES:
                out.append(Finding("error", n,
                                   "%s=%s is not a waytype the engine knows, and "
                                   "get_waytype() does not shrug it off - it calls "
                                   "dbg->fatal() and makeobj dies. It knows: %s"
                                   % (key, got, ", ".join(WAYTYPES)), code="bad-waytype"))

        # A KEY THE ENGINE READS AS A NUMBER, GIVEN SOMETHING THAT IS NOT ONE.
        #
        # obj.get_int() is atoi(get(key)), and atoi reads an optional sign and then
        # digits, STOPPING at the first thing that is not one - it never fails, it
        # just returns 0 or a prefix. So power=abc is silently power 0, cost=1,000 is
        # silently cost 1, level=2.5 is silently level 2, and makeobj says nothing.
        # The schema already knows which keys are read this way; validate them.
        if reader_of(obj_type, key) in _INT_READERS:
            val = value.split("#")[0].strip()
            if val and not _INTEGER.match(val):
                reads = _atoi(val)
                out.append(Finding("error", n,
                                   "%s=%s is not an integer. The engine reads it with "
                                   "atoi(), which stops at the first non-digit and "
                                   "would take this as %d - silently. makeobj will not "
                                   "warn." % (key, val, reads), code="bad-int"))

        # A key can stand for a whole family: image[n,e,s,w][0-1] is eight of them.
        keys = expand_key(key)

        out.extend(_comment_findings(obj_type, keys, value, n))

        for k in keys:
            m = _SEASON_KEY.match(k)
            if m:
                # count the season images of this object; report on the first line
                first = min(seasons.keys()) if seasons else n
                seasons[first] = max(seasons.get(first, 0), int(m.group(1)) + 1)

        unknown = [k for k in keys if not known_key(obj_type, k)]
        if unknown:
            others = types_reading(unknown[0])
            hint = (" - it belongs to obj=%s" % ", obj=".join(others)) if others else ""
            shown = key if len(keys) == 1 else "%s (e.g. %s)" % (key, unknown[0])
            out.append(Finding("warning", n,
                               "obj=%s does not read %r%s. makeobj will ignore it."
                               % (obj_type, shown, hint), code="unknown-key"))

    for bad, (line, count) in unknown_types.items():
        more = "" if count == 1 else " (%d objects in this file)" % count
        out.append(Finding("error", line,
                           "unknown obj type %r%s. makeobj does not FAIL on this - "
                           "obj_writer.cc prints 'Skipping unknown %s object ...' and "
                           "moves on - so a typo here does not break the build, it "
                           "just quietly leaves the object out of the pakset. The "
                           "engine knows: %s"
                           % (bad, more, bad, ", ".join(TOP_LEVEL)), code="unknown-obj"))

    out.extend(_season_findings(seasons))
    out.extend(_icon_findings(icon_blocks))

    suppressed = _suppressed_codes(text)
    if suppressed:
        out = [f for f in out if f.code not in suppressed]

    out.sort(key=lambda f: f.line)
    return out
