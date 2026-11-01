"""
edit.py — a local editor for the order of collections, galleries and photos.

Usage:
  python3 ~/Desktop/solgutt.github.io/edit.py      (opens the editor in your browser)

Drag collections and galleries into the order they appear on the site, drag photos
within a gallery, add new photos, galleries and collections, edit captions, rotate photos and pick each gallery's cover. Saving writes the
right collections.json files, rebuilds data.js and makes any missing thumbnails.
It runs only on this computer. Publish sends the saved changes to solgutt.com
(it commits them and runs `git push`). Ctrl+C stops it.
"""

import os, re, json, shutil, subprocess, tempfile, threading, unicodedata, webbrowser
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlsplit, parse_qs

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)

import build, make_thumbs

PORT        = 8124
ORIGINS     = {f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}"}
COLLECTIONS = os.path.realpath(os.path.join(ROOT, build.COLLECTIONS_ROOT))
save_lock   = threading.Lock()

# What Publish commits: the photos, their collections.json files, data.js and thumbnails.
PUBLISH_PATHS = ["Images", "data.js", "thumbs"]

# Adding photos: what the site can show, what gets converted on the way in (iPhone photos),
# and how big a photo may be before it is scaled down to keep the site fast.
PHOTO_TYPES   = {".jpg", ".jpeg", ".png", ".webp"}
CONVERT_TYPES = {".heic", ".heif"}
MAX_UPLOAD    = 80 * 1024 * 1024
MAX_EDGE      = 2400


def tree():
    """Everything on the site as one nested tree; the top level is the Fotos page."""
    return {"id": "", "title": "Fotos", "type": "parent", "path": build.COLLECTIONS_ROOT,
            "children": build.collect_trees() or []}


def find(node, path):
    if node["path"] == path:
        return node
    for child in node.get("children", []):
        hit = find(child, path)
        if hit:
            return hit
    return None


def folder_for(path):
    """The folder behind a collection path, refusing anything outside Images/Collections."""
    full = os.path.realpath(os.path.join(ROOT, path))
    if full != COLLECTIONS and not full.startswith(COLLECTIONS + os.sep):
        raise ValueError("That folder is outside Images/Collections.")
    if not os.path.isdir(full):
        raise ValueError(f"Folder not found: {path}")
    return full


def read_meta(folder):
    """Like build.read_meta, but refuses to overwrite a collections.json it can't read."""
    path = os.path.join(folder, "collections.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"{os.path.relpath(path, ROOT)} has a formatting error ({e}). Fix it before saving.")


def write_meta(folder, changes, remove=()):
    meta = read_meta(folder)
    meta.update(changes)
    for key in remove:
        meta.pop(key, None)
    with open(os.path.join(folder, "collections.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
        f.write("\n")


def all_photos(node):
    return node.get("photos", []) + [p for c in node.get("children", []) for p in all_photos(c)]


# EXIF orientation values that only turn the photo, and how far clockwise each one turns it.
QUARTER_TURNS = {1: 0, 6: 90, 3: 180, 8: 270}


def exif_orientation(path):
    """A JPEG's EXIF orientation as (value, byte offset of the value, byte order), or (1, None, None)."""
    with open(path, "rb") as f:
        data = f.read()
    if data[:2] != b"\xff\xd8":
        return 1, None, None
    i = 2
    while i + 4 <= len(data) and data[i] == 0xFF and data[i + 1] != 0xDA:
        length = int.from_bytes(data[i + 2:i + 4], "big")
        if data[i + 1] == 0xE1 and data[i + 4:i + 10] == b"Exif\0\0":
            tiff = i + 10
            order = "little" if data[tiff:tiff + 2] == b"II" else "big"
            ifd = tiff + int.from_bytes(data[tiff + 4:tiff + 8], order)
            for n in range(int.from_bytes(data[ifd:ifd + 2], order)):
                entry = ifd + 2 + 12 * n
                if int.from_bytes(data[entry:entry + 2], order) == 0x0112:
                    return int.from_bytes(data[entry + 8:entry + 10], order), entry + 8, order
        i += 2 + length
    return 1, None, None


def rotate_photo(path, degrees):
    """Turn a photo clockwise in place. Its camera's orientation tag is folded into the pixels and
    reset, so browsers and thumbnails all show the same thing; make_thumbs then remakes the
    thumbnail because the photo is newer."""
    orientation, _, _ = exif_orientation(path)
    if orientation not in QUARTER_TURNS:
        raise ValueError(f"{os.path.basename(path)} is mirrored by its camera settings. Rotate it in Preview instead.")
    total = (QUARTER_TURNS[orientation] + degrees) % 360
    if total:
        jpeg = path.lower().endswith((".jpg", ".jpeg"))
        result = subprocess.run(["sips", "-r", str(total), *(["-s", "formatOptions", "92"] if jpeg else []), path],
                                capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise ValueError(f"Could not rotate {os.path.basename(path)}.")
    # sips keeps the EXIF block, so the old tag would turn the photo a second time in browsers.
    _, at, order = exif_orientation(path)
    if at is not None:
        with open(path, "r+b") as f:
            f.seek(at)
            f.write((1).to_bytes(2, order))


def sips(*args):
    result = subprocess.run(["sips", *args], capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise ValueError("macOS couldn't read that file as a photo.")
    return result.stdout


def pixel_size(path):
    values = [line.split(":")[1].strip() for line in sips("-g", "pixelWidth", "-g", "pixelHeight", path).splitlines()
              if "pixel" in line]
    if len(values) != 2 or not all(v.isdigit() for v in values):
        raise ValueError("macOS couldn't read it as a photo.")
    return [int(v) for v in values]


def photos_folder(node):
    """Where a gallery keeps its photos: country galleries hold them directly, the rest in Photos/."""
    folder = folder_for(node["path"])
    if "/Photos/" in node["path"]:
        return folder
    photos = os.path.join(folder, "Photos")
    os.makedirs(photos, exist_ok=True)
    return photos


def add_photo(path, name, body):
    """Put one new photo into a gallery: converted to JPEG if it's HEIC, scaled down if it's very
    large, and renamed with (2), (3)… rather than replacing a photo with the same name."""
    node = find(tree(), path)
    if not node or node.get("type") != "gallery":
        raise ValueError("Photos can only be added to a gallery.")
    name = unicodedata.normalize("NFC", os.path.basename(name.replace("\\", "/"))).strip()
    stem, ext = os.path.splitext(name)
    ext = ext.lower()
    if not stem or stem.startswith("."):
        raise ValueError(f"{name or 'That file'} needs a proper name.")
    if ext not in PHOTO_TYPES | CONVERT_TYPES:
        raise ValueError(f"{name} isn't a photo the site can show. Use JPG, PNG, WebP or HEIC.")
    if not body:
        raise ValueError(f"{name} is empty.")

    folder = photos_folder(node)
    out_ext = ".jpg" if ext in CONVERT_TYPES else ext
    taken = {f.lower() for f in os.listdir(folder)}
    final, n = stem + out_ext, 2
    while final.lower() in taken:
        final, n = f"{stem} ({n}){out_ext}", n + 1
    dest = os.path.join(folder, final)

    # Work on a copy outside the site, so a half-finished file never shows up in a gallery.
    work = tempfile.mkdtemp(prefix="solgutt-upload-")
    try:
        incoming = os.path.join(work, "incoming" + ext)
        with open(incoming, "wb") as f:
            f.write(body)
        width, height = pixel_size(incoming)
        args = []
        if max(width, height) > MAX_EDGE:
            args += ["-Z", str(MAX_EDGE)]
        if ext in CONVERT_TYPES:
            args += ["-s", "format", "jpeg"]
        if args:
            if out_ext in (".jpg", ".jpeg"):
                args += ["-s", "formatOptions", "85"]
            sips(*args, incoming, "--out", os.path.join(work, "ready" + out_ext))
            incoming = os.path.join(work, "ready" + out_ext)
        shutil.move(incoming, dest)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return final


def rebuild():
    build.build_data_js()
    return make_thumbs.run()


def folder_name(title, gallery):
    """A safe folder name in the site's style: a_natureza for galleries, European-Voyage for collections."""
    plain = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    words = re.findall(r"[A-Za-z0-9]+", plain)
    if not words:
        raise ValueError("Give it a title with at least one letter or number.")
    return "_".join(w.lower() for w in words) if gallery else "-".join(words)


def create(request):
    """Make a new, empty gallery or collection inside a collection (or a collection on the Fotos page)."""
    parent = find(tree(), request.get("parent"))
    if not parent or parent.get("type") != "parent":
        raise ValueError("New galleries and collections go inside a collection or on the Fotos page.")
    kind = request.get("kind")
    if kind not in ("gallery", "collection"):
        raise ValueError("Choose a gallery or a collection.")
    on_fotos = parent["path"] == build.COLLECTIONS_ROOT
    if on_fotos and kind == "gallery":
        raise ValueError("The Fotos page holds collections. Open a collection to add a gallery to it.")
    title = " ".join((request.get("title") or "").split())
    subtitle = " ".join((request.get("subtitle") or "").split())
    if not title:
        raise ValueError("Give it a title.")
    if len(title) > 80 or len(subtitle) > 160:
        raise ValueError("Keep the title under 80 characters and the subtitle under 160.")
    siblings = parent.get("children", [])
    if any(c["title"].lower() == title.lower() for c in siblings):
        raise ValueError(f"{'The Fotos page' if on_fotos else parent['title']} already has “{title}”.")

    where = folder_for(parent["path"]) if on_fotos else os.path.join(folder_for(parent["path"]), "sub")
    os.makedirs(where, exist_ok=True)
    base = folder_name(title, kind == "gallery")
    taken = {f.lower() for f in os.listdir(where)}
    name, n = base, 2
    while name.lower() in taken:
        name, n = f"{base}{'_' if kind == 'gallery' else '-'}{n}", n + 1
    folder = os.path.join(where, name)
    os.makedirs(folder)
    write_meta(folder, {"title": title, "subtitle": subtitle, "description": "", "cover": "",
                        "order": len(siblings) + 1, "type": "gallery" if kind == "gallery" else "parent"})
    build.build_data_js()
    return os.path.relpath(folder, ROOT).replace(os.sep, "/")


def save(request):
    node = find(tree(), request.get("path"))
    if not node:
        raise ValueError("That collection no longer exists. Reload the editor.")

    if "children" in request:
        current = [c["path"] for c in node.get("children", [])]
        if sorted(request["children"]) != sorted(current):
            raise ValueError("Galleries were added or removed since the editor loaded. Reload it and try again.")
        for i, child_path in enumerate(request["children"], 1):
            write_meta(folder_for(child_path), {"order": i})

    if "photos" in request:
        files = [os.path.basename(p["src"]) for p in node.get("photos", [])]
        if sorted(request["photos"]) != sorted(files):
            raise ValueError("Photos were added or removed since the editor loaded. Reload it and try again.")
        folder   = folder_for(node["path"])
        sources  = {os.path.basename(p["src"]): p["src"] for p in node.get("photos", [])}
        rotate   = request.get("rotate", {})
        if any(name not in sources or turn not in (90, 180, 270) for name, turn in rotate.items()):
            raise ValueError("A rotation didn't match a photo in this gallery. Reload the editor.")
        for name, turn in rotate.items():
            rotate_photo(os.path.join(ROOT, sources[name]), turn)
        captions = dict(read_meta(folder).get("captions", {}))
        for name, caption in request.get("captions", {}).items():
            if name in files:
                captions[name] = caption.strip()
        changes = {"photo_order": request["photos"]}
        if captions:
            changes["captions"] = captions
        cover = request.get("cover")
        if cover is not None and (cover == "" or cover in files):
            changes["cover"] = cover
        write_meta(folder, changes)

    if "preview" in request:
        if node["path"] == build.COLLECTIONS_ROOT:
            raise ValueError("Choose Fotos photos inside a collection, not on the Fotos page itself.")
        chosen = request["preview"][:4]
        inside = {p["src"] for p in all_photos(node)}
        if any(src not in inside for src in chosen):
            raise ValueError("Some chosen photos are no longer in this collection. Reload the editor.")
        prefix = node["path"] + "/"
        if chosen:
            write_meta(folder_for(node["path"]), {"preview": [src[len(prefix):] for src in chosen]})
        else:
            write_meta(folder_for(node["path"]), {}, remove=("preview",))

    return rebuild()


def git(*args):
    """Run git in the site folder; never stop to ask for a password, fail with a readable message instead."""
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=300,
                            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().splitlines()
        last = detail[-1] if detail else f"git {args[0]} failed"
        if "could not read" in last or "Authentication failed" in last or "403" in last:
            raise ValueError("GitHub didn't accept the saved login. Push once from the Terminal app to sign in again.")
        raise ValueError(last)
    return result.stdout.strip()


def publish():
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    if branch != "main":
        raise ValueError(f"solgutt.com publishes from main, but this folder is on '{branch}'. Switch to main first.")
    git("add", "-A", "--", *PUBLISH_PATHS)
    changed = git("diff", "--cached", "--name-only", "--", *PUBLISH_PATHS).splitlines()
    if changed:
        git("commit", "-m", "Update collections from the editor", "--", *PUBLISH_PATHS)
    git("fetch", "-q", "origin", "main")
    if git("rev-list", "--count", "HEAD..origin/main") != "0":
        raise ValueError("GitHub has changes this computer doesn't. Pull them first (git pull), then publish.")
    if git("rev-list", "--count", "origin/main..HEAD") == "0":
        return {"published": False, "files": 0}
    git("push", "origin", "main")
    return {"published": True, "files": len(changed)}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def log_message(self, *args):
        pass

    def send_json(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/":
            body = EDITOR.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/__tree":
            self.send_json(200, tree())
        else:
            super().do_GET()

    def do_POST(self):
        # Only the editor page itself may change anything, never another website open in the browser.
        url = urlsplit(self.path)
        if url.path not in ("/__save", "/__publish", "/__upload", "/__rebuild", "/__create") or self.headers.get("Origin") not in ORIGINS:
            return self.send_json(403, {"ok": False, "error": "Not allowed."})
        try:
            length = int(self.headers.get("Content-Length", 0))
            if url.path == "/__upload":
                if length > MAX_UPLOAD:
                    self.rfile.read(length)
                    raise ValueError("That photo is over 80 MB. Export a smaller copy first.")
                query = parse_qs(url.query)
                body = self.rfile.read(length)
                with save_lock:
                    name = add_photo(query.get("path", [""])[0], query.get("name", [""])[0], body)
                return self.send_json(200, {"ok": True, "name": name})
            request = json.loads(self.rfile.read(length) or b"{}")
            with save_lock:
                if url.path == "/__save":
                    made = save(request)
                    self.send_json(200, {"ok": True, "thumbsMade": made, "tree": tree()})
                elif url.path == "/__rebuild":
                    made = rebuild()
                    self.send_json(200, {"ok": True, "thumbsMade": made, "tree": tree()})
                elif url.path == "/__create":
                    path = create(request)
                    self.send_json(200, {"ok": True, "path": path, "tree": tree()})
                else:
                    self.send_json(200, {"ok": True, **publish()})
        except (ValueError, OSError, json.JSONDecodeError, subprocess.TimeoutExpired) as e:
            self.send_json(400, {"ok": False, "error": str(e)})


EDITOR = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Editor — Solomon Guttmann</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..100,500..800&family=Spectral:ital,wght@0,400;1,400&display=swap">
<style>
  :root {
    --straw: #E3D19B; --straw-deep: #D5C083; --ink: #23281C; --schist: #5A5843;
    --olive: #6B7550; --olive-ink: #535C3A; --rule: rgba(35, 40, 28, 0.22);
    --sans: 'Archivo', 'Helvetica Neue', Arial, sans-serif; --serif: 'Spectral', Georgia, serif;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html { font-variation-settings: 'wdth' 68; }
  body { background: var(--straw); color: var(--ink); font-family: var(--serif); font-size: 16px; line-height: 1.5;
         height: 100vh; display: grid; grid-template-rows: auto 1fr; }
  button { font: inherit; color: inherit; background: none; border: 0; cursor: pointer; }
  :focus-visible { outline: 2px solid var(--olive-ink); outline-offset: 2px; }

  header { display: flex; align-items: center; gap: 24px; padding: 14px 24px; border-bottom: 1px solid var(--rule); font-family: var(--sans); }
  header h1 { font-weight: 800; font-size: 22px; }
  #status { flex: 1; font-family: var(--serif); font-style: italic; color: var(--schist); font-size: 15px; }
  #status.error { color: #8A2E1C; font-style: normal; }
  header a { color: var(--olive-ink); font-weight: 500; }
  #save { font-weight: 800; background: var(--olive-ink); color: var(--straw); padding: 8px 20px; border-radius: 6px; }
  #save:disabled { background: var(--straw-deep); color: var(--schist); cursor: default; }
  #publish { font-weight: 800; border: 2px solid var(--olive-ink); color: var(--olive-ink); padding: 6px 18px; border-radius: 6px; }
  #publish:disabled { opacity: 0.5; cursor: default; }

  .layout { display: grid; grid-template-columns: 260px 1fr; min-height: 0; }
  nav { overflow-y: auto; padding: 16px 12px 40px; border-right: 1px solid var(--rule); font-family: var(--sans); font-weight: 500; }
  nav ul { list-style: none; }
  nav ul ul { margin-left: 14px; border-left: 1px solid var(--rule); padding-left: 6px; }
  nav button { display: block; width: 100%; text-align: left; padding: 3px 8px; border-radius: 4px; font-size: 15px; }
  nav button:hover { background: var(--straw-deep); }
  nav button[aria-current="true"] { background: var(--olive-ink); color: var(--straw); }
  nav .parent-item > button { font-weight: 800; }

  main { overflow-y: auto; padding: 24px 32px 80px; }
  main h2 { font-family: var(--sans); font-weight: 800; font-size: 40px; line-height: 1; }
  .hint { font-style: italic; color: var(--schist); margin: 8px 0 24px; max-width: 70ch; }

  .grid { display: grid; gap: 14px; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); }
  .card { background: var(--straw-deep); border-radius: 6px; overflow: hidden; cursor: grab; position: relative;
          border: 2px solid transparent; user-select: none; }
  .card.dragging { opacity: 0.35; }
  .card.over { border-color: var(--olive-ink); }
  .card img { display: block; width: 100%; aspect-ratio: 4 / 3; object-fit: cover; pointer-events: none; background: var(--rule);
              transition: transform 0.2s; }
  .card .blank { aspect-ratio: 4 / 3; border-bottom: 1px dashed var(--rule); }
  .card .label { padding: 6px 8px 8px; font-family: var(--sans); font-weight: 800; font-size: 15px; line-height: 1.2; }
  .card .num { position: absolute; top: 6px; left: 6px; background: rgba(35, 40, 28, 0.75); color: var(--straw);
               font-family: var(--sans); font-weight: 500; font-size: 12px; padding: 1px 6px; border-radius: 3px; pointer-events: none; }
  .card .tools { position: absolute; top: 4px; right: 4px; display: flex; gap: 2px; z-index: 1; }
  .card .num { z-index: 1; }
  .card .tools button { background: rgba(227, 209, 155, 0.92); border-radius: 3px; width: 26px; height: 24px; font-size: 14px; line-height: 1; }
  .card .tools button:hover { background: var(--straw); }
  .card .star[aria-pressed="true"] { color: var(--olive-ink); }
  .card input { width: 100%; border: 0; border-top: 1px solid var(--rule); background: var(--straw); padding: 6px 8px;
                font-family: var(--serif); font-style: italic; font-size: 14px; color: var(--ink); cursor: text; }
  .card input.changed { background: #EEE3BC; }
  .card.is-cover { border-color: var(--olive); }

  section + section { margin-top: 40px; }
  h3 { font-family: var(--sans); font-weight: 800; font-size: 22px; margin-bottom: 4px; }
  .slots { display: grid; grid-template-columns: repeat(4, minmax(0, 170px)); gap: 14px; }
  .slots .card.auto { opacity: 0.55; cursor: default; }
  .slots .empty { aspect-ratio: 4 / 3; border: 2px dashed var(--rule); border-radius: 6px; }
  .slot-actions { display: flex; gap: 16px; align-items: baseline; margin-top: 12px; font-family: var(--sans); }
  .slot-actions button { color: var(--olive-ink); font-weight: 500; text-decoration: underline; }
  .pool h4 { font-family: var(--sans); font-weight: 800; font-size: 15px; margin: 18px 0 6px; }
  .pool .picks { display: grid; gap: 6px; grid-template-columns: repeat(auto-fill, minmax(92px, 1fr)); }
  .pool button { border-radius: 4px; overflow: hidden; border: 3px solid transparent; }
  .pool button[aria-pressed="true"] { border-color: var(--olive-ink); }
  .pool img { display: block; width: 100%; aspect-ratio: 1; object-fit: cover; }

  .gallery-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 24px; }
  .add-photos { font-family: var(--sans); font-weight: 800; border: 2px solid var(--olive-ink); color: var(--olive-ink);
                padding: 6px 18px; border-radius: 6px; white-space: nowrap; }
  .add-photos:hover { background: var(--straw-deep); }
  .card.is-new { border-color: var(--olive-ink); box-shadow: 0 0 0 2px var(--olive-ink); }
  main.dropping { outline: 3px dashed var(--olive-ink); outline-offset: -12px; background: #E8D9A8; }
  .head-actions { display: flex; gap: 10px; }

  dialog { margin: auto; border: 0; border-radius: 10px; padding: 24px 28px; width: min(440px, 92vw);
           background: var(--straw); color: var(--ink); box-shadow: 0 20px 60px rgba(35, 40, 28, 0.35); }
  dialog::backdrop { background: rgba(35, 40, 28, 0.35); }
  dialog h3 { margin-bottom: 4px; }
  dialog label { display: block; font-family: var(--sans); font-weight: 500; font-size: 14px; margin-top: 16px; }
  dialog input { display: block; width: 100%; margin-top: 4px; padding: 8px 10px; border: 1px solid var(--rule); border-radius: 5px;
                 background: #EEE3BC; font-family: var(--serif); font-size: 16px; color: var(--ink); }
  dialog .error { color: #8A2E1C; font-size: 14px; margin-top: 10px; min-height: 1.2em; }
  dialog .actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 18px; font-family: var(--sans); }
  dialog .actions button { padding: 7px 18px; border-radius: 6px; font-weight: 800; }
  dialog .actions .primary { background: var(--olive-ink); color: var(--straw); }
  dialog .actions .primary:disabled { opacity: 0.6; cursor: default; }
</style>
</head>
<body>
<header>
  <h1>Editor</h1>
  <p id="status">Loading…</p>
  <a href="/index.html" target="_blank">Preview the site</a>
  <button id="save" disabled>Save</button>
  <button id="publish">Publish</button>
</header>
<dialog id="create">
  <form method="dialog">
    <h3 id="create-title">New gallery</h3>
    <p class="hint" id="create-where"></p>
    <label>Title <input name="title" required maxlength="80" autocomplete="off"></label>
    <label>Subtitle (optional) <input name="subtitle" maxlength="160" autocomplete="off"></label>
    <p class="error" id="create-error"></p>
    <div class="actions"><button type="button" value="cancel" id="create-cancel">Cancel</button><button class="primary" id="create-go">Create</button></div>
  </form>
</dialog>
<div class="layout">
  <nav id="tree" aria-label="Collections"></nav>
  <main id="panel"></main>
</div>

<script>
  const treeEl = document.getElementById('tree');
  const panel = document.getElementById('panel');
  const statusEl = document.getElementById('status');
  const saveBtn = document.getElementById('save');
  let data = null, current = null, dirty = false, dragging = null;

  function h(tag, attrs, ...children) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) if (v != null && v !== false) el.setAttribute(k, v === true ? '' : v);
    for (const c of children.flat()) if (c != null && c !== '') el.append(c);
    return el;
  }

  const enc = path => path.split('/').map(encodeURIComponent).join('/');
  const fileOf = src => src.split('/').pop();
  const rotatedAt = {};  // src → when it was rotated, so the browser fetches the new file

  // Small preview made by make_thumbs.py, falling back to the photo itself.
  function thumb(src) {
    const v = rotatedAt[src] ? '?v=' + rotatedAt[src] : '';
    const img = h('img', { src: '/thumbs/' + enc(src.replace(/\.[^.]+$/, '.jpg')) + v, alt: '', loading: 'lazy' });
    img.addEventListener('error', () => { img.src = '/' + enc(src) + v; }, { once: true });
    return img;
  }

  function firstPhoto(node) {
    if (node.photos && node.photos.length) {
      return (node.cover && node.photos.find(p => fileOf(p.src) === node.cover)) || node.photos[0];
    }
    for (const c of node.children || []) { const p = firstPhoto(c); if (p) return p; }
    return null;
  }

  function find(node, path) {
    if (node.path === path) return node;
    for (const c of node.children || []) { const hit = find(c, path); if (hit) return hit; }
    return null;
  }

  function setStatus(text, isError) {
    statusEl.textContent = text;
    statusEl.classList.toggle('error', !!isError);
  }

  function setDirty(on) {
    dirty = on;
    saveBtn.disabled = !on;
    if (on) setStatus('Unsaved changes');
  }

  // ─── Left: every collection and gallery ───

  function renderTree() {
    const list = node => h('ul', {}, (node.children || []).map(item));
    const item = node => {
      const btn = h('button', { type: 'button', 'aria-current': current && current.path === node.path ? 'true' : 'false' }, node.title);
      btn.addEventListener('click', () => open(node.path));
      return h('li', { class: node.children ? 'parent-item' : '' }, btn, node.children ? list(node) : null);
    };
    const top = h('button', { type: 'button', 'aria-current': current && current.path === data.path ? 'true' : 'false' }, 'Fotos page');
    top.addEventListener('click', () => open(data.path));
    treeEl.replaceChildren(h('ul', {}, h('li', { class: 'parent-item' }, top, list(data))));
  }

  // ─── Right: the thing being ordered ───

  function open(path, force) {
    if (!force && dirty && !confirm('You have unsaved changes. Discard them?')) return;
    if (current && current.path !== path) justAdded = new Set();
    current = find(data, path);
    setDirty(false);
    setStatus(current.type === 'parent' ? 'Drag to change the order.' : 'Drag photos to reorder, edit captions, or star the cover.');
    renderTree();
    if (current.type === 'parent') renderParent(current);
    else renderGallery(current);
  }

  // The four photos a top-level collection shows on the Fotos page, worked out the
  // same way the site does when nothing is chosen.
  function autoPicks(node) {
    const all = [];
    const collect = n => { (n.photos || []).forEach(p => all.push(p)); (n.children || []).forEach(collect); };
    collect(node);
    const picks = [];
    const add = p => { if (p && picks.length < 4 && !picks.includes(p)) picks.push(p); };
    if (node.cover) add(firstPhoto(node));
    (node.children || []).forEach(c => add(firstPhoto(c)));
    const step = Math.max(1, Math.floor(all.length / 4));
    for (let i = 0; i < all.length && picks.length < 4; i += step) add(all[i]);
    return picks.map(p => p.src);
  }

  function fotosPicker(node) {
    let chosen = (node.preview || []).slice();
    const slots = h('div', { class: 'slots' });
    const note = h('span', { class: 'hint' });
    const reset = h('button', { type: 'button' }, 'Reset to automatic');
    const pool = h('div', { class: 'pool' });
    const poolButtons = [];

    // Read the order back from the slots, in case they were dragged.
    const syncFromSlots = () => {
      if (chosen.length) chosen = [...slots.querySelectorAll('.card')].map(c => c.dataset.src);
    };

    function draw() {
      const auto = !chosen.length;
      const shown = auto ? autoPicks(node) : chosen;
      const cards = shown.map(src => {
        const remove = h('button', { type: 'button', title: 'Remove' }, '×');
        const card = h('div', { class: 'card' + (auto ? ' auto' : ''), 'data-src': src, draggable: auto ? null : 'true' },
          h('span', { class: 'num' }), auto ? null : h('div', { class: 'tools' }, remove), thumb(src));
        remove.addEventListener('click', () => { syncFromSlots(); chosen = chosen.filter(s => s !== src); setDirty(true); draw(); });
        return card;
      });
      const blanks = auto ? [] : Array.from({ length: 4 - chosen.length }, () => h('div', { class: 'empty' }));
      slots.replaceChildren(...cards, ...blanks);
      if (!auto) makeSortable(slots); else renumber(slots);
      note.textContent = auto ? 'Automatic: the covers of the first galleries. Click photos below to choose your own.'
                              : chosen.length + ' of 4 chosen. Drag to reorder.';
      reset.hidden = auto;
      poolButtons.forEach(b => b.setAttribute('aria-pressed', String(chosen.includes(b.dataset.src))));
    }

    reset.addEventListener('click', () => { chosen = []; setDirty(true); draw(); });

    const group = n => {
      if (n.photos && n.photos.length) {
        const buttons = n.photos.map(p => {
          const b = h('button', { type: 'button', 'data-src': p.src, title: p.caption || fileOf(p.src) }, thumb(p.src));
          b.addEventListener('click', () => {
            syncFromSlots();
            if (chosen.includes(p.src)) chosen = chosen.filter(s => s !== p.src);
            else if (chosen.length >= 4) { setStatus('Four are already chosen. Remove one first.', true); return; }
            else chosen.push(p.src);
            setDirty(true);
            draw();
          });
          poolButtons.push(b);
          return b;
        });
        pool.append(h('h4', {}, n.title), h('div', { class: 'picks' }, buttons));
      }
      (n.children || []).forEach(group);
    };
    group(node);
    draw();

    const section = h('section', {},
      h('h3', {}, 'Shown on the Fotos page'),
      h('p', { class: 'hint' }, 'The four photos next to ' + node.title + ' on the Fotos page.'),
      slots, h('div', { class: 'slot-actions' }, note, reset));
    section.readChoice = () => { syncFromSlots(); return chosen; };
    return { section, pool };
  }

  // ─── New galleries and collections ───

  const dialog = document.getElementById('create');
  const form = dialog.querySelector('form');
  let creating = null;  // { parent, kind }

  function newButton(node, kind) {
    const b = h('button', { type: 'button', class: 'add-photos' }, kind === 'gallery' ? 'New gallery' : 'New collection');
    b.addEventListener('click', () => {
      if (dirty) { setStatus('Save your changes first.', true); return; }
      creating = { parent: node, kind };
      document.getElementById('create-title').textContent = b.textContent;
      document.getElementById('create-where').textContent = node.path === data.path
        ? 'A new section on the Fotos page. Add galleries to it next.'
        : 'Inside ' + node.title + '. ' + (kind === 'gallery' ? 'Add photos to it next.' : 'Add galleries to it next.');
      document.getElementById('create-error').textContent = '';
      form.reset();
      dialog.showModal();
      form.elements.title.focus();
    });
    return b;
  }

  document.getElementById('create-cancel').addEventListener('click', () => dialog.close());
  form.addEventListener('submit', async e => {
    e.preventDefault();
    const go = document.getElementById('create-go');
    go.disabled = true;
    try {
      const res = await fetch('/__create', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ parent: creating.parent.path, kind: creating.kind, title: form.elements.title.value, subtitle: form.elements.subtitle.value }) });
      const out = await res.json();
      if (!out.ok) throw new Error(out.error);
      dialog.close();
      data = out.tree;
      open(out.path, true);
      setStatus('Created “' + form.elements.title.value.trim() + '”. ' + (creating.kind === 'gallery'
        ? 'Add photos to it, then Publish.' : 'Add galleries to it with New gallery, then Publish.'));
    } catch (err) {
      document.getElementById('create-error').textContent = err.message;
    } finally {
      go.disabled = false;
    }
  });

  function renderParent(node) {
    const grid = h('div', { class: 'grid' });
    node.children.forEach(child => {
      const cover = firstPhoto(child);
      const card = h('div', { class: 'card', draggable: 'true', 'data-path': child.path },
        h('span', { class: 'num' }),
        cover ? thumb(cover.src) : h('div', { class: 'blank' }),
        h('div', { class: 'label' }, child.title));
      card.addEventListener('dblclick', () => open(child.path));
      grid.append(card);
    });
    const isFotos = node.path === data.path;
    const topLevel = data.children.includes(node);
    const picker = topLevel && firstPhoto(node) ? fotosPicker(node) : null;
    // Collections that already hold sub-collections (like Around the World) can take another one.
    const holdsCollections = (node.children || []).some(c => c.type === 'parent');
    const actions = h('div', { class: 'head-actions' },
      isFotos ? null : newButton(node, 'gallery'),
      isFotos || holdsCollections ? newButton(node, 'collection') : null);
    panel.replaceChildren(
      h('div', { class: 'gallery-head' }, h('h2', {}, isFotos ? 'Fotos page' : node.title), actions),
      picker ? picker.section : null,
      h('section', {},
        picker ? h('h3', {}, 'Gallery order') : null,
        h('p', { class: 'hint' }, isFotos
          ? 'Drag to set the order of the collections on the Fotos page. Double-click one to open it and choose the photos it shows there.'
          : 'Drag to set the order these appear in on the site. Double-click one to open it.'),
        grid),
      picker ? h('section', {}, h('h3', {}, 'All photos in ' + node.title), h('p', { class: 'hint' }, 'Click a photo to show it on the Fotos page; click again to take it off.'), picker.pool) : null);
    panel.picker = picker;
    makeSortable(grid);
  }

  // ─── Adding photos: the button, or dropping files from Finder onto a gallery ───

  const picker = h('input', { type: 'file', multiple: true, accept: 'image/jpeg,image/png,image/webp,.heic,.heif', hidden: true });
  document.body.append(picker);
  picker.addEventListener('change', () => { addPhotos([...picker.files]); picker.value = ''; });
  let justAdded = new Set();  // photos added this time, outlined until you leave the gallery

  function addButton() {
    const b = h('button', { type: 'button', class: 'add-photos' }, 'Add photos');
    b.addEventListener('click', () => {
      if (dirty) { setStatus('Save your changes first, then add photos.', true); return; }
      picker.click();
    });
    return b;
  }

  async function addPhotos(files) {
    if (!files.length || !current || current.type !== 'gallery') return;
    if (dirty) { setStatus('Save your changes first, then add photos.', true); return; }
    const gallery = current.path, added = [], failed = [];
    for (const [i, file] of files.entries()) {
      setStatus('Adding photo ' + (i + 1) + ' of ' + files.length + '…');
      try {
        const res = await fetch('/__upload?path=' + encodeURIComponent(gallery) + '&name=' + encodeURIComponent(file.name),
                                { method: 'POST', headers: { 'Content-Type': 'application/octet-stream' }, body: file });
        const out = await res.json();
        if (!out.ok) throw new Error(out.error);
        added.push(gallery + (gallery.includes('/Photos/') ? '/' : '/Photos/') + out.name);
      } catch (err) {
        failed.push(file.name + ' (' + err.message + ')');
      }
    }
    if (added.length) {
      setStatus('Making thumbnails and rebuilding the site…');
      try {
        const res = await fetch('/__rebuild', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
        const out = await res.json();
        if (!out.ok) throw new Error(out.error);
        data = out.tree;
      } catch (err) {
        setStatus('The photos were added, but the site could not be rebuilt: ' + err.message, true);
        return;
      }
      justAdded = new Set(added);
      open(gallery, true);
    }
    const done = added.length ? 'Added ' + added.length + (added.length === 1 ? ' photo' : ' photos')
      + '. New photos are outlined at the end: drag them into place, Save, then Publish.' : '';
    setStatus([done, failed.length ? 'Not added: ' + failed.join('; ') : ''].filter(Boolean).join(' '), failed.length > 0);
  }

  const isFileDrag = e => [...(e.dataTransfer?.types || [])].includes('Files');
  panel.addEventListener('dragover', e => {
    if (!isFileDrag(e) || !current || current.type !== 'gallery') return;
    e.preventDefault();
    panel.classList.add('dropping');
  });
  panel.addEventListener('dragleave', e => { if (!panel.contains(e.relatedTarget)) panel.classList.remove('dropping'); });
  panel.addEventListener('drop', e => {
    panel.classList.remove('dropping');
    if (!isFileDrag(e) || !current || current.type !== 'gallery') return;
    e.preventDefault();
    addPhotos([...e.dataTransfer.files]);
  });

  function renderGallery(node) {
    const grid = h('div', { class: 'grid' });
    const head = h('div', { class: 'gallery-head' }, h('h2', {}, node.title), addButton());
    if (!node.photos || !node.photos.length) {
      panel.replaceChildren(head, h('p', { class: 'hint' }, 'This gallery has no photos yet. Use Add photos, or drag photos here from Finder.'));
      return;
    }
    node.photos.forEach(p => {
      const name = fileOf(p.src);
      const star = h('button', { type: 'button', class: 'star', title: 'Use as cover', 'aria-pressed': String(node.cover === name) }, '★');
      const toStart = h('button', { type: 'button', title: 'Move to the start' }, '⇤');
      const toEnd = h('button', { type: 'button', title: 'Move to the end' }, '⇥');
      const left = h('button', { type: 'button', title: 'Rotate left' }, '↺');
      const right = h('button', { type: 'button', title: 'Rotate right' }, '↻');
      const caption = h('input', { type: 'text', value: p.caption, placeholder: 'Caption', 'aria-label': 'Caption for ' + name });
      const img = thumb(p.src);
      const card = h('div', { class: 'card' + (node.cover === name ? ' is-cover' : '') + (justAdded.has(p.src) ? ' is-new' : ''), draggable: 'true', 'data-file': name, 'data-caption': p.caption, 'data-turn': '0' },
        h('span', { class: 'num' }), h('div', { class: 'tools' }, left, right, toStart, toEnd, star), img, caption);

      // Shows the turn straight away; the photo itself is rotated when you save.
      const turn = by => {
        const deg = (Number(card.dataset.turn) + by + 360) % 360;
        card.dataset.turn = deg;
        img.style.transform = deg ? `rotate(${deg}deg)` + (deg % 180 ? ' scale(0.75)' : '') : '';
        setDirty(true);
      };
      left.addEventListener('click', () => turn(-90));
      right.addEventListener('click', () => turn(90));

      caption.addEventListener('mousedown', e => e.stopPropagation());
      caption.addEventListener('input', () => { caption.classList.toggle('changed', caption.value !== p.caption); setDirty(true); });
      star.addEventListener('click', () => {
        const on = star.getAttribute('aria-pressed') !== 'true';
        grid.querySelectorAll('.star').forEach(s => s.setAttribute('aria-pressed', 'false'));
        grid.querySelectorAll('.card').forEach(c => c.classList.remove('is-cover'));
        star.setAttribute('aria-pressed', String(on));
        card.classList.toggle('is-cover', on);
        setDirty(true);
      });
      toStart.addEventListener('click', () => { grid.prepend(card); renumber(grid); setDirty(true); });
      toEnd.addEventListener('click', () => { grid.append(card); renumber(grid); setDirty(true); });
      grid.append(card);
    });
    panel.replaceChildren(
      head,
      h('p', { class: 'hint' }, 'Drag to reorder, or use ⇤ ⇥ to send a photo to the start or end. ↺ ↻ rotate a photo; the file itself is turned when you save. ★ makes it this gallery\'s cover: it stands for the gallery on its collection page, and on the Fotos page when the gallery is one of its collection\'s first four. To add photos, use the button or drag them here from Finder.'),
      grid);
    makeSortable(grid);
  }

  function renumber(grid) {
    grid.querySelectorAll('.card .num').forEach((n, i) => { n.textContent = i + 1; });
  }

  function makeSortable(grid) {
    renumber(grid);
    grid.querySelectorAll('.card').forEach(card => {
      card.addEventListener('dragstart', e => { dragging = card; card.classList.add('dragging'); e.dataTransfer.effectAllowed = 'move'; });
      card.addEventListener('dragend', () => { card.classList.remove('dragging'); grid.querySelectorAll('.over').forEach(c => c.classList.remove('over')); dragging = null; });
      card.addEventListener('dragover', e => { e.preventDefault(); if (card !== dragging) card.classList.add('over'); });
      card.addEventListener('dragleave', () => card.classList.remove('over'));
      card.addEventListener('drop', e => {
        e.preventDefault();
        card.classList.remove('over');
        if (!dragging || card === dragging || dragging.parentNode !== grid) return;
        const cards = [...grid.children];
        grid.insertBefore(dragging, cards.indexOf(dragging) < cards.indexOf(card) ? card.nextSibling : card);
        renumber(grid);
        setDirty(true);
      });
    });
  }

  // ─── Saving ───

  async function save() {
    const grid = panel.querySelector('.grid');
    const body = { path: current.path };
    if (current.type === 'parent') {
      body.children = [...grid.children].map(c => c.dataset.path);
      if (panel.picker) body.preview = panel.picker.section.readChoice();
    } else {
      const cards = [...grid.children];
      body.photos = cards.map(c => c.dataset.file);
      body.captions = {};
      cards.forEach(c => { const v = c.querySelector('input').value; if (v !== c.dataset.caption) body.captions[c.dataset.file] = v; });
      const cover = cards.find(c => c.querySelector('.star').getAttribute('aria-pressed') === 'true');
      body.cover = cover ? cover.dataset.file : '';
      body.rotate = {};
      cards.forEach(c => { if (c.dataset.turn !== '0') body.rotate[c.dataset.file] = Number(c.dataset.turn); });
    }
    saveBtn.disabled = true;
    setStatus('Saving and rebuilding the site…');
    try {
      const res = await fetch('/__save', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      const out = await res.json();
      if (!out.ok) throw new Error(out.error);
      (current.photos || []).forEach(p => { if (body.rotate && body.rotate[fileOf(p.src)]) rotatedAt[p.src] = Date.now(); });
      data = out.tree;
      open(current.path, true);
      setStatus('Saved. The site is rebuilt' + (out.thumbsMade ? ' and ' + out.thumbsMade + ' new thumbnails were made' : '') + '. Preview it, then Publish.');
    } catch (err) {
      setStatus('Not saved: ' + err.message, true);
      saveBtn.disabled = false;
    }
  }

  saveBtn.addEventListener('click', save);

  // ─── Publishing: commit the saved changes and push them to solgutt.com ───

  const publishBtn = document.getElementById('publish');
  publishBtn.addEventListener('click', async () => {
    if (dirty) { setStatus('Save your changes first, then publish.', true); return; }
    if (!confirm('Publish your saved changes to solgutt.com?')) return;
    publishBtn.disabled = true;
    setStatus('Publishing to solgutt.com…');
    try {
      const res = await fetch('/__publish', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
      const out = await res.json();
      if (!out.ok) throw new Error(out.error);
      setStatus(out.published ? 'Published. solgutt.com updates in a minute or two.' : 'Nothing new to publish: solgutt.com is already up to date.');
    } catch (err) {
      setStatus('Not published: ' + err.message, true);
    } finally {
      publishBtn.disabled = false;
    }
  });
  document.addEventListener('keydown', e => { if ((e.metaKey || e.ctrlKey) && e.key === 's') { e.preventDefault(); if (dirty) save(); } });
  addEventListener('beforeunload', e => { if (dirty) e.preventDefault(); });

  fetch('/__tree').then(r => r.json()).then(tree => { data = tree; open(data.path, true); })
    .catch(() => setStatus('Could not load the collections. Is edit.py still running?', true));
</script>
</body>
</html>
"""


if __name__ == "__main__":
    url = f"http://127.0.0.1:{PORT}/"
    try:
        server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except OSError:
        print(f"The editor is already running, or port {PORT} is in use. Open {url}")
        raise SystemExit(1)
    print(f"Editor running at {url}  (Ctrl+C to stop)")
    if "--no-open" not in os.sys.argv:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nEditor stopped.")
