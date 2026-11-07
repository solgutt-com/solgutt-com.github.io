# Dev Log

---

## 2026-11-07

### Film palette for the photography pages
- Every photography page now uses the film palette sampled from the rolls: a darkroom of warm black deepening to oxblood, linen text, saffron accents, and soft staggered light-leak seams under each heading and between collections
- Each page ends in a saffron-to-sun footer with the menu; the gallery viewer stays a pure darkroom
- Homepage: the haystack and needle are replaced by a film-strip reel. Twelve strips of photos from the collections scroll like a feed and settle on one gallery's cover (a different one each visit); clicking it opens that gallery
- Literata replaces Spectral, so the photography pages and Put It On Paper share the same two typefaces; the olive needle's-eye frame around Fotos is gone
- Later: the homepage reel shows a single gallery cover at full size, cut into strips that slide into line, smaller and framed in a thin linen line; the blocky horizontal seams and stretched leak photo are replaced by smooth vertical light leaks down both edges of the screen (not in the gallery viewer) and a smooth fade into the footer

### Put It On Paper: Tide only
- Tide is now the page's only palette, made lighter and calmer: deep sea blue instead of near-black at the top, the aqua light leak opening straight onto sea-foam practices, then sea glass, yellow, apricot and sand. The colour switch is gone
- Logo files and the favicon mark recoloured in Tide
- Put It On Paper's hero is words only now: the film strips and the window photo are gone (the strips live on as the photography homepage's reel)
- Put It On Paper matches the photography pages' light leaks: smooth vertical glows in Tide colours down both screen edges, the blocky seams replaced by plain OKLab fades, and the aqua leak band redrawn as a smooth glow instead of the stretched scan

### Thin white frames
- The homepage reel and the gallery viewer's photo get a thin white border (`--frame`), drawn outside the photo so nothing shifts; the reel starts on the small preview and swaps in the full-size photo as soon as it arrives

---

## 2026-11-05

### Put It On Paper
- New page at `put-it-on-paper/` (solgutt.com/put-it-on-paper/) for the handwriting practice, linked from every page's menu
- Its own look, drawn from the film: the page gets lighter as you scroll, from darkroom red through a real light leak to sunlit grass; Archivo set extra-condensed against expanded, Literata for reading
- Hero: strips of ten film frames scroll like a feed and settle on the open window from `PioPcover.jpeg` (cropped 3:2, blue scanner line removed)
- Two practices (Catch a fragment; Scroll, then recall with a built-in timer), the Instagram brain essay as its own view (`#instagram-brain`), and a request form that turns a request into a message to send
- Edit page: opened through the editor, every word on the page can be edited in place; Save writes `put-it-on-paper/index.html`
- Editor: **Edit Put It On Paper** link, a `/__pop_save` route, and Publish now includes `put-it-on-paper/`
- Brand, plan, logo files, sources and original photos in `Put it on Paper/` (not published)
- Later: the hero shows the whole window (full-width 3:2 crop) in a larger frame; staggered "seams" of neighbouring colours break the gradient between sections; Edit page gained **Arrange** (move, resize, text size, padding, corners, alignment, kept separately for wide screens and phones); the editor refuses a save from a copy of the page opened before its latest rebuild
- Then: no caption under the hero photo, which is now feathered into the page with a soft window glow; seams blur and fade into the colour around them with light film grain; booking through Cal.com (paste the booking link in edit mode; the request form stays as the fallback); a shop plan for prints and photo-cover journals in the playbook
- Last: two typefaces only (Archivo extra-condensed for headings and the logo, Literata for reading, including the italic second lines); the logo is now one typeface, stacked PUT IT ON / PAPER with both lines the same width, in the header and footer
- Tide: a second palette in blues (deep blue, aqua, green, yellow, orange, sand), each colour the film colour's OKLCH lightness and chroma at a new hue, with a Tide version of the light-leak photo; a two-swatch switch in the header lets visitors choose (remembered per browser), and the scheme saved in edit mode is the default; every colour on the page now comes from the palette

### Instagram uploader
- New folder `instagram-uploader/`: its own public GitHub repo (`solgutt-com/instagram-uploader`), listed in `.gitignore` so it never ends up on the site
- Drop photos into `instagram-uploader/queue/`. Within seconds each photo gets a `.txt` caption with the same name: the date and time it was taken, the place (from GPS, or the location typed in Lightroom), and the camera with its settings. Type extra words into the `.txt` and they're posted exactly as written
- Each photo is replaced by an Instagram-ready copy: sRGB, upright, 1440 px wide, fitted to 4:5–1.91:1 with white side bars (no cropping), and all metadata stripped so GPS never reaches GitHub. The untouched original is kept locally in `originals/`
- A background watcher on the Mac does this and syncs the folder with GitHub. It runs through a small helper app, "Instagram Uploader", because macOS only lets it read the Desktop after you click Allow once. Install with `bash instagram-uploader/scripts/install-watcher.sh`
- GitHub Actions posts one photo at 09:00 and one at 19:00 (Israel time) through Instagram's official API, even with the Mac off. Photos go in alphabetical filename order and move to `posted/` afterwards, with links in `posted/log.csv`. Change the times or number per day in `config.json`
- Connected to **@sol_gutt_foto** with a never-expiring system-user token from Meta Business Settings: secrets `IG_ACCESS_TOKEN` + `IG_USER_ID`. It refuses to post to any other account. The route that worked is written down in `instagram-uploader/SETUP.md`
- 16 B&W photos queued. The first post is set for 19:00 today

---

## 2026-10-29

### "Haystack" redesign goes live
- New look across every page: straw background, olive-black ink, one steel-blue accent; Archivo (condensed headings) + Spectral (captions, descriptions, CV)
- Homepage: a drawn haystack with one hidden needle. The hay drops in and the needle falls into it on the first visit of each browser session; straws bounce away from the cursor and a breeze sways the stack. Clicking the needle zooms through its eye into Fotos
- Fotos and collection pages show real photo thumbnails instead of icons; galleries have a dark viewer, "4 of 48" counter, Previous / Next and a filmstrip; each photo has its own link (`#4`)
- About: CV typeset as a proper page instead of the typing animation
- Map: lists only countries with photos (adds Belgium and Luxembourg)
- New shared files: `site.js` (data helpers used by every page), `make_thumbs.py` + `thumbs/` (small previews for grids and filmstrips)

### Adding photos now
- Run `python3 build.py`, then `python3 make_thumbs.py` (only makes thumbnails for new or changed photos)

### Later the same day
- Homepage settled on a dense stack whose straws bounce away from the cursor, with a matte olive needle hidden at a new spot and angle on every visit; clicking it levels the needle sideways and zooms through its eye into Fotos
- Two typefaces used consistently: Archivo at one condensed width (800 / 500) and Spectral regular / italic
- Fewer words: no gallery or photo counts, no description line under collection titles
- Olive replaces the blue accent; Fotos has a thin rounded olive frame around the window

### Editor for ordering
- `python3 edit.py` opens a local editor in the browser (only on this computer, never on the live site)
- Drag collections and galleries into order, drag photos within a gallery, edit captions, star a cover
- Save writes the right `collections.json` files, rebuilds `data.js` and makes missing thumbnails; then `git push` to publish
- Replaces the copy-and-paste `reorder.html`
- `build.py` gained `collect_trees()` so the editor can read the same structure the build uses (output unchanged)

### Sharper previews, smaller site (2026-11-01)
- 207 photos longer than 2400 px scaled to 2400 px (quality 85): 820 MB -> 234 MB; the published site went from about 1.3 GB to about 720 MB, under GitHub Pages' 1 GB limit. The full-size versions remain in git history
- `make_thumbs.py` also makes sharp 640 px copies in `thumbs-large/` of the photos shown large (the Fotos squares and collection cards), picked the same way `site.js` picks them, and removes ones no longer used
- Fotos squares and collection cards use the sharp copies, falling back to the small thumbnail, then the photo

---

## 2026-05-17

### Folder structure cleanup
- Renamed `Analog-BW/Sub/` → `sub/` (lowercase)
- Renamed `Around the world/` → `Around-the-World/`
- Fixed typo `Euopean Voyage/` → `European-Voyage/`
- Renamed `Coming Soon/` → `Coming-Soon/`
- Renamed `os_cidadãos/` → `os_cidadaos/` (removed accent for URL safety)
- Renamed `um_passeio_até_ao_hotel_longroiva/` → `hotel_longroiva/`

### European-Voyage photo flattening
- Moved all country code folders (AL, AT, BA, BE, BW, CH, DE, EE, ES, FI, FR, Highlights, HR, IT, LT, LV, LX, ME, NL, PL, PT, SE, SI, TheJungle, XX, ZA, ZW) from `European-Voyage/Photos/Images_CountryCode/` up one level into `European-Voyage/Photos/`
- Removed empty `Images_CountryCode/` wrapper folder

### Africa collection restructure
- Renamed `SA/` → `Searching-for-King-Solomons-Mines/` (combines SA + ZW photos into one gallery)
- Promoted `ZW/Photos/` up to `Searching-for-King-Solomons-Mines/Photos/`
- Removed `ZW/` sub-folder (no longer needed)
- Updated `collections.json`: type `gallery`, title "Searching for King Solomon's Mines"

### collections.json scaffolding
- Created `collections.json` template in all 18 collection and sub-collection folders
- Fields: `title`, `subtitle`, `description`, `cover`, `order`, `type`
- Types assigned: `parent` (has sub-collections), `gallery` (leaf with Photos/), `coming-soon`

### build.py rewrite
- Rewrote `build.py` to scan `Images/Collections/` hierarchy instead of old `Images_CountryCode/`
- Outputs two JS variables: `collectionsData` (nested tree for new pages) and `siteData` (flat lookup for `gallery.html`)
- `src` values in `siteData` are now full paths from site root (e.g. `Images/Collections/.../AL_1.jpeg`)
- Handles three folder patterns: `sub/` for parent collections, `Photos/sub-dirs` for country-code style, `Photos/` files for leaf galleries
- `captions.json` backward-compatible: country codes still used as caption keys
- Fixed trailing-comma JSON errors in `captions.json`
- Run: `python3 build.py` → rebuilds `data.js`; `python3 build.py captions` → updates caption stubs

### gallery.html path update
- Updated `countries/gallery.html` to use `../${p.src}` instead of `../Images_CountryCode/${country.folder}/${p.src}`
- Now works with full paths stored in `siteData`

### SVG collection icons designed (viewBox="0 0 120 100")
- **Cidadelhe**: stone gate/wall (provided from prior session)
- **Analog-BW**: camera body with pentaprism bump + concentric lens rings
- **Around-the-World**: globe — circle + equator ellipse + prime meridian line
- **Coming-Soon**: hourglass — left V + right V + top/bottom caps in one path

### photography.html — new collections landing page
- Replaced old map page with 2×2 quadrant grid layout
- Each quadrant: SVG icon (dim by default), title, subtitle, description on hover
- Hover: icon brightens, description fades in; subtle background lift
- Coming-Soon quadrant is dimmed and non-interactive (`pointer-events: none`)
- "Browse by country →" footer link → `map.html`
- JS reads `collectionsData` from `data.js` to populate subtitle + description dynamically
- Mobile (≤768px): single column, description hidden
- Old map page content copied to `map.html` (map.html not yet cleaned up)

### style.css additions
- `.collections-grid`, `.collection-quadrant`, `.collection-icon`, `.collection-info`
- `.collection-title`, `.collection-subtitle`, `.collection-description`
- `.collection-coming-soon`, `.collections-footer`, `.browse-countries`
- Mobile responsive overrides at 768px breakpoint

### sub-collection.html — intermediate collection page
- Reads `?id=` from URL, DFS-searches `collectionsData` for the matching node
- Lists children as rows: title, subtitle (if set), arrow →
- Rows default to opacity 0.4; hover lifts to 1.0 with arrow sliding right 5px
- Navigation: `parent` type → `sub-collection.html?id=X&parent=Y`; `gallery` type → `countries/gallery.html?code=X`
- Back link reads `?parent=` param and resolves parent title dynamically; falls back to `← Fotos`
- `coming-soon` children rendered as non-interactive `<div>` at 0.15 opacity
- Scrollable content (handles European-Voyage's 27 country children cleanly)
- Mobile: reduced horizontal padding

### Code quality cleanup (simplify review)
- `build.py`: extracted `_list_images()` and `_make_node()` helpers; `scan_leaf_gallery` and `scan_collection` both use them
- `build.py`: `generate_captions_json` now reuses `scan_collection` tree instead of duplicating traversal
- `photography.html`: removed hardcoded collection ID list; now iterates `collectionsData` directly
- `style.css`: removed redundant `color` / `font-weight` from collection label classes (inherited from parent)
- `gallery.html`: cached `photo-counter` DOM element at init

### Git + deployment
- Initialised git repo, added `.gitignore` (excludes `Images/`, backup files, `.DS_Store`)
- Force-pushed all site infrastructure (16 files) to `https://github.com/solgutt-com/solgutt-com.github.io`
- Site live at solgutt.com — images intentionally excluded from repo (516 MB)

---

## What's next

### Content (priority)
- Fill in `subtitle`, `description`, `cover` fields in each `collections.json`, then run `python3 build.py` and push `data.js`
- Add photos to the currently empty folders:
  - `Images/Collections/Analog-BW/sub/Olympus/Photos/`
  - `Images/Collections/Analog-BW/sub/Davide's Camera/Photos/`
  - `Images/Collections/Analog-BW/sub/Plastic Point n Shoot/Photos/`
  - `Images/Collections/Searching-for-King-Solomons-Mines/Photos/`
  - All `Cidadelhe/sub/*/Photos/` folders

### Image hosting
- Decide how to serve the `Images/` folder (currently excluded from git):
  - Option A: push images to a separate `images` branch or repo
  - Option B: host on a CDN (Cloudflare R2, S3, etc.) and update paths in `data.js`
  - Option C: push images directly to the repo if total size stays manageable over time

### Polish
- `map.html`: add a `← Fotos` back-link in the header (currently shows site name)
- `LX` country code in European-Voyage — verify if this is Luxembourg (should be `LU`) or intentional
- Fill in `README.md` with project notes
