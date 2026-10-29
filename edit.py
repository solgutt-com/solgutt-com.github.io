"""
edit.py — a local editor for the order of collections, galleries and photos.

Usage:
  python3 ~/Desktop/solgutt.github.io/edit.py      (opens the editor in your browser)

Drag collections and galleries into the order they appear on the site, drag photos
within a gallery, edit captions and pick each gallery's cover. Saving writes the
right collections.json files, rebuilds data.js and makes any missing thumbnails.
It runs only on this computer; publish as usual with `git push`. Ctrl+C stops it.
"""

import os, json, threading, webbrowser
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)

import build, make_thumbs

PORT        = 8124
ORIGINS     = {f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}"}
COLLECTIONS = os.path.realpath(os.path.join(ROOT, build.COLLECTIONS_ROOT))
save_lock   = threading.Lock()


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


def write_meta(folder, changes):
    meta = read_meta(folder)
    meta.update(changes)
    with open(os.path.join(folder, "collections.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
        f.write("\n")


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

    build.build_data_js()
    return make_thumbs.run()


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
        # Only the editor page itself may save, never another website open in the browser.
        if self.path != "/__save" or self.headers.get("Origin") not in ORIGINS:
            return self.send_json(403, {"ok": False, "error": "Not allowed."})
        try:
            request = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            with save_lock:
                made = save(request)
            self.send_json(200, {"ok": True, "thumbsMade": made, "tree": tree()})
        except (ValueError, OSError, json.JSONDecodeError) as e:
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
  .card img { display: block; width: 100%; aspect-ratio: 4 / 3; object-fit: cover; pointer-events: none; background: var(--rule); }
  .card .blank { aspect-ratio: 4 / 3; border-bottom: 1px dashed var(--rule); }
  .card .label { padding: 6px 8px 8px; font-family: var(--sans); font-weight: 800; font-size: 15px; line-height: 1.2; }
  .card .num { position: absolute; top: 6px; left: 6px; background: rgba(35, 40, 28, 0.75); color: var(--straw);
               font-family: var(--sans); font-weight: 500; font-size: 12px; padding: 1px 6px; border-radius: 3px; pointer-events: none; }
  .card .tools { position: absolute; top: 4px; right: 4px; display: flex; gap: 2px; }
  .card .tools button { background: rgba(227, 209, 155, 0.92); border-radius: 3px; width: 26px; height: 24px; font-size: 14px; line-height: 1; }
  .card .tools button:hover { background: var(--straw); }
  .card .star[aria-pressed="true"] { color: var(--olive-ink); }
  .card input { width: 100%; border: 0; border-top: 1px solid var(--rule); background: var(--straw); padding: 6px 8px;
                font-family: var(--serif); font-style: italic; font-size: 14px; color: var(--ink); cursor: text; }
  .card input.changed { background: #EEE3BC; }
  .card.is-cover { border-color: var(--olive); }
</style>
</head>
<body>
<header>
  <h1>Editor</h1>
  <p id="status">Loading…</p>
  <a href="/index.html" target="_blank">Preview the site</a>
  <button id="save" disabled>Save</button>
</header>
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

  // Small preview made by make_thumbs.py, falling back to the photo itself.
  function thumb(src) {
    const img = h('img', { src: '/thumbs/' + enc(src.replace(/\.[^.]+$/, '.jpg')), alt: '', loading: 'lazy' });
    img.addEventListener('error', () => { img.src = '/' + enc(src); }, { once: true });
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
    current = find(data, path);
    setDirty(false);
    setStatus(current.type === 'parent' ? 'Drag to change the order.' : 'Drag photos to reorder, edit captions, or star the cover.');
    renderTree();
    if (current.type === 'parent') renderParent(current);
    else renderGallery(current);
  }

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
    panel.replaceChildren(
      h('h2', {}, node.path === data.path ? 'Fotos page' : node.title),
      h('p', { class: 'hint' }, 'Drag to set the order these appear in on the site. Double-click one to open it.'),
      grid);
    makeSortable(grid);
  }

  function renderGallery(node) {
    const grid = h('div', { class: 'grid' });
    if (!node.photos || !node.photos.length) {
      panel.replaceChildren(h('h2', {}, node.title), h('p', { class: 'hint' }, 'This gallery has no photos yet.'));
      return;
    }
    node.photos.forEach(p => {
      const name = fileOf(p.src);
      const star = h('button', { type: 'button', class: 'star', title: 'Use as cover', 'aria-pressed': String(node.cover === name) }, '★');
      const toStart = h('button', { type: 'button', title: 'Move to the start' }, '⇤');
      const toEnd = h('button', { type: 'button', title: 'Move to the end' }, '⇥');
      const caption = h('input', { type: 'text', value: p.caption, placeholder: 'Caption', 'aria-label': 'Caption for ' + name });
      const card = h('div', { class: 'card' + (node.cover === name ? ' is-cover' : ''), draggable: 'true', 'data-file': name, 'data-caption': p.caption },
        h('span', { class: 'num' }), h('div', { class: 'tools' }, toStart, toEnd, star), thumb(p.src), caption);

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
      h('h2', {}, node.title),
      h('p', { class: 'hint' }, 'Drag to reorder, or use ⇤ ⇥ to send a photo to the start or end. ★ makes it the cover shown on the Fotos and collection pages.'),
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
        if (!dragging || card === dragging) return;
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
    } else {
      const cards = [...grid.children];
      body.photos = cards.map(c => c.dataset.file);
      body.captions = {};
      cards.forEach(c => { const v = c.querySelector('input').value; if (v !== c.dataset.caption) body.captions[c.dataset.file] = v; });
      const cover = cards.find(c => c.querySelector('.star').getAttribute('aria-pressed') === 'true');
      body.cover = cover ? cover.dataset.file : '';
    }
    saveBtn.disabled = true;
    setStatus('Saving and rebuilding the site…');
    try {
      const res = await fetch('/__save', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      const out = await res.json();
      if (!out.ok) throw new Error(out.error);
      data = out.tree;
      open(current.path, true);
      setStatus('Saved. The site is rebuilt' + (out.thumbsMade ? ' and ' + out.thumbsMade + ' new thumbnails were made' : '') + '. Preview it, then git push to publish.');
    } catch (err) {
      setStatus('Not saved: ' + err.message, true);
      saveBtn.disabled = false;
    }
  }

  saveBtn.addEventListener('click', save);
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
