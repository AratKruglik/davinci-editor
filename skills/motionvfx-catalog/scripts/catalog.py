"""Catalog of installed Fusion templates (MotionVFX and others): titles, transitions, effects, generators.

scan:   python3 catalog.py scan --out catalog.json [--dir EXTRA_TEMPLATES_DIR ...]
search: python3 catalog.py search catalog.json [--category Titles] [--vendor MotionVFX] [--text-inputs 1] QUERY WORDS...

Reads .drfx bundles (zip) and loose .setting files under Fusion/Templates. Never modifies them.
"""
import argparse
import json
import os
import re
import zipfile

DEFAULT_DIRS = [
    os.path.expanduser("~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Templates"),
    "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Templates",
]
CATEGORIES = {"Titles", "Transitions", "Effects", "Generators"}
FIELD = re.compile(r'(\w+)\s*=\s*"([^"]*)"')
TOP_TOOL = re.compile(r"^\s*(\w+)\s*=\s*(MacroOperator|GroupOperator)\s*\{", re.M)


def blocks(text, marker):
    """Bodies of `<id> = <marker> { ... }` blocks, brace-matched."""
    for m in re.finditer(r"(\w+)\s*=\s*" + marker + r"\s*\{", text):
        depth, i = 1, m.end()
        while depth and i < len(text):
            depth += {"{": 1, "}": -1}.get(text[i], 0)
            i += 1
        yield m.group(1), text[m.end():i - 1]


def parse_setting(text):
    inputs, text_inputs = [], 0
    for input_id, body in blocks(text, "InstanceInput"):
        fields = dict(FIELD.findall(body))
        if fields.get("Source") == "StyledText":
            text_inputs += 1
        name = fields.get("Name")
        if name and not input_id.startswith("Label"):
            inputs.append(name)
    top = TOP_TOOL.search(text)
    return {"macro": top.group(1) if top else None, "text_inputs": text_inputs, "inputs": list(dict.fromkeys(inputs))[:40]}


def entry(rel_path, text, source):
    parts = rel_path.replace("\\", "/").split("/")
    if "Edit" in parts:
        parts = parts[parts.index("Edit") + 1:]
    if not parts or parts[0] not in CATEGORIES:
        return None
    folders = parts[1:-1]
    return {"name": os.path.splitext(parts[-1])[0], "category": parts[0], "vendor": folders[0] if folders else "",
            "pack": "/".join(folders[1:]), "source": source, "path": rel_path, **parse_setting(text)}


def scan(dirs):
    items, errors = [], []
    for root in dirs:
        if not os.path.isdir(root):
            continue
        for folder, _, files in os.walk(root):
            for name in sorted(files):
                path = os.path.join(folder, name)
                try:
                    if name.endswith(".drfx"):
                        with zipfile.ZipFile(path) as z:
                            for member in z.namelist():
                                if member.endswith(".setting") and not member.startswith("__MACOSX"):
                                    e = entry(member, z.read(member).decode("utf-8", "replace"), path)
                                    if e:
                                        items.append(e)
                    elif name.endswith(".setting"):
                        with open(path, encoding="utf-8", errors="replace") as f:
                            e = entry(os.path.relpath(path, root), f.read(), path)
                        if e:
                            items.append(e)
                except (zipfile.BadZipFile, OSError) as exc:
                    errors.append({"file": path, "error": str(exc)})
    return {"items": items, "errors": errors}


def summary(catalog):
    counts = {}
    for it in catalog["items"]:
        key = f'{it["vendor"] or "-"} / {it["category"]}'
        counts[key] = counts.get(key, 0) + 1
    return {"total": len(catalog["items"]), "by_vendor_category": dict(sorted(counts.items())), "errors": catalog["errors"]}


def search(catalog, words, category=None, vendor=None, text_inputs=None, limit=15):
    words = [w.lower() for w in words]
    scored = []
    for it in catalog["items"]:
        if category and it["category"].lower() != category.lower():
            continue
        if vendor and vendor.lower() not in it["vendor"].lower():
            continue
        if text_inputs is not None and it["text_inputs"] < text_inputs:
            continue
        hay = " ".join([it["name"], it["pack"], it["vendor"], " ".join(it["inputs"])]).lower()
        score = sum(hay.count(w) * (3 if w in it["name"].lower() else 1) for w in words) if words else 1
        if score:
            scored.append((score, it))
    scored.sort(key=lambda s: (-s[0], s[1]["name"]))
    keep = ("name", "category", "vendor", "pack", "text_inputs")
    return [dict({k: it[k] for k in keep}, inputs=it["inputs"][:8], score=score) for score, it in scored[:limit]]


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="mode", required=True)
    s = sub.add_parser("scan")
    s.add_argument("--out", required=True)
    s.add_argument("--dir", action="append", default=[])
    q = sub.add_parser("search")
    q.add_argument("catalog")
    q.add_argument("words", nargs="*")
    q.add_argument("--category")
    q.add_argument("--vendor")
    q.add_argument("--text-inputs", type=int)
    q.add_argument("--limit", type=int, default=15)
    a = p.parse_args()
    if a.mode == "scan":
        catalog = scan(DEFAULT_DIRS + a.dir)
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(catalog, f, ensure_ascii=False, indent=1)
        print(json.dumps(summary(catalog), ensure_ascii=False, indent=1))
    else:
        with open(a.catalog, encoding="utf-8") as f:
            catalog = json.load(f)
        print(json.dumps(search(catalog, a.words, a.category, a.vendor, a.text_inputs, a.limit), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
