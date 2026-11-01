# solgutt-com.github.io

Solomon Guttmann's site, published at https://solgutt.com from the `main` branch.

## Reordering collections, galleries and photos

```bash
python3 ~/Desktop/solgutt.github.io/edit.py
```

The editor opens in your browser. Pick something on the left, drag it into order
(⇤ ⇥ send a photo to the start or end, ↺ ↻ rotate it, ★ makes it the gallery's cover, captions
are editable under each photo) and press Save or Cmd+S. Opening Cidadelhe, Analog
B&W or Around the World also lets you choose the four photos it shows on the Fotos
page: click photos to fill the slots, drag to reorder, or reset to automatic. Saving rebuilds the site,
so "Preview the site" shows the result straight away; Publish puts it live.
Ctrl+C in the terminal stops it.

## Adding photos

Open a gallery in the editor and press **Add photos**, or drag photos onto it from
Finder. JPG, PNG, WebP and iPhone HEIC all work (HEIC becomes JPEG); anything longer
than 2400 px is scaled down to keep the site fast, and a photo with the same name as
one already there gets "(2)" added instead of replacing it. New photos land at the end,
outlined: drag them into place, Save, then Publish. The filename is the starting caption.

Without the editor: drop the photos into the gallery's `Photos/` folder, then run
`python3 build.py` and `python3 make_thumbs.py`.

## New galleries and collections

In the editor, open a collection and press **New gallery**, or press **New collection**
on the Fotos page (collections that hold sub-collections, like Around the World, have
it too). Give it a title and an optional subtitle; the editor makes the folder and its
settings and opens it, ready for Add photos. A collection with no photos yet shows
faded on the Fotos page and becomes clickable once it has photos.

## Publishing

Press **Publish** in the editor: it commits your saved changes (photos, their
`collections.json` files, `data.js`, thumbnails) and pushes them. GitHub takes a
minute or two to update solgutt.com.

Without the editor:

```bash
cd ~/Desktop/solgutt.github.io && git add -A Images data.js thumbs thumbs-large && git commit -m "Update photos" && git push origin main
```
