# Dev Log

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
