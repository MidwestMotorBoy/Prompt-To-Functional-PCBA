# KiCad practice and scripting

Contents: 1. Board setup · 2. Net classes · 3. Custom rules (.kicad_dru) · 4. Zones · 5. Net ties and rule areas ·
6. Routing tools · 7. Checking: DRC, parity, renders · 8. Scripting with pcbnew (pitfalls) · 9. Script-based routing
lessons · 10. Hand-off etiquette

Written against KiCad 8–10. Check `Board Setup → Design Rules → Custom Rules → Syntax help` for the exact grammar of
your version.

## 1. Board setup

- Physical stack-up: layer count, thicknesses, copper weights matching the fab's stack (JLC publishes theirs).
- Constraints: minimum clearance, track width, via size/drill, annular ring, hole-to-hole, copper-to-edge, silk
  rules — copy from the fab's capabilities, then add margin.
- Pre-defined track widths and via sizes per net class for quick switching while routing.

## 2. Net classes

Group nets by electrical need and give each class width, clearance and via defaults, e.g.:

| Class | Width | Clearance | Via | Nets |
|---|---|---|---|---|
| HighCurrent | 2.5 mm (or pours) | 0.25 mm | 0.3/0.6 | pack, cells, switch nodes, VBUS, PPHV |
| Power | 0.8 mm | 0.2 mm | 0.3/0.5 | 5 V, 3.3 V rails |
| GateDrive | 0.4 mm | 0.2 mm | 0.3/0.45 | HO/LO, BST |
| Kelvin | 0.2 mm | 0.2 mm | 0.3/0.45 | sense pairs |
| Default | 0.2 mm | 0.15 mm | 0.3/0.45 | everything else |

Assign by name patterns (`*/SW1`, `/Cells and Gauge/CELL*`) so new nets inherit the right class.

## 3. Custom rules (.kicad_dru)

Use custom rules for constraints the board-setup table can't express. Rules live in `<project>.kicad_dru`:

```
(version 1)

# More clearance between high-current copper and small signals (pads keep their footprint spacing)
(rule "HighCurrent to small signals"
	(constraint clearance (min 0.25mm))
	(condition "A.NetClass == 'HighCurrent' && B.NetClass == 'Default' && A.Type != 'Pad' && B.Type != 'Pad'"))

# Component holes on 2 oz outer copper need a bigger ring
(rule "PTH annular ring 2 oz"
	(constraint annular_width (min 0.25mm))
	(condition "A.Type == 'Pad' && A.Pad_Type == 'Through-hole' && A.Hole_Size_X >= 0.5mm"))

# Copper-to-edge, except a connector whose land pattern reaches the notch
(rule "Edge margin"
	(constraint edge_clearance (min 0.25mm))
	(condition "A.Parent.Reference != 'J401'"))

# Differential pair geometry
(rule "USB pair"
	(condition "A.inDiffPair('/USB_D*')")
	(constraint diff_pair_gap (opt 0.15mm))
	(constraint track_width (opt 0.2mm)))
```

Notes: one `layer` token per rule (only the last counts); `severity` and `assertion` exist since v7;
`insideCourtyard()` is deprecated in favour of `intersectsCourtyard()`. A `zone_connection` rule did not change the
fill in KiCad 10's python/kicad-cli fills — set the connection on the pad/footprint instead.

## 4. Zones

- One zone outline per net per layer. Priority decides which of overlapping zones fills first; a lower-priority
  zone is cut around a higher one by clearance. Same-net zones with different priorities don't merge (the lower is
  knocked out); same-net same-priority overlaps raise `zones_intersect`.
- Zone settings: clearance, minimum width (removes slivers narrower than this), pad connection (solid / thermal /
  none), thermal gap and spoke width (spoke ≤ pad width; zone min width ≤ spoke width), island removal.
- Full-board plane: draw the outline inset ~0.5 mm from the edge. Give mounting holes a keep-out ring.
- Keep vias inside the zone outline; a via outside the edge makes a narrow neck.
- `connection_width` / minimum-width DRC warnings point only at the zone origin: find the neck by rendering the
  fill or by bisecting (remove footprints, refill, re-run DRC).
- Thermal vias inside exposed pads got thermal-relief rings and pinched planes: set `(zone_connect 2)` (solid) on
  those pads in the footprint.
- Refill zones before DRC (`kicad-cli` DRC refills; scripts must call the filler).
- Stitching-via arrays: after the fill, remove any via that doesn't land in its net's fill (or a same-net pad) on
  both F and B. Holder pegs, mounting holes and pad clearances leave dead spots that a grid can't see.
- Power-pour vias: set `via.SetRemoveUnconnected(True)` so In1/In4 clear the hole (0.15 + 0.2 mm), not the pad. A
  0.6/0.3 mm via grid then needs only ~1.0 mm pitch for a 0.3 mm plane web; with rings kept it needs 1.3 mm.
  `check_routing_rules.py` measures antipads the same way. Also call `via.SetKeepStartEnd(True)`: a scripted fill
  runs before connectivity is built, so without it the filler treats the via's F/B rings as unused, clears only
  the hole, and DRC then reports zone-to-via clearance errors.
- Items from `board.GetConnectivity().GetConnectedItems(item)` (the whole connected cluster) come back as base
  wrappers: call `.Cast()` before using type-specific methods (a via otherwise reports `GetClass() == "PCB_VIA"`
  but has no `GetWidth(layer)`). Ratsnest edges themselves aren't exposed to python, so build the missing
  connections from these clusters: per net, group pads into islands and join them nearest-first.

## 5. Net ties and rule areas

- **Net tie** footprints let two nets meet at one defined point (AGND–PGND at a pad, CSA–SW1, gauge VSS–GND at a
  shunt, a copper "link" replacing a 0 Ω). The DRC then flags any other contact.
- **Rule areas** (keep-outs) for antenna regions, mounting holes, board-edge zones; put them in the footprint when
  they belong to a part so they move with it.

## 6. Routing tools

- Interactive router: walkaround/shove modes; set track width per net class; use the differential-pair router for
  pairs and the length tuner for matching.
- Teardrops (v8+): add on narrow tracks into pads/vias for mechanical/etch robustness; not on RF lines.
- Stitching vias: place in a grid on fills; they must be on a net (GND) to connect.
- Freerouting (DSN/SES) exists but on dense power boards it routes across power stages and breaks DRC; prefer hand
  routing or a constrained custom router for critical nets.

## 7. Checking: DRC, parity, renders

- `kicad-cli pcb drc --schematic-parity --severity-all -o report.rpt board.kicad_pcb` — run after every stage;
  compare counts by type against the previous run (`scripts/drc_summary.py`).
- **kicad-cli and pcbnew saves rewrite `<project>.kicad_pro`** (key order, defaults, sometimes lost custom rules):
  back it up before and restore after, or the next DRC runs with default rules. If DRC suddenly shows copper-edge,
  clearance or drill errors everywhere, compare the `.kicad_pro` against git first.
- **kicad-cli lists at most 499 unconnected items** however many there are. Read the true count from pcbnew:
  `board.BuildConnectivity(); board.GetConnectivity().GetUnconnectedCount(False)`.
- Render PNGs (`scripts/render_board.py`) and look at them; the browser pane can't open local SVGs, PNGs work with
  the image viewer.
- If KiCad has the board open (`~board.kicad_pcb.lck`), tell the user to revert/reload before saving after a
  scripted change, or their save overwrites it.
- **Trial DRC with other constraints** (what would the fab's numbers flag? does this re-layering add anything?):
  copy the board into a scratch folder *as `<project>.kicad_pcb` with the real `.kicad_pro`, `.kicad_dru` and
  `fp-lib-table` beside it* (without the lib table every footprint reports `lib_footprint_issues`), edit the
  constraint in the copied `.kicad_pro` (`"min_clearance"`, `"min_track_width"`, `"min_hole_to_hole"` …), run DRC
  there and diff the item lists against a baseline run. Compare whole items (type line plus the `@(…)` lines), not
  counts.
- **Check `.kicad_dru` against git before trusting a DRC run.** It turned up empty (0 bytes) after a GUI session
  once, and DRC then silently ran without the annular-ring, edge and high-current rules.
- `pcbnew.LoadBoard()` returns `None` for a file whose name doesn't end in `.kicad_pcb` (a backup copy named
  `pcb.before_x` renders nothing): copy it to a `.kicad_pcb` name first.
- `hole_to_hole` errors between same-net vias are real for the fab too: a 0.508 mm via pitch with 0.3 mm drills
  leaves 0.208 mm of material; use 0.635 mm or more.

## 8. Scripting with pcbnew (pitfalls)

- Use KiCad's bundled python (`C:/Program Files/KiCad/10.0/bin/python.exe` on Windows); run scripts with `-I`
  (isolated) and never name a script after a stdlib module (`bisect.py`, `random.py` shadow imports).
- **One board per process**: a second `LoadBoard()` after a save can return a dead wrapper.
- **Mass removal kills wrappers**: removing hundreds of items via pcbnew makes later calls return dead SWIG objects.
  Strip old `(segment …)`/`(via …)`/`(zone …)` blocks from the file as text (balanced-paren scan matching their
  uuid) *before* `LoadBoard`.
- **Groups are write-only from python** in KiCad 10 (`GetItems()` returns bare SwigPyObjects): keep a sidecar file
  of the uuids your script added and delete those on the next run — makes scripts re-runnable.
- **`PCB_VIA.GetWidth()` without a layer argument raises an assert dialog that hangs a headless script**: always
  `GetWidth(pcbnew.F_Cu)`. Find such hangs with `python -X faulthandler` and `faulthandler.dump_traceback_later(30)`.
- `board.GetBoardPolygonOutlines(polyset, False)` needs the bool; `SHAPE_POLY_SET.Collide/Contains/Inflate` work;
  `pad.GetEffectivePolygon(layer, pcbnew.ERROR_INSIDE)` gives the exact pad shape; `zone.GetFilledPolysList(layer)`
  the fill.
- `pcbnew.ExportSpecctraDSN` / `ImportSpecctraSES` work, but SES import replaces every track and via.
- A scratch copy saved under a new name gets default rules (min connection 0): DRC on it is meaningless unless you
  copy the real `.kicad_pro` and `.kicad_dru` beside it.
- Write any script containing backslashes with a file-writing tool, not a shell heredoc (heredocs can halve
  backslashes and corrupt regexes or KiCad text).
- Footprints: changing a symbol's footprint field then reloading the footprint on the board at its old position is
  the clean way to swap packages; check parity afterwards.
- **Removal order**: `board.Remove()` of *any* item before later reads (even one Edge.Cuts shape) can make
  `board.GetTracks()` raise `TypeError: 'SwigPyObject' object is not iterable`. Read everything into lists first,
  remove last, save. Removing ~30 board-level `gr_text` items through the API poisons `footprint.Reference()`
  (no `SetVisible`): strip `gr_text` blocks as text before `LoadBoard`.
- **Footprint fields in KiCad 10**: `f.HasField("LCSC")`, `f.GetFieldText("LCSC")`, `f.GetFields()`; there is no
  `GetFieldByName`/`HasFieldByName`. `str()` every wxString before `format()` (`UTF8.__format__` fails).
- **Teardrops have no CLI or python path** (no `TEARDROP_MANAGER` in pcbnew, nothing in kicad-cli): they are
  generated in the editor, Edit → Edit Teardrops (scope PTH pads / SMD pads / vias / track-to-track, "Add with
  default values") then save. With the user's KiCad open this can be driven through the desktop (computer-use:
  the PCB Editor window must be frontmost; `open_application` brings it forward); the save rewrites `.kicad_pro`
  with last-used via/zone defaults, harmless. 4000+ teardrop zones on a 430-part board; DRC unchanged.
- **Refill before plotting**: `pcbnew.ZONE_FILLER(board).Fill(board.Zones())` then `Save()` (restore the
  `.kicad_pro`), so the gerbers carry current fills; the GUI save does not refill by itself.
- `shutil.rmtree` on a folder the shell's cwd is inside fails silently on Windows; delete files individually.
- Saved zone fills are stored fractured (one outline, no holes), so web/neck analysis on `GetFilledPolysList`
  finds nothing; rasterise or bisect by removing items on copies (`connection_width` DRC items carry only the zone
  origin, also in JSON).
- Legend text below the board's `min_text_height` 0.8 / thickness 0.15 (JLC floor) is a DRC error: abbreviate
  and rotate labels instead of shrinking them; 0.8 mm text does not fit between loops on a 2.54 mm grid.

## 9. Script-based routing lessons

- Map every pad of an area first (render by net, dump pad boxes), then write zone polygons/tracks with explicit
  coordinates and check clearances before running. One area at a time; DRC and render after each.
- Power as zones (one outline per net per layer), mirrored on the opposite outer layer, stitched. Cap ground pads
  surrounded by another net's pour get a small ground "pocket" zone with their own vias to the plane.
- Placement may need small fixes for routing (turn a sense resistor so current flows straight, move a filter part
  out of the current path): fix placement, not the route.
- Gate drive: keep each gate and its return as a side-by-side pair on F.Cu where possible. If a pair must go
  inner, both run side by side on the same Manhattan layer, in that layer's direction. Stacking on In2/In3 doesn't
  work, because they run at right angles. Keep bootstrap loops on the outer layer without vias. Count lanes and
  check order before coordinates.
- Kelvin taps from the resistor pad's quiet end; route the pair together; never let a router connect a sense line
  to nearby copper of the same net.
- A maze router (A*) on a 0.1 mm grid with obstacles = other-net copper grown by clearance + half width, the
  ground plane layers excluded, and per-layer costs, routes a dense board's small signals far better than
  Freerouting; bucket hole positions for fast via-spacing checks.
- Make such a router obey `routing-discipline.md`:
  - on the inner pair, allow only vertical moves on one layer and horizontal moves on the other, so a turn costs
    a via;
  - cap the path length on F.Cu/B.Cu for signal nets (escapes only);
  - when a via is placed, reserve a GND via site within 1 mm.
  Run `check_routing_rules.py` on the result.
- **Verify every scripted copper change with a real DRC, not a home-made clearance test.** A segment-vs-segment
  check that moved three paths from the plane to In3 missed two crossings and a 30 mm track that ended on two
  GND vias; the next DRC found them. Pattern that works: apply the change to a copy (section 7, trial DRC),
  accept only when no item is new and nothing becomes unconnected, else revert that change.
- **Never "tidy" track ends board-wide** (snap to via centres etc.): hand routes have hundreds of ends a few
  hundredths off centre, and moving them all broke clearances elsewhere. Snap only the ends DRC names.
- **GND reference vias**: never drop them inside another net's pour (they cut power paths; the user reverted a
  353-via pass for exactly that). Place only in GND copper or empty board, and ask before a board-wide pass.
- When one connection has no clean layer on its current path (In2 is a pour, B.Cu is a pour, In3 crosses
  another net), the answer is a different path (over the top, from the net's other end), not forcing the plane
  layer; the A* router also fails there because the zone fills are obstacles, so map the corridor by hand.
- **A real DRC is necessary and still not enough.** A legal signal via in a pour neck, or a short signal hop on a
  power-plane layer, can pinch or cut a power path while every rule, the open-connection count and the
  plane-island check stay clean. After every scripted change near power copper run the solver loop in
  `solver-verified-layout.md`, and make the link search test new vias and tracks against the pours they land in.
- A router that can't finish a net reports the two *groups* it couldn't join; list the whole net's tracks,
  vias and pads first (`GetTracks()` filtered by net) so you know which ends are free.

## 10. Hand-off etiquette

- Work on a copy (branch/worktree) when the user is editing the same board in KiCad.
- Commit scripts that generate copper; record decisions (pour plan, stack-up) in project docs.
- **After a user's hand-routing round, check; don't reroute.** Back up their save, run DRC (with parity, zones
  refilled), `check_routing_rules.py` and the measurements below, and report findings with coordinates and the
  fix each needs. Leave the copper to them unless they ask. Silkscreen, docs, fab outputs are fine to do. If a
  script already touched the board, restore their save byte-for-byte and say so.
- Worth measuring in such a review (all cheap in pcbnew): straight-line driver-pin-to-gate distance and gate track
  width per gate net; narrow tracks leaving shunt pads (Kelvin taps start *inside* the pad polygon); HF caps on
  the switch nets within a few mm of the FETs; GND vias at low-side source pads; via count per high-current net;
  tracks on plane layers; via rows under 0.3 mm plane webs; holder/connector polarity marks vs pad nets (marks
  owned by the footprint rotate with it, so they are right by construction); fill polygons intersecting antenna
  keep-out rule areas (test fills, not only tracks).

## 11. Fab outputs (JLCPCB)

- `kicad-cli pcb export gerbers --layers F.Cu,In1.Cu,…,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts
  --subtract-soldermask --no-x2 --no-netlist --precision 6` (Protel extensions are the default) and
  `kicad-cli pcb export drill --format excellon --excellon-units mm --excellon-zeros-format decimal
  --excellon-separate-th --drill-origin absolute --generate-map --map-format gerberx2`; zip the folder. Both
  rewrite `.kicad_pro`. Refill zones and save first (section 8).
- **Assembly BOM** (`Comment, Designator, Footprint, LCSC Part #`): **one line per LCSC number.** JLC's BOM tool
  marks every line "Unconfirmed — multiple lines in the BOM have been matched to the same part" when two lines
  share a number (10k vs "10k 1%", RAC vs RBAT shunts, WAKE vs RESET switches). Join the values in the Comment.
- **CPL** (`Designator, Mid X, Mid Y, Layer, Rotation`): footprint position in mm with **Y negated** (KiCad's
  own position export does the same), `Top`/`Bottom`, KiCad rotation plus JLC's offset for that part.
- **Rotation offsets are per LCSC part, and only JLC's placement preview is the truth.** The community table
  (matthewlai/JLCKicadTools `cpl_rotations_db.csv`) was wrong for 4 of the 5 families it matched here (6.3 mm
  electrolytics 0 not 180, SOT-23 180 not −90, a TI VQFN-32 and WQFN-38 0 while a TI VQFN-36 and VQFN-20 need
  270). Method that worked: upload once with plain KiCad angles, screenshot the preview, crop every keyed part
  (PIL, board-mm → pixels from the outline box) beside KiCad's pad-1 side (`pad.GetPosition() - fp.GetPosition()`),
  read the magenta pin-1 dot / cathode bar, and record the offset keyed by LCSC number in the exporter; a second
  upload confirms. Parts too small to read at ~10 px/mm (SOD-323/523 diodes, 0603 LEDs) stay flagged for the
  user. JLC's red designator text renders upside-down regardless of rotation: ignore it, read the dot.
- **Position offsets are per part too**: JLC places at its own footprint origin, which for some parts is not the
  body centre (a SOT-89 LDO sat 0.75 mm toward its leads, a PDFN-8 FET 0.5 mm along its lead axis). Keep an
  offset in the KiCad footprint frame, rotate it with the part (KiCad angle is CCW on a y-down screen:
  `x += ox·cosθ + oy·sinθ; y += −ox·sinθ + oy·cosθ`) and add it before negating Y. Derive the direction from a
  *zoomed* JLC preview (body edge vs pad row) on two different rotations; a whole-board screenshot is too coarse
  (0.13 mm/px) and misled the first attempt.
- Leave out and list separately: DNP (`FP_DNP`), hand-fit (`FP_EXCLUDE_FROM_POS_FILES`), `FP_EXCLUDE_FROM_BOM`
  and anything without an LCSC number (a module bought direct from TI, a connector to be chosen later). Check
  that list against the README: a part the docs say JLC places but which is `exclude_from_bom` on the board (the
  test-point loops here were actually plain pads) is a doc/board mismatch to report.
- **Stock check**: POST `{"keyword": "<Cxxxx>", "currentPage": 1, "pageSize": 5}` to
  `https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList`; match
  `componentCode`, read `stockCount`, `componentLibraryType` (`base` = basic), `preferredComponentFlag`,
  `componentPrices[0].productPrice`. Run it over the whole BOM before an order (`hardware/DevBoard/tools/jlc_stock.py` in this repo).
- JLC's "BOM Matching" export (`…-JLCPCB Assembly Order.xls`) is really xlsx: unzip, read `xl/sharedStrings.xml`
  and `xl/worksheets/sheet1.xml`; column K "Warning" says why a line is unconfirmed.
