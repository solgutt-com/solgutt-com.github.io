# solgutt-com.github.io

Solomon Guttmann's site, published at https://solgutt.com from the `main` branch.

## Reordering collections, galleries and photos

```bash
python3 ~/Desktop/solgutt.github.io/edit.py
```

The editor opens in your browser. Pick something on the left, drag it into order
(⇤ ⇥ send a photo to the start or end, ★ makes it the gallery's cover, captions
are editable under each photo) and press Save or Cmd+S. Saving rebuilds the site,
so "Preview the site" shows the result straight away; Publish puts it live.
Ctrl+C in the terminal stops it.

## Adding photos

1. Drop the photos into the gallery's `Photos/` folder.
2. `python3 build.py` then `python3 make_thumbs.py`
3. Optionally put them in order with the editor.

## Publishing

Press **Publish** in the editor: it commits your saved changes (photos, their
`collections.json` files, `data.js`, thumbnails) and pushes them. GitHub takes a
minute or two to update solgutt.com.

Without the editor:

```bash
cd ~/Desktop/solgutt.github.io && git add -A Images data.js thumbs && git commit -m "Update photos" && git push origin main
```
