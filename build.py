"""
build.py — generates data.js from Images/Collections/ folder structure.

Usage:
  python3 build.py           — rebuild data.js
  python3 build.py captions  — regenerate/update captions.json stubs
"""

import os, json, sys

COLLECTIONS_ROOT = "Images/Collections"
OUTPUT_PATH = "data.js"
CAPTIONS_PATH = "captions.json"
IMAGE_EXTENSIONS = {'.jpeg', '.jpg', '.png', '.webp'}

# Display names for leaf galleries that have no collections.json
GALLERY_NAMES = {
    "AL": "Albania",       "AT": "Austria",        "BA": "Bosnia & Herzegovina",
    "BE": "Belgium",       "BW": "Black & White",  "CH": "Switzerland",
    "DE": "Germany",       "EE": "Estonia",         "ES": "Spain",
    "FI": "Finland",       "FR": "France",          "Highlights": "Highlights",
    "HR": "Croatia",       "IT": "Italy",           "LT": "Lithuania",
    "LV": "Latvia",        "LX": "Luxembourg",      "ME": "Montenegro",
    "NL": "Netherlands",   "PL": "Poland",          "PT": "Portugal",
    "SE": "Sweden",        "SI": "Slovenia",        "TheJungle": "The Jungle",
    "XX": "Somewhere",     "ZA": "South Africa",    "ZW": "Zimbabwe",
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


def load_captions(root):
    path = os.path.join(root, CAPTIONS_PATH)
    if not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


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
    return sorted(f for f in os.listdir(directory) if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS)


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


def scan_photos(photos_dir, site_rel_path, caption_key, captions):
    """Return [{src, caption}] for all images in photos_dir."""
    manual = captions.get(caption_key, {})
    return [
        {
            "src": site_rel_path + "/" + f,
            "caption": manual.get(f, clean_caption(f))
        }
        for f in _list_images(photos_dir)
    ]


def scan_leaf_gallery(folder_path, site_rel_path, captions):
    """Scan a folder whose images sit directly inside (no Photos/ subdirectory)."""
    folder_name = os.path.basename(folder_path)
    node = _make_node(folder_name, read_meta(folder_path), "gallery", site_rel_path)
    node["photos"] = scan_photos(folder_path, site_rel_path, folder_name, captions)
    return node


def scan_collection(folder_path, site_rel_path, captions):
    """Recursively build a collection node from folder_path."""
    folder_name = os.path.basename(folder_path)
    meta        = read_meta(folder_path)
    coll_type   = meta.get("type", "gallery")

    node = _make_node(folder_name, meta, coll_type, site_rel_path)

    if coll_type == "parent":
        children = []

        # Standard sub-collections in sub/
        sub_dir = os.path.join(folder_path, "sub")
        if os.path.isdir(sub_dir):
            for name in sorted(os.listdir(sub_dir)):
                child_path = os.path.join(sub_dir, name)
                if os.path.isdir(child_path):
                    child = scan_collection(
                        child_path,
                        site_rel_path + "/sub/" + name,
                        captions
                    )
                    children.append(child)

        # Country-code-style galleries sitting as sub-directories inside Photos/
        photos_dir = os.path.join(folder_path, "Photos")
        if os.path.isdir(photos_dir):
            for name in sorted(os.listdir(photos_dir)):
                child_path = os.path.join(photos_dir, name)
                if os.path.isdir(child_path):
                    child = scan_leaf_gallery(
                        child_path,
                        site_rel_path + "/Photos/" + name,
                        captions
                    )
                    children.append(child)

        children.sort(key=lambda x: (x["order"], x["id"]))
        node["children"] = children

    elif coll_type == "gallery":
        photos_dir = os.path.join(folder_path, "Photos")
        node["photos"] = scan_photos(
            photos_dir,
            site_rel_path + "/Photos",
            folder_name,
            captions
        )

    # coming-soon: no children or photos added

    return node


def collect_galleries(node, index):
    """Walk the nested tree and populate a flat id→gallery dict."""
    if node["type"] == "gallery":
        index[node["id"]] = {
            "name":   node["title"],
            "photos": node.get("photos", []),
        }
    for child in node.get("children", []):
        collect_galleries(child, index)


def build_data_js():
    root             = os.path.dirname(os.path.abspath(__file__))
    collections_path = os.path.join(root, COLLECTIONS_ROOT)

    if not os.path.isdir(collections_path):
        print(f"Error: {COLLECTIONS_ROOT} not found")
        return

    captions = load_captions(root)

    collections = []
    for name in sorted(os.listdir(collections_path)):
        folder_path = os.path.join(collections_path, name)
        if not os.path.isdir(folder_path):
            continue
        node = scan_collection(folder_path, COLLECTIONS_ROOT + "/" + name, captions)
        collections.append(node)
    collections.sort(key=lambda x: (x["order"], x["id"]))

    gallery_index = {}
    for c in collections:
        collect_galleries(c, gallery_index)

    output_path = os.path.join(root, OUTPUT_PATH)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("// Auto-generated by build.py — do not edit manually\n\n")
        f.write("const collectionsData = ")
        f.write(json.dumps(collections, indent=2, ensure_ascii=False))
        f.write(";\n\n")
        f.write("// Flat gallery lookup for gallery.html, keyed by folder name / country code\n")
        f.write("const siteData = ")
        f.write(json.dumps(gallery_index, indent=2, ensure_ascii=False))
        f.write(";\n")

    total_photos = sum(len(v["photos"]) for v in gallery_index.values())
    print("─────────────────────────────────")
    print("data.js rebuilt successfully")
    print(f"Top-level collections : {len(collections)}")
    print(f"Total galleries       : {len(gallery_index)}")
    print(f"Total photos indexed  : {total_photos}")
    print("─────────────────────────────────")


def generate_captions_json():
    """Write/update captions.json stubs for all gallery folders."""
    root             = os.path.dirname(os.path.abspath(__file__))
    collections_path = os.path.join(root, COLLECTIONS_ROOT)

    existing = load_captions(root)
    updated  = dict(existing)
    added    = 0

    # Build tree with no existing captions so auto-captions populate photo entries
    collections = []
    for name in sorted(os.listdir(collections_path)):
        fp = os.path.join(collections_path, name)
        if os.path.isdir(fp):
            collections.append(scan_collection(fp, COLLECTIONS_ROOT + "/" + name, {}))

    def stub_node(node):
        nonlocal added
        if node["type"] == "gallery":
            bucket = updated.setdefault(node["id"], {})
            for photo in node.get("photos", []):
                filename = os.path.basename(photo["src"])
                if filename not in bucket:
                    bucket[filename] = photo["caption"]
                    added += 1
        for child in node.get("children", []):
            stub_node(child)

    for c in collections:
        stub_node(c)

    captions_path = os.path.join(root, CAPTIONS_PATH)
    with open(captions_path, 'w', encoding='utf-8') as f:
        json.dump(updated, f, indent=2, ensure_ascii=False)

    total = sum(len(v) for v in updated.values())
    print(f"captions.json updated — {total} total entries, {added} new stubs added")


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'captions':
        generate_captions_json()
    else:
        build_data_js()
