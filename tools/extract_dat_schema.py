"""Read the .dat schema out of the engine's own source.

    python tools/extract_dat_schema.py [path-to-simutrans] > core/dat_schema.json

There is no schema document for .dat files. The authority is the C++ that reads
them: src/simutrans/descriptor/writer/*.cc. Every key is a literal in a call like

    obj.get_int("payload", 0)
    obj.get("weight")
    obj.get_int_clamped("loading_time", 1000, 0, 0x7FFFFFFF)

and every object type names itself in its header:

    const char *get_type_name() const OVERRIDE { return "vehicle"; }

So we do not hand-maintain a key list that drifts away from the engine on the
next commit - we take it FROM the engine, and a test re-extracts it and fails if
what we shipped no longer matches the source.

Two things the source makes awkward, handled explicitly:

  * Image keys are built at runtime - sprintf(buf, "emptyimage[%s]", dir) - so
    they are not literals. We capture the FORMAT STRINGS instead and keep them as
    patterns. Over-approximating here is the safe direction: a linter that knows
    about too many keys stays quiet, one that knows too few cries wolf.

  * Keys are case-insensitive. tabfile.cc lowercases every key it reads
    (tabfile.cc:856), which is why `EmptyImage[s]` matches `emptyimage[%s]`.
    Everything below is stored lowercase.
"""

import json
import os
import re
import sys

# obj.get(...) / obj.get_int(...) / obj.get_int64(...) / ...
# longest alternatives first, or get_int would swallow get_int64
_READ = re.compile(
    r"obj\.get(_int64|_int_clamped|_ints|_int|_koord|_color|_string)?\s*\(\s*"
    r'"([^"]+)"\s*(?:,\s*([^,()]+?)\s*[,)])?')

# sprintf(buf, "emptyimage[%s]", ...) - a key built at runtime
_FORMAT = re.compile(r'sn?printf\s*\(\s*\w+\s*,\s*"([^"]+)"')

_TYPE_NAME = re.compile(r'get_type_name\(\)[^{]*\{\s*return\s+"([^"]+)"')
_REGISTER = re.compile(r"register_writer\(\s*(true|false)\s*\)")
_CLASS = re.compile(r"^class\s+(\w+)\s*:", re.M)

# ONE WRITER HANDS THE WHOLE .dat OBJECT TO ANOTHER, and that other one then reads
# its own keys out of it:
#
#     factory_writer.cc:225   building_writer_t::instance()->write_obj(fp, node, obj);
#
# So obj=factory reads every key obj=building reads - dims, level, the whole
# BackImage grid, all of it. Miss this and the linter cries wolf on every factory
# in the pakset: it did, 1622 times, the first time we ran it against pak128.
#
# The tell is the bare `obj` argument. imagelist_writer_t::write_obj(fp, node, keys)
# gets a key list, not the tabfileobj, and delegates nothing.
_DELEGATE = re.compile(r"(\w+)_writer_t::instance\(\)\s*->\s*write_obj\s*\("
                       r"[^;]*?,\s*obj\s*[,)]")


def writer_classes(htext):
    """[(class_prefix, type_name, top_level)] for EVERY writer class in a header.

    One header declares several: building_writer.h has both "tile" and
    "building", and factory_writer.h has six. Reading only the first match lost
    exactly the types that matter most - buildings and factories - so split the
    file into class blocks and read each one.

    The class prefix is what a delegation names (building_writer_t -> "building");
    the type name is what a .dat says (obj=building). They are usually the same and
    sometimes are not: way_obj_writer_t declares obj=way-object.
    """
    hits = list(_CLASS.finditer(htext))
    bounds = [m.start() for m in hits] + [len(htext)]
    out = []
    for i, m in enumerate(hits):
        block = htext[bounds[i]:bounds[i + 1]]
        name = _TYPE_NAME.search(block)
        if not name:
            continue                      # abstract writer: no obj= of its own
        reg = _REGISTER.search(block)
        prefix = re.sub(r"_writer_t$", "", m.group(1)).lower()
        out.append((prefix, name.group(1).lower(),
                    bool(reg and reg.group(1) == "true")))
    return out


def _writer_dir(src):
    return os.path.join(src, "src", "simutrans", "descriptor", "writer")


def _read(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def keys_in(text):
    """{key: {reader, default}} for every literal key the writer reads."""
    out = {}
    for reader, key, default in _READ.findall(text):
        k = key.lower()
        entry = out.setdefault(k, {"reader": "get" + (reader or ""), "default": None})
        if default and entry["default"] is None:
            entry["default"] = default.strip()
    return out


# A KEY WRITTEN OUT AS A LITERAL, e.g. "smoketile[0]" or "openimage[ns]".
#
# Not every key reaches obj.get() as a string literal, and not every one is built
# with sprintf. factory_writer.cc:291 does neither - it declares a char BUFFER and
# then pokes at it:
#
#     char str_smoketile[] = "smoketile[0]";
#     ...
#     str_smoketile[10] = '0' + i;                       // <- the key changes here
#     pos_off[i] = obj.get_koord( str_smoketile, koord(0,0) );
#
# No regex over `obj.get("...")` will ever see that, and no regex over sprintf will
# either. The literal in the initialiser is the ONLY trace the key leaves, so that
# is what we harvest.
#
# This one mattered. Without it the linter reported all thirteen of pak128's smoking
# factories as writing a key the engine ignores - and they are correct, and makeobj
# reads all four of smoketile[0..3]. We very nearly published that as a pakset bug.
_KEY_LITERAL = re.compile(r'"([a-z_]+\[[a-z0-9_,]+\])"')


def _generalise(literal):
    """'smoketile[0]' -> 'smoketile[%d]'. The writer that pokes a digit into the
    buffer walks it upward, so the whole family is a key, not just the zeroth."""
    return re.sub(r"\[\d+\]", "[%d]", literal)


def patterns_in(text):
    """Key FORMATS the writer builds at runtime. Only the ones that look like keys."""
    out = {f.lower() for f in _FORMAT.findall(text) if "[" in f}

    literals = sorted({m.lower() for m in _KEY_LITERAL.findall(text)})

    # keys spelled out in a literal, in whatever way the writer then uses them
    out.update(_generalise(lit) for lit in literals)

    # a format whose FIRST conversion is %s is being handed a key prefix; pair it
    # with the prefixes this writer actually has, rather than letting %s match
    # anything at all (crossing_writer.cc:28: sprintf(buf, "%s[%i]", key, i))
    for fmt in list(out):
        if fmt.startswith("%s") and literals:
            out.update(lit + fmt[2:] for lit in literals)

    return sorted(out)


def delegates_in(text):
    """Which other writers this one hands the whole .dat object to."""
    return sorted({m.lower() for m in _DELEGATE.findall(text)})


def _resolve_delegates(types, by_writer_class):
    """Fold each writer's delegated keys and patterns into its own.

    Depth-first with a visiting set, because the graph is a graph: nothing in the
    engine stops two writers delegating to each other, and a plain recursion would
    simply hang instead of telling us.
    """
    done, visiting = {}, set()

    def resolve(name):
        if name in done:
            return done[name]
        if name in visiting:
            return ({}, [])                 # a cycle: stop, do not spin
        visiting.add(name)

        t = types[name]
        keys = dict(t["keys"])
        patterns = list(t["patterns"])
        for cls in t["delegates_to"]:
            target = by_writer_class.get(cls)
            if target is None or target not in types:
                continue                    # not a .dat-level writer (imagelist, xref)
            dkeys, dpatterns = resolve(target)
            for k, v in dkeys.items():
                keys.setdefault(k, v)
            patterns.extend(p for p in dpatterns if p not in patterns)

        visiting.discard(name)
        done[name] = (keys, sorted(patterns))
        return done[name]

    for name in types:
        keys, patterns = resolve(name)
        types[name]["keys"] = keys
        types[name]["patterns"] = patterns


def extract(src):
    wdir = _writer_dir(src)
    if not os.path.isdir(wdir):
        raise SystemExit("no writers at %s - is that a Simutrans checkout?" % wdir)

    version = "unknown"
    m = re.search(r'#define\s+SIM_VERSION_(?:MAJOR|MINOR)\s+(\d+)',
                  _read(os.path.join(src, "src", "simutrans", "simversion.h")))
    if m:
        vt = _read(os.path.join(src, "src", "simutrans", "simversion.h"))
        nums = re.findall(r"#define\s+SIM_VERSION_\w+\s+(\d+)", vt)
        version = ".".join(nums[:3])

    # obj_writer.cc holds what EVERY object reads (name, copyright, ...)
    common = keys_in(_read(os.path.join(wdir, "obj_writer.cc")))

    types = {}
    by_writer_class = {}
    for header in sorted(f for f in os.listdir(wdir) if f.endswith(".h")):
        htext = _read(os.path.join(wdir, header))
        source = header[:-2] + ".cc"
        cc = os.path.join(wdir, source)
        text = _read(cc) if os.path.exists(cc) else ""

        # Several writer classes can share a .cc, and there is no honest way to
        # tell from the source which of them reads which key. So each type gets
        # the whole file's keys. For a linter that is the safe direction:
        # slightly too permissive, never a false alarm.
        for prefix, name, top_level in writer_classes(htext):
            by_writer_class[prefix] = name
            types[name] = {
                "writer": source,
                "top_level": top_level,
                "keys": keys_in(text),
                "patterns": patterns_in(text),
                "delegates_to": delegates_in(text),
            }

    _resolve_delegates(types, by_writer_class)

    return {
        "_comment": "GENERATED by tools/extract_dat_schema.py - do not hand-edit. "
                    "Regenerate when the engine changes; tests/test_schema_drift.py "
                    "fails if this and the engine source disagree.",
        "engine_version": version,
        "common_keys": common,
        "obj_types": types,
    }


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "simutrans")
    schema = extract(os.path.abspath(src))
    json.dump(schema, sys.stdout, indent=1, sort_keys=True)
    print()
    n = sum(len(t["keys"]) for t in schema["obj_types"].values())
    print("%d object types, %d keys, engine %s"
          % (len(schema["obj_types"]), n, schema["engine_version"]), file=sys.stderr)


if __name__ == "__main__":
    main()
