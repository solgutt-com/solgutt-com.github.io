"""
build.py — generates data.js from Images/Collections/ folder structure.

Usage:
  python3 build.py  — rebuild data.js

Captions: set per-gallery in collections.json under "captions": {"filename.jpg": "My caption"}
Photo order: set per-gallery in collections.json under "photo_order": ["file1.jpg", "file2.jpg"]
Both fields are optional; defaults are cleaned filenames and alphabetical order.
"""

import os, json, unicodedata

def nfc(s):
    return unicodedata.normalize('NFC', s)

COLLECTIONS_ROOT = "Images/Collections"
OUTPUT_PATH      = "data.js"
IMAGE_EXTENSIONS = {'.jpeg', '.jpg', '.png', '.webp'}

GALLERY_NAMES = {
    "AL": "Albania",       "AT": "Austria",        "BA": "Bosnia & Herzegovina",
    "BE": "Belgium",       "CH": "Switzerland",     "DE": "Germany",
    "EE": "Estonia",       "ES": "Spain",           "FI": "Finland",
    "FR": "France",        "HR": "Croatia",         "IT": "Italy",
    "LT": "Lithuania",     "LV": "Latvia",          "LX": "Luxembourg",
    "ME": "Montenegro",    "NL": "Netherlands",     "PL": "Poland",
    "PT": "Portugal",      "SE": "Sweden",          "SI": "Slovenia",
    "TheJungle": "The Jungle", "XX": "Somewhere",
    "ZA": "South Africa",  "ZW": "Zimbabwe",
}


def clean_caption(filename):
    name = os.path.splitext(filename)[0]
    for prefix in ("SolGutt - ", "SolGutt-"):
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
    parts = name.split('_', 1)
    if len(parts) == 2 and parts[0].isupper() and len(parts[0]) <= 3:
        name = parts[1]
    name = name.replace('_', ' ').replace('-', ' ')
    name = ' '.join(w for w in name.split() if w.lower() != 'large')
    return name


def read_meta(folder_path):
    path = os.path.join(folder_path, "collections.json")
    if not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            print(f"Warning: invalid JSON in {path}")
            return {}


def _list_images(directory):
    if not os.path.isdir(directory):
        return []
    return sorted(nfc(f) for f in os.listdir(directory) if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS)


def _make_node(folder_name, meta, coll_type, site_rel_path):
    return {
        "id":          folder_name,
        "title":       meta.get("title") or GALLERY_NAMES.get(folder_name, folder_name),
        "subtitle":    meta.get("subtitle", ""),
        "description": meta.get("description", ""),
        "cover":       meta.get("cover", ""),
        "order":       meta.get("order", 999),
        "type":        coll_type,
        "path":        site_rel_path,
    }


def scan_photos(photos_dir, site_rel_path, meta):
    """Return [{src, caption}] using photo_order and captions from meta."""
    captions    = meta.get("captions", {})
    photo_order = meta.get("photo_order")
    all_imgs    = _list_images(photos_dir)

    if photo_order:
        ordered = [f for f in photo_order if f in all_imgs]
        ordered += [f for f in all_imgs if f not in ordered]
    else:
        ordered = all_imgs

    return [
        {
            "src":     site_rel_path + "/" + f,
            "caption": captions.get(f, clean_caption(f))
        }
        for f in ordered
    ]


def scan_leaf_gallery(folder_path, site_rel_path):
    """Scan a country-code folder whose images sit directly inside (no Photos/ subdir)."""
    folder_name = os.path.basename(folder_path)
    meta        = read_meta(folder_path)
    node        = _make_node(folder_name, meta, "gallery", site_rel_path)
    node["photos"] = scan_photos(folder_path, site_rel_path, meta)
    return node


def scan_collection(folder_path, site_rel_path):
    """Recursively build a collection node from folder_path."""
    folder_name = os.path.basename(folder_path)
    meta        = read_meta(folder_path)
    coll_type   = meta.get("type", "gallery")
    node        = _make_node(folder_name, meta, coll_type, site_rel_path)

    if coll_type == "parent":
        children = []

        sub_dir = os.path.join(folder_path, "sub")
        if os.path.isdir(sub_dir):
            for name in sorted(os.listdir(sub_dir)):
                child_path = os.path.join(sub_dir, name)
                if os.path.isdir(child_path):
                    children.append(scan_collection(child_path, site_rel_path + "/sub/" + name))

        photos_dir = os.path.join(folder_path, "Photos")
        if os.path.isdir(photos_dir):
            for name in sorted(os.listdir(photos_dir)):
                child_path = os.path.join(photos_dir, name)
                if os.path.isdir(child_path):
                    children.append(scan_leaf_gallery(child_path, site_rel_path + "/Photos/" + name))

        children.sort(key=lambda x: (x["order"], x["id"]))
        node["children"] = children

    elif coll_type == "gallery":
        photos_dir = os.path.join(folder_path, "Photos")
        node["photos"] = scan_photos(photos_dir, site_rel_path + "/Photos", meta)

    return node


def flatten(node, parent_id=None):
    """Convert a nested tree node into a flat list of nodes with a parent field."""
    entry = {k: v for k, v in node.items() if k != "children"}
    entry["parent"] = parent_id
    result = [entry]
    for child in node.get("children", []):
        result.extend(flatten(child, node["id"]))
    return result


def build_data_js():
    root             = os.path.dirname(os.path.abspath(__file__))
    collections_path = os.path.join(root, COLLECTIONS_ROOT)

    if not os.path.isdir(collections_path):
        print(f"Error: {COLLECTIONS_ROOT} not found")
        return

    trees = []
    for name in sorted(os.listdir(collections_path)):
        folder_path = os.path.join(collections_path, name)
        if os.path.isdir(folder_path):
            trees.append(scan_collection(folder_path, COLLECTIONS_ROOT + "/" + name))
    trees.sort(key=lambda x: (x["order"], x["id"]))

    all_nodes = []
    for tree in trees:
        all_nodes.extend(flatten(tree))

    output_path = os.path.join(root, OUTPUT_PATH)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("// Auto-generated by build.py — do not edit manually\n\n")
        f.write("const collections = ")
        f.write(json.dumps(all_nodes, indent=2, ensure_ascii=False))
        f.write(";\n")

    galleries    = [n for n in all_nodes if n["type"] == "gallery"]
    total_photos = sum(len(n.get("photos", [])) for n in galleries)
    print("─────────────────────────────────")
    print("data.js rebuilt successfully")
    print(f"Top-level collections : {len(trees)}")
    print(f"Total galleries       : {len(galleries)}")
    print(f"Total photos indexed  : {total_photos}")
    print("─────────────────────────────────")


if __name__ == '__main__':
    build_data_js()
