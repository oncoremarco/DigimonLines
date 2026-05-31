# DigiTree — Task List

Each phase ends on a **deliverable, stable, testable** build. Phases build on each other; do not start a phase until the prior phase's deliverable passes manual smoke testing.

---

## Phase 1 — Project Shell & Data Layer

Goal: A runnable application window and a fully working save/load data layer. No canvas rendering yet. Verifiable by creating, saving, and reloading a tree file and inspecting it as valid XML.

### 1.1 Project structure
- [ ] Create top-level package `digitree/`
- [ ] Create `main.py` entry point (launches the Qt app)
- [ ] Create `requirements.txt` with pinned dependencies:
  - `PySide6>=6.6.0`
  - `requests>=2.31.0`
  - `beautifulsoup4>=4.12.0`
  - `mwparserfromhell>=0.6.0`
  - `lxml>=4.9.0`
  - `Pillow>=10.0.0`
  - `networkx>=3.0`
  - `tenacity>=8.0.0`
- [ ] Create `README.md` with install and run instructions

### 1.2 App data paths
- [ ] `digitree/app_paths.py` — resolves `%APPDATA%\DigiTree\` on Windows, `~/.local/share/DigiTree/` on Linux/Mac
- [ ] On first launch: create `trees/`, `wikimon_images/`, `presets/`, `exports/` subdirectories
- [ ] Load/save `config.json` (recent trees list, last open path, UI preferences)

### 1.3 Tree XML data model
- [ ] `digitree/models/tree.py` — dataclasses: `Tree`, `Stage`, `TypeTag`, `RequirementType`, `Version`, `Entry`, `Connection`, `RequirementGroup`, `RequirementCondition`
- [ ] `digitree/io/tree_xml.py` — `save_tree(tree, path)` and `load_tree(path) -> Tree` using `lxml.etree`
- [ ] Schema matches the `.dtree.xml` format defined in the spec (Section 4.1)
- [ ] Round-trip test: create a Tree in code, save to XML, reload, assert all fields match

### 1.4 Wikimon SQLite cache
- [ ] `digitree/db/cache.py` — `CacheDB` class wrapping `sqlite3`
- [ ] On open: create `wikimon_cache.db` if absent, run schema migrations
- [ ] Schema: `digimon`, `digimon_attacks`, `digimon_images` tables (Section 4.2)
- [ ] CRUD helpers: `upsert_digimon()`, `get_digimon()`, `upsert_attacks()`, `get_attacks()`, `upsert_image()`, `get_images()`

### 1.5 Main window shell
- [ ] `digitree/ui/main_window.py` — `MainWindow(QMainWindow)`
- [ ] Three-panel layout: left sidebar (tree list), center canvas placeholder (`QLabel("Canvas goes here")`), right profile panel placeholder
- [ ] Status bar at bottom
- [ ] Menu bar: File (New Tree, Open Tree, Save, Save As, Exit), View (stub), Help (stub)
- [ ] Window title updates to current tree name

### 1.6 New Tree dialog
- [ ] `digitree/ui/dialogs/new_tree_dialog.py`
- [ ] Fields: Name, Description, optional device association (free text for now)
- [ ] "Start from Digimon defaults" checkbox — pre-fills standard stages (Stage I–VI), type tags (Vaccine/Data/Virus/Free), and a default requirement type set

### 1.7 Tree sidebar
- [ ] List of recently opened user trees (loaded from `config.json`)
- [ ] "New Tree" and "Open Tree" buttons
- [ ] Selecting a tree in the list opens it (loads XML, updates window title)
- [ ] Trees display name and modification date

### **Phase 1 Deliverable**
Running `python main.py` opens the app. The user can create a new tree (with or without Digimon defaults), which appears in the sidebar. Saving and reopening the app reloads the tree list. The `.dtree.xml` file is valid and inspectable. No entries or canvas yet.

---

## Phase 2 — Entry & Connection Editors (No Canvas)

Goal: Full data entry for a tree's contents via dialogs. A complete tree can be authored and saved entirely through forms. Verifiable by building a small test tree (5–10 entries, several connections with requirements) and confirming it saves and reloads correctly.

### 2.1 Stage / Type Tag / Requirement Type / Version editors
- [ ] `digitree/ui/dialogs/stages_editor.py` — list with add/remove/rename/reorder (drag), color swatch picker
- [ ] `digitree/ui/dialogs/type_tags_editor.py` — list with add/remove/rename, color swatch, short symbol field
- [ ] `digitree/ui/dialogs/req_types_editor.py` — list with add/remove/rename, value type dropdown (range / threshold / min_count / boolean), symbol field
- [ ] `digitree/ui/dialogs/versions_editor.py` — list with add/remove/rename, color swatch
- [ ] All editors accessible from a "Tree Settings" toolbar button (stub toolbar for now)

### 2.2 Entry editor dialog
- [ ] `digitree/ui/dialogs/entry_editor.py`
- [ ] Fields: Name, Stage (dropdown), Type Tags (checkboxes), Versions (checkboxes)
- [ ] Image / Sprite: file browse + clear, thumbnail preview (64×64)
- [ ] Device data: Library #, Power, HP, Sleep time
- [ ] Wikimon key: text field + "Test link" button (stub — just validates non-empty for now) + status display
- [ ] Notes: text area
- [ ] Save / Delete Entry / Cancel

### 2.3 Connection editor dialog
- [ ] `digitree/ui/dialogs/connection_editor.py`
- [ ] From / To entry selectors (dropdowns populated from current tree's entries)
- [ ] Versions checkboxes
- [ ] Style selector: Normal / Dashed-failure
- [ ] Requirement group builder:
  - Dynamic list of groups, each group is a collapsible section
  - Within each group: list of conditions (req type dropdown, value inputs vary by value_type)
  - Add/remove conditions within a group
  - Add/remove groups
- [ ] Save / Delete Connection / Cancel

### 2.4 Entries & connections list views (non-canvas)
- [ ] `digitree/ui/panels/entries_list.py` — table view of all entries in the current tree (name, stage, type tags, wikimon key status)
- [ ] Double-click row → opens Entry editor dialog
- [ ] "Add Entry" button → opens blank Entry editor
- [ ] `digitree/ui/panels/connections_list.py` — table view of all connections (from → to, version, has requirements)
- [ ] Double-click row → opens Connection editor dialog
- [ ] "Add Connection" button → opens Connection editor

### **Phase 2 Deliverable**
A complete Digimon tree (entries + connections with requirements + version tags) can be authored entirely through the UI with no canvas. Save/reload round-trips correctly. The entry and connection list panels display the full tree contents.

---

## Phase 3 — Graph Canvas

Goal: The tree renders as an interactive visual graph. Nodes are draggable, edges draw correctly, the canvas supports zoom/pan. Verifiable by loading the Phase 2 test tree and confirming it renders accurately and interactively.

### 3.1 GraphCanvas base class
- [ ] `digitree/widgets/graph_canvas.py` — `GraphCanvas(QGraphicsView)`
  - `QGraphicsScene` with zoom (Ctrl+scroll) and pan (middle-drag or space+drag)
  - Abstract `add_node(id, x, y)` and `add_edge(from_id, to_id)` interface
  - Node selection: click to select, Ctrl+click multi-select
  - Node drag: reposition by dragging
  - Context menu hook: `build_context_menu(node_id) -> QMenu` (override in subclass)
  - Fit-to-view: `fit_view()` method
  - Zoom in/out buttons and keyboard shortcuts (+/-)

### 3.2 GrowthTreeCanvas
- [ ] `digitree/widgets/growth_tree_canvas.py` — `GrowthTreeCanvas(GraphCanvas)`
- [ ] Entry card rendering:
  - Stage color band at top
  - Image (64×64, placeholder silhouette if none set)
  - Name label
  - Type tag badge
  - "W" badge if wikimon key is linked; warning icon if fetch failed
  - Version-exclusive entries: colored border (XA = blue, XB = green, both = none)
- [ ] Connection arrow rendering: directional arrow, with dashed style for failure evolutions
- [ ] Requirement label on arrow midpoint (compact notation, see spec Section 7.4)
- [ ] Hover tooltip on requirement label: full requirement text
- [ ] Clicking an entry → emits `entry_selected(entry_id)` signal

### 3.3 Auto-layout
- [ ] `digitree/layout/tree_layout.py` — `compute_layout(tree) -> dict[entry_id, (x, y)]`
- [ ] Stage-column mode: entries in the same stage share a horizontal band, spaced vertically
- [ ] Simple crossing-reduction: sort entries within each stage column by their connections to minimize crossing edges
- [ ] `networkx` used for DAG topology (finding layer assignments, cycle detection/warning)
- [ ] Auto-layout button in toolbar triggers layout computation and animates nodes to new positions

### 3.4 Stage column mode
- [ ] Toolbar toggle: "Stage Columns" on/off
- [ ] When on: entries are locked to their stage's horizontal band; drag is constrained to vertical movement within column
- [ ] Stage column headers rendered at top of each column (stage label + color band)
- [ ] Column widths auto-size to fit content

### 3.5 Version filter
- [ ] Toolbar dropdown "Version: [All ▾]" populated from tree's defined versions
- [ ] When a version is selected: entries/connections tagged to other versions are hidden (or dimmed — user-configurable)
- [ ] Canvas re-layouts if stage column mode is active

### 3.6 Canvas integrated into main window
- [ ] Replace canvas placeholder with `GrowthTreeCanvas`
- [ ] Canvas toolbar: Add Entry, Add Connection, Stages, Types, Reqs, Versions, Auto Layout, Fit View, Zoom+/-, Version filter, Show Requirements toggle
- [ ] Selecting entry on canvas → updates profile panel placeholder (show entry name for now)
- [ ] Node positions saved back to tree XML on save

### **Phase 3 Deliverable**
The tree renders on the canvas. Nodes are draggable, the layout auto-arranges, stage columns work, version filter works, connections draw with requirement labels. Clicking a node shows its name in the (still placeholder) profile panel. The full tree round-trips: edit in dialogs → auto-layout → drag to adjust → save → reload preserves positions.

---

## Phase 4 — Wikimon Integration & Profile Panel

Goal: Clicking a Digimon on canvas loads its full Wikimon profile. Data is fetched once and cached; the app works offline after that. Verifiable by fetching 3–5 Digimon from Wikimon, closing the app, disabling network, reopening, and confirming profile data still displays.

### 4.1 Wikimon scraper
- [ ] `digitree/wikimon/scraper.py` — `WikimonScraper`
  - `fetch_digimon(wikimon_key) -> WikimonData` — fetches and parses one Digimon page
  - `fetch_image(url, local_path) -> bool` — downloads and saves image
  - Rate limiting: minimum 2.0s between requests (tracked via `last_request_time`)
  - `tenacity` retry decorator: up to 3 retries with exponential backoff on network errors
  - Attempts MediaWiki API first (`/api.php?action=parse&page=...&prop=wikitext`); falls back to HTML scraping
- [ ] `digitree/wikimon/parser.py` — `parse_digimon_page(html) -> WikimonData`
  - Extracts: display name, JP name, level, attribute, type, elemental attr, fields, profile EN, profile JP, artwork URL, sprite URL, attacks (special + normal, with JP/romaji/EN names and descriptions)
  - Tolerant: missing sections set to `None`, `fetch_status` set to `"partial"` or `"ok"`
- [ ] `digitree/wikimon/models.py` — `WikimonData` dataclass

### 4.2 Cache integration
- [ ] `WikimonScraper.fetch_digimon()` checks cache first; only fetches if not cached or if `force_refresh=True`
- [ ] After fetch: `upsert_digimon()` + `upsert_attacks()` + download and cache images via `upsert_image()`
- [ ] `fetch_status` stored in DB; stale threshold: 30 days from `fetched_at`

### 4.3 Wikimon key editor (Entry dialog update)
- [ ] "Test link" button now actually fetches page title to validate key (shows spinner, then "✓ Valid" or "✗ Not found")
- [ ] "Fetch now" button triggers immediate fetch and refreshes profile panel
- [ ] Status line shows cache date and staleness

### 4.4 Profile panel
- [ ] `digitree/ui/panels/profile_panel.py` — `ProfilePanel(QWidget)`, ~320px wide, collapsible
- [ ] Connected to `entry_selected` signal from canvas
- [ ] Renders all states (Section 8 of spec):
  - No wikimon key → "Link to Wikimon" button
  - Key set, not fetched → "Fetch from Wikimon" button
  - Fetching → spinner
  - Fetched (ok) → full display: artwork, fields, profile text (collapsible), attacks, device data, sprite, wikimon cache status
  - Partial → data with "—" for missing fields, note "Some data unavailable"
  - Failed → error message + "Try again" button
- [ ] `[↗]` button opens Wikimon page in system browser
- [ ] `[W]` badge glows if cache is fresh, gray if stale (>30 days)

### 4.5 Batch fetch dialog
- [ ] `digitree/ui/dialogs/batch_fetch_dialog.py`
- [ ] Lists all entries in current tree that have a `wikimon_key` set
- [ ] Shows cache status for each (cached / stale / not fetched)
- [ ] Progress bar, cancel button
- [ ] Fetches sequentially with rate limiting; updates list as each completes

### **Phase 4 Deliverable**
Full Wikimon profile panel works end-to-end. Click any entry with a linked wikimon key → profile loads (fetching on first access, serving from cache on subsequent). Batch fetch works with progress display. App is fully functional offline once data is cached. Stale indicator appears correctly after 30 days.

---

## Phase 5 — PNG Export

Goal: The current tree canvas can be exported as a PNG at user-specified resolution up to 4000×4000. Verifiable by exporting a mid-size tree at 1×, 2×, and 4× scales and confirming pixel dimensions and visual accuracy.

### 5.1 Export engine
- [ ] `digitree/export/png_export.py` — `export_canvas_png(canvas, path, options)`
- [ ] Uses `QPainter` rendering onto `QImage` at target resolution
- [ ] Renders full tree extent (fit to content), not just current viewport
- [ ] Scale factors: 1× (screen resolution), 2×, 4× — output capped at 4000×4000 px; if tree at 4× would exceed 4000px, scale down to fit and warn user
- [ ] Background options: White, Transparent, Theme background color
- [ ] Stage column headers included/excluded per option

### 5.2 Export dialog
- [ ] `digitree/ui/dialogs/export_png_dialog.py`
- [ ] Options: scale (1×/2×/4×), background, include stage headers checkbox
- [ ] Preview: shows estimated pixel dimensions at chosen scale
- [ ] File picker for output path (defaults to `exports/[tree_name]_[date].png`)
- [ ] "Export" button — shows progress for large renders, then opens the output folder on completion

### 5.3 Menu integration
- [ ] File > Export > PNG Image… opens the export dialog
- [ ] Right-click on canvas > Export as PNG… (same dialog)

### **Phase 5 Deliverable**
Any tree can be exported as a PNG. The export dialog shows estimated dimensions, warns if capped at 4000px, and the output file is pixel-accurate at 1×, 2×, and 4× scale.

---

## Phase 6 — Route Finder

Goal: A bottom panel can compute and display all evolutionary routes between two chosen Digimon, with optional canvas highlighting. Verifiable by finding routes on a known device tree (e.g. DM Original) and confirming all valid paths match the known chart.

### 6.1 Route algorithm
- [ ] `digitree/logic/route_finder.py` — `find_routes(tree, from_id, to_id, version=None) -> list[list[entry_id]]`
- [ ] DFS from `from_id`, following outgoing connections; terminates at `to_id` or dead ends
- [ ] Version filter: skip connections not valid for selected version
- [ ] Results sorted by path length (fewest evolutions first)
- [ ] Cycle guard: skip any path that revisits a node

### 6.2 Route Finder panel
- [ ] `digitree/ui/panels/route_finder_panel.py` — collapsible bottom panel
- [ ] From / To dropdowns (entries in current tree)
- [ ] Version dropdown
- [ ] "Find Routes" button
- [ ] Results list: each route shows the chain with requirement summaries (compact notation)
- [ ] "Highlight on canvas" button per route: dims all non-route nodes/edges
- [ ] "Clear highlight" button
- [ ] "Copy as text" button: copies route chain to clipboard

### **Phase 6 Deliverable**
Route Finder panel fully functional. Routes compute correctly on a loaded tree. Canvas highlight dims non-route elements and clears correctly. Text copy produces readable output.

---

## Phase 7 — Device Presets

Goal: Built-in device preset trees can be browsed and loaded as editable copies. Verifiable by loading the DM Original preset and confirming entry count, stage structure, and connections match the known humulos.com chart.

### 7.1 Preset infrastructure
- [ ] `digitree/presets/` directory bundled with the app (not in `%APPDATA%`)
- [ ] Preset loader: `digitree/io/preset_loader.py` — discovers all `.dtree.xml` files in the bundled `presets/` directory
- [ ] Loading a preset creates a copy in the user's `trees/` folder; original is never modified
- [ ] "Reset to preset" option on Tree Settings reverts user copy to bundled original

### 7.2 Preset browser UI
- [ ] `digitree/ui/dialogs/preset_browser.py`
- [ ] Grid or list of preset cards: device name, brief description, entry count
- [ ] "Load Preset" button → copies to `trees/`, opens in canvas
- [ ] Accessible via File > Open Preset and sidebar "Open Preset" button

### 7.3 Preset data files (data entry task)
Compile each preset as a `.dtree.xml` using the established format. Source: humulos.com charts.
Priority order:

- [ ] `dm_original.dtree.xml` — Digital Monster Ver.1–6 (6 versions, combined chart)
- [ ] `dmx_xaxb.dtree.xml` — Digital Monster X Ver.XA/XB
- [ ] `dmx_xcxd.dtree.xml` — Digital Monster X Ver.XC/XD
- [ ] `dmx_xexf.dtree.xml` — Digital Monster X Ver.XE/XF
- [ ] `pen_original.dtree.xml` — Digimon Pendulum (Original)
- [ ] `pen_ver20.dtree.xml` — Digimon Pendulum Ver.20th
- [ ] `penz.dtree.xml` — Digimon Pendulum Z
- [ ] `penc.dtree.xml` — Digimon Pendulum Color
- [ ] `vbdm.dtree.xml` — Vital Bracelet Digital Monster
- [ ] `vbbe.dtree.xml` — Vital Bracelet BE

All preset entries should have `wikimon_key` pre-populated.

### **Phase 7 Deliverable**
At least the DM Original and DMX XA/XB presets are loadable from the preset browser, open on the canvas with correct structure, and can be saved as editable user copies. Entry count matches humulos.com data.

---

## Phase 8 — Polish & Completeness

Goal: The app is stable enough for daily use. Verifiable by a full end-to-end session: load a preset, fetch Wikimon data for all entries (batch), use Route Finder, export a PNG, edit the tree, save.

### 8.1 Undo/Redo
- [ ] `QUndoStack` wired to all mutating operations: add/delete/edit entry, add/delete/edit connection, drag node, auto-layout
- [ ] Ctrl+Z / Ctrl+Y shortcuts
- [ ] Undo history shown in Edit menu

### 8.2 Search
- [ ] `Ctrl+F` opens a search bar above the canvas
- [ ] Filters entry list and highlights matching nodes on canvas (non-matching nodes dimmed)
- [ ] Clears on Escape

### 8.3 Entry duplicate detection
- [ ] Warn (non-blocking dialog) when adding an entry whose name exactly matches an existing entry in the same tree

### 8.4 Dark / Light theme
- [ ] `QApplication.setStyle()` + custom palette toggle
- [ ] Theme stored in `config.json`
- [ ] Toggle via View > Theme menu

### 8.5 Settings screen
- [ ] `digitree/ui/dialogs/settings_dialog.py`
- [ ] Cache management: show cache DB size, "Clear wikimon image cache" button, "Clear all cached data" (with confirmation)
- [ ] Rate limit config: adjustable delay between Wikimon requests (default 2.0s)
- [ ] Default card size: Small / Medium / Large
- [ ] Wikimon image directory path (override default)

### 8.6 Missing / remaining presets
- [ ] Complete any remaining preset data files from Phase 7

### **Phase 8 Deliverable**
Full application is stable and usable. Undo/redo works across all operations. Search highlights entries. Settings screen functional. All priority presets from Phase 7 complete. App can be handed to a user with no further explanation needed.

---

## Dependency Summary

```
PySide6>=6.6.0
requests>=2.31.0
beautifulsoup4>=4.12.0
mwparserfromhell>=0.6.0
lxml>=4.9.0
Pillow>=10.0.0
networkx>=3.0
tenacity>=8.0.0
```

No PDF dependency. PNG export is handled entirely by PySide6's `QPainter` + `QImage` — no additional library required.
