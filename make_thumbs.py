"""
make_thumbs.py — small preview images for the photo grids and gallery filmstrip.

Usage (after `python3 build.py`; works from any folder):
  python3 ~/Desktop/solgutt.github.io/make_thumbs.py

Reads every photo listed in data.js and writes a JPEG to
thumbs/<same path>.jpg with its short edge at SHORT_EDGE pixels.
Thumbnails that are already newer than their source are skipped, so re-running
after adding photos only does the new ones. Uses macOS `sips`, no installs needed.
"""

import os, json, subprocess
from concurrent.futures import ThreadPoolExecutor

SHORT_EDGE = 360
QUALITY    = 70
OUT_ROOT   = "thumbs"


def photo_paths():
    with open("data.js", encoding="utf-8") as f:
        s = f.read()
    data = json.loads(s[s.index("["):s.rindex("]") + 1])
    return [p["src"] for c in data for p in c.get("photos", [])]


def thumb_path(src):
    return os.path.join(OUT_ROOT, os.path.splitext(src)[0] + ".jpg")


def size_of(path):
    out = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", path],
                         capture_output=True, text=True).stdout
    vals = [int(line.split(":")[1]) for line in out.splitlines() if "pixel" in line]
    return vals[0], vals[1]


def make(src):
    dst = thumb_path(src)
    if os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src):
        return "skip"
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    w, h = size_of(src)
    # Resample along the long edge so the short edge lands on SHORT_EDGE.
    if w >= h:
        flag, target = "--resampleWidth", max(1, round(w * SHORT_EDGE / h))
    else:
        flag, target = "--resampleHeight", max(1, round(h * SHORT_EDGE / w))
    if min(w, h) <= SHORT_EDGE:
        flag, target = "--resampleWidth", w
    subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", str(QUALITY),
                    flag, str(target), src, "--out", dst],
                   capture_output=True, check=True)
    return "made"


def run():
    srcs = [s for s in photo_paths() if os.path.exists(s)]
    with ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as pool:
        results = list(pool.map(make, srcs))
    total = sum(os.path.getsize(thumb_path(s)) for s in srcs if os.path.exists(thumb_path(s)))
    print(f"{results.count('made')} made, {results.count('skip')} up to date, "
          f"{total / 1e6:.1f} MB of thumbnails in {OUT_ROOT}/")


if __name__ == "__main__":
    # Work from the site root whatever folder this is launched from.
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    run()
