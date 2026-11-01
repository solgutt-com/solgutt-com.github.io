"""
make_thumbs.py — preview images for the photo grids, collection cards and gallery filmstrip.

Usage (after `python3 build.py`; works from any folder):
  python3 ~/Desktop/solgutt.github.io/make_thumbs.py

Reads every photo listed in data.js and writes a small JPEG to
thumbs/<same path>.jpg with its short edge at SHORT_EDGE pixels. The photos that
appear large — the four squares per collection on the Fotos page and the cover on
each collection card — also get a sharper copy in thumbs-large/, chosen the same
way site.js chooses them; sharp copies no longer in use are removed.
Images that are already newer than their source are skipped, so re-running
after adding photos only does the new ones. Uses macOS `sips`, no installs needed.
"""

import os, json, subprocess, unicodedata
from concurrent.futures import ThreadPoolExecutor

SHORT_EDGE = 360
QUALITY    = 70
OUT_ROOT   = "thumbs"

LARGE_EDGE    = 640
LARGE_QUALITY = 80
LARGE_ROOT    = "thumbs-large"


def collections():
    with open("data.js", encoding="utf-8") as f:
        s = f.read()
    return json.loads(s[s.index("["):s.rindex("]") + 1])


def photo_paths():
    return [p["src"] for c in collections() for p in c.get("photos", [])]


def thumb_path(src, root=OUT_ROOT):
    return os.path.join(root, os.path.splitext(src)[0] + ".jpg")


def preview_paths(nodes):
    """The photos shown large on the site, picked exactly as site.js picks them:
    previewPhotos(id, 4) for each row on the Fotos page, previewPhotos(id, 1) for each card."""
    by_id = {n["id"]: n for n in nodes}

    def children(id):
        return sorted((n for n in nodes if n["parent"] == id), key=lambda n: n.get("order") or 999)

    def under(id):
        n = by_id[id]
        return n["photos"] if "photos" in n else [p for k in children(id) for p in under(k["id"])]

    def cover(id):
        n = by_id[id]
        if n.get("cover"):
            starred = next((p for p in under(id) if p["src"].endswith("/" + n["cover"])), None)
            if starred:
                return starred
        if "photos" in n:
            return n["photos"][0] if n["photos"] else None
        for k in children(id):
            p = cover(k["id"])
            if p:
                return p
        return None

    def previews(id, count):
        n, every, picks = by_id[id], under(id), []
        def add(p):
            if p and len(picks) < count and p not in picks:
                picks.append(p)
        for src in n.get("preview", []):
            add(next((p for p in every if p["src"] == src), None))
        if n.get("cover"):
            add(cover(id))
        for k in children(id):
            add(cover(k["id"]))
        step = max(1, len(every) // count)
        for i in range(0, len(every), step):
            add(every[i])
        return picks

    srcs = set()
    for n in nodes:
        if n["parent"] is None:
            srcs.update(p["src"] for p in previews(n["id"], 4))
        srcs.update(p["src"] for p in previews(n["id"], 1))
    return srcs


def size_of(path):
    out = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", path],
                         capture_output=True, text=True).stdout
    vals = [int(line.split(":")[1]) for line in out.splitlines() if "pixel" in line]
    return vals[0], vals[1]


def make(src, root=OUT_ROOT, edge=SHORT_EDGE, quality=QUALITY):
    dst = thumb_path(src, root)
    if os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src):
        return "skip"
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    w, h = size_of(src)
    # Resample along the long edge so the short edge lands on `edge`.
    if w >= h:
        flag, target = "--resampleWidth", max(1, round(w * edge / h))
    else:
        flag, target = "--resampleHeight", max(1, round(h * edge / w))
    if min(w, h) <= edge:
        flag, target = "--resampleWidth", w
    subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", str(quality),
                    flag, str(target), src, "--out", dst],
                   capture_output=True, check=True)
    return "made"


def prune(root, keep):
    """Remove sharp copies whose photo is no longer shown large, and any folders left empty.
    Names are compared in one Unicode form, since macOS may report accented letters (ã) differently."""
    nfc = lambda p: unicodedata.normalize("NFC", p)
    keep = {nfc(p) for p in keep}
    removed = 0
    for folder, _, files in os.walk(root, topdown=False):
        for name in files:
            path = os.path.join(folder, name)
            if nfc(path) not in keep:
                os.remove(path)
                removed += 1
        if folder != root and not os.listdir(folder):
            os.rmdir(folder)
    return removed


def run():
    nodes = collections()
    srcs = [p["src"] for c in nodes for p in c.get("photos", []) if os.path.exists(p["src"])]
    large = sorted(s for s in preview_paths(nodes) if os.path.exists(s))
    with ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as pool:
        results = list(pool.map(make, srcs))
        large_results = list(pool.map(lambda s: make(s, LARGE_ROOT, LARGE_EDGE, LARGE_QUALITY), large))
    removed = prune(LARGE_ROOT, {thumb_path(s, LARGE_ROOT) for s in large}) if os.path.isdir(LARGE_ROOT) else 0
    total = sum(os.path.getsize(thumb_path(s)) for s in srcs if os.path.exists(thumb_path(s)))
    large_total = sum(os.path.getsize(thumb_path(s, LARGE_ROOT)) for s in large if os.path.exists(thumb_path(s, LARGE_ROOT)))
    print(f"{results.count('made')} made, {results.count('skip')} up to date, "
          f"{total / 1e6:.1f} MB of thumbnails in {OUT_ROOT}/")
    print(f"{large_results.count('made')} made, {large_results.count('skip')} up to date, {removed} removed, "
          f"{large_total / 1e6:.1f} MB of sharp previews in {LARGE_ROOT}/")
    return results.count('made') + large_results.count('made')


if __name__ == "__main__":
    # Work from the site root whatever folder this is launched from.
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    run()
