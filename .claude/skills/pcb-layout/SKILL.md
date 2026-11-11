---
name: pcb-layout
description: Practical, source-backed method for PCB layout — floorplanning and placement, multilayer stack-ups and plane assignment, return paths and grounding, switching-converter hot loops and gate drive, high-current pours and vias, thermal design, Kelvin sensing, mixed-signal and battery-gauge layout, USB/I2C/differential pairs, RF/antenna modules, ESD and connectors, DFM for JLCPCB, and KiCad zone/DRC/python workflow. Use this skill whenever the task involves placing parts, planning or drawing copper pours, choosing a layer stack-up, routing (by hand or by script), reviewing or critiquing a board layout, fixing DRC, preparing a board for fabrication, or answering "how should I lay this out" questions — even if the user only says "route this", "pour plan", "which layer", "is this layout OK", "ground plane", "thermal vias", "hot loop", or names a KiCad board file.
---

# PCB layout

This skill turns a placed-or-unplaced schematic into a manufacturable, quiet, cool board. It is written for
multilayer boards with power conversion and some low-level analog (chargers, battery packs, motor drives, sensor
boards), laid out in KiCad and built at JLCPCB-class fabs, but the physics applies to any tool.

The single idea under almost every rule here: **current flows in loops, and the return half of the loop is part of
the circuit.** At DC it takes the path of least resistance; above a few kHz it takes the path of least inductance,
which is the copper directly under (or beside) the outgoing conductor. Loop area is inductance; inductance is
ringing, voltage spikes, radiated emissions and coupling into neighbours. Most layout decisions are really
decisions about where the return current will flow — so ask that question first, every time.

## How to use this skill

1. Read the **workflow** below and follow it in order; it is the order that avoids rework.
2. For each step, open the matching reference file. They are long and detailed on purpose; read the one you need,
   not all of them:

| Topic | File | Read when |
|---|---|---|
| Stack-up, plane assignment, layer roles | `references/stackup-and-planes.md` | Choosing layer count/order, deciding what goes on each layer, writing a pour plan |
| Return paths, grounding, splits, stitching, EMC | `references/return-paths-and-grounding.md` | Any ground-plane question, analog/digital or AGND/PGND, crossing a gap, layer changes |
| Floorplan and placement | `references/placement.md` | Before and during placement; when a layout "looks random" |
| Switching converters | `references/power-conversion.md` | Buck, boost, buck-boost, gate drivers, bootstrap, snubbers, FB/COMP, current-sense filters |
| High current and thermal | `references/high-current-and-thermal.md` | Trace/pour widths, via counts, battery paths, thermal pads, solid vs relief |
| Signals and interfaces | `references/signals-and-interfaces.md` | Kelvin sense, gauges/ADCs, I2C/SMBus, USB, differential pairs, crosstalk, length |
| RF and antenna modules | `references/rf-and-antennas.md` | BLE/Wi-Fi modules, chip antennas, matching networks, 50 Ω feeds |
| ESD, TVS and connectors | `references/esd-and-connectors.md` | Placing TVS/ESD parts, USB-C/headers, cable entry |
| Manufacturing (DFM/DFA) | `references/dfm-jlcpcb.md` | Rules, vias, mask, paste, fiducials, panel, before ordering |
| Routing discipline (house rules) | `references/routing-discipline.md` | **Before any routing**: inner Manhattan layer pair, outer layers local only, fan-out first with 1.5 mm clear, planes untouchable, GND via at every layer change, one width per net and direct routes |
| KiCad practice and scripting | `references/kicad-practice.md` | Zones, net classes, custom rules, net ties, python/pcbnew automation, DRC |
| Review checklist | `references/review-checklist.md` | Before routing, after routing, before ordering, when asked to review a board |
| Solver-verified layout | `references/solver-verified-layout.md` | **Before any scripted routing pass and after any edit near power copper**: the check loop that finds what DRC cannot (cut or pinched power paths, Kelvin taps, loop inductance, coupling), the order of work for a scripted layout, and the solver tools in this repo |

3. Use the scripts in `scripts/` for things that should be deterministic (see **Scripts**).
4. For doing the work by program, the sibling skills go deeper: `pcb-scripted-placement` (placer and placement
   checks), `pcb-scripted-routing` (router, cleanup pass, tidiness measure), `pcb-loop-and-coupling-solvers` and
   `pcb-copper-resistance` (the solvers behind the check loop), `pcb-proto-flow` (the whole flow and its gaps).

## Workflow

### 0. Gather the facts before touching copper

- Every IC's datasheet **layout section** and the vendor **EVM layout** (they encode the vendor's measured
  experience — copy their loop topology, not just their parts).
- Currents per net (continuous and peak), voltages per net (for clearance and cap derating), switching
  frequencies and edge rates, which nets are sensitive (sense lines, references, feedback, crystals, antenna feed).
- Fab capabilities for the chosen copper weights (see `dfm-jlcpcb.md`); mechanical constraints (outline, mounting
  holes, connectors, keep-outs, height).
- Write these down in a short table; you will refer to it at every later step.

### 1. Choose the stack-up and write a per-layer plan

Decide layer count and order from the objectives in `stackup-and-planes.md` (every signal layer adjacent and close
to a plane; at least one solid unbroken ground plane; high current on thick outer copper; sensitive routing on
buried layers next to ground). Then write a **pour plan**: one line per layer saying what it carries and what it
must never carry. Agree it with the user before routing — it is cheap to change now and expensive later.

### 2. Floorplan, then place

Mechanical parts first and locked (connectors, holders, holes, antenna edge). Then blocks in signal/power-flow
order, power stages before their controllers, support passives at the pins they serve, test points last.
Placement decides 80 % of layout quality: a hot loop or a Kelvin connection cannot be fixed by routing. Follow
`placement.md`; render the result (see scripts) and look at it before routing.

### 3. Route in priority order

Read `routing-discipline.md` first; its rules hold at every step below.

0. **Fan out every dense IC** (more than 20 pins, or pitch under 0.8 mm): an escape and a via per signal pin,
   inside the 1.5 mm area kept clear at placement. Do this before any other net, so the vias of other nets can't
   crowd it.
1. **Hot loops and switch nodes** (power-stage copper, as compact pours).
2. **High-current paths** (pours on outer layers, mirrored, stitched).
3. **Ground**: plane(s), stitching, every IC ground pad/thermal pad straight down with vias.
4. **Critical small signals**: Kelvin sense pairs, gate drive (drive + return paired), feedback, references,
   RF feed, crystals, differential pairs.
5. **Everything else**, shortest first, on the inner Manhattan pair: one layer vertical only, its partner
   horizontal only, and turns made by a via between them. Outer layers carry only escapes and short local links.
6. **Fills**: GND fill on remaining area of signal layers, stitched; remove slivers and islands.

Run DRC and `check_routing_rules.py` after each stage, not only at the end, and render the result. Each stage changes what the next one can do.

After any stage or hand edit that puts a track or via within a few millimetres of power copper, also run the
check loop in `solver-verified-layout.md` (plane pieces, power-path resistance on the fine grid, Kelvin taps, then
loop inductance and coupling after each pass). A legal signal via can pinch a power pour, and no rule reports it.

### 4. Review and fix

Walk `review-checklist.md` and run the full solver loop of `solver-verified-layout.md` on the finished file,
comparing every number with the previous run. Fix in the order: electrical correctness (shorts, opens, parity) → hot loops and
returns → current capacity → sensitive signals → DFM → cosmetics/silkscreen. After a round of the user's own
hand routing, check and report only (`kicad-practice.md` §10); they decide what moves.

### 5. Fab outputs

Refill zones, plot gerbers and drills with the fab's settings, write the assembly BOM (one line per part
number) and position file, list the hand-fit/DNP parts, stock-check every part number, and do one last
"critical only" pass (what stops it working, what the fab rejects). Recipes: `kicad-practice.md` §11,
`dfm-jlcpcb.md` §9.

## Core rules (the ones that matter most)

These are summaries; the reference files give the reasoning, numbers and sources.

- **The ground planes are untouchable.** On a 6-layer board L2 and L5 are solid GND: no traces, no splits, no
  other-net islands, no via rows whose antipads merge into a slot. One continuous ground, partitioned by
  placement and routing discipline (Ott). If a second ground must exist (a battery gauge's VSS across a shunt,
  AGND), pour it locally on the outer and signal layers, never on a plane, and join it at exactly one point.
- **Inner signal layers are a Manhattan pair**: L3 vertical, L4 horizontal, direction changes only by a via to
  the partner. Outer layers are free-angle but only for escapes, short local links, decoupling and power.
- **Dense ICs get 1–1.5 mm clear all round** (only decoupling caps inside; bootstrap/filter/FB parts just outside), and they are fanned out before any other
  net is routed.
- **Every signal layer gets an adjacent reference plane, close.** A trace's return runs in the nearest plane;
  when a trace changes layers and the reference plane changes, put a ground (stitching) via within 1 mm of the
  signal via. Never route across a gap in the adjacent plane.
- **Hot loop = input/output capacitor + the half-bridge.** Place the smallest high-frequency ceramic so its pads
  sit at the high-side drain and the low-side source; put a solid ground plane on the layer directly beneath.
  Make switch-node copper only as large as current requires.
- **Gate drive is a loop too.** Route gate and its return (source/SW or PGND) side by side on one layer, short,
  away from sense lines.
- **Kelvin sensing**: sense traces leave from the resistor pads themselves (not the current-carrying copper), run
  as a tight pair, away from switch nodes, filter at the IC.
- **High current goes in pours on the thick outer layers**, mirrored top and bottom and stitched; size with
  IPC-2152 data and leave margin for the ±20 % etch tolerance; enough vias at every layer change (~1 A per 0.3 mm
  via is a conservative planning figure).
- **Decoupling**: cap → via → plane with the shortest possible loop; own vias per cap, at the pad.
- **Exposed pads**: thermal via arrays into the ground planes, solid connection, follow the land pattern.
- **TVS/ESD**: at the connector, in the path (no stub), with a short fat ground to the plane.
- **Antenna modules**: board edge, no copper on any layer under the antenna, solid ground either side.
- **Respect the fab's minimums but don't design at them**; relax wherever density allows.
- **A clean DRC is not a correct board.** Four real faults in one scripted layout passed DRC, parity and the
  open-connection count: a cut power bus, a pinched one, Kelvin taps reading plane drop, and a bulk capacitor cut
  off from its regulator. Each was a legal track or via of *another* net. Solve the power paths, the taps and the
  loops after every edit near them, and compare with the run before (`solver-verified-layout.md`).
- **Legal and working is still not finished.** A board also has to look intended to the person who opens it:
  one width per net, direct routes, few bends, nothing at an odd angle. A script-routed board passed DRC and
  every solver and failed this in the first minute. Measure it (`routing-discipline.md` section 7) after every pass.
- **Reserve signal corridors at placement.** Slow signals that must pass between power stages need a lane and a
  via site on a signal layer before the stages close around them, or they end up cut into a ground plane.

## Working with the user

- Layout is full of trade-offs (density vs thermal, cost vs layer count, a nicer loop vs a harder escape). State
  the trade-off and recommend, rather than silently choosing.
- Prefer showing over telling: render the board region you changed (see scripts) and look at it yourself before
  reporting.
- Treat the vendor's EVM and datasheet layout as the default; deviate only with a reason you can state.
- When a rule here conflicts with a datasheet, the datasheet wins for that part — note the conflict.
- Record decisions (pour plan, stack-up, deviations) in the project's docs so the next session doesn't re-derive
  them.

## Scripts

All scripts run with KiCad's bundled python (it has `pcbnew`, `PIL`, `numpy`):
`"C:/Program Files/KiCad/10.0/bin/python.exe" -I <script> ...` on Windows; adjust the path elsewhere.

| Script | Does |
|---|---|
| `scripts/render_board.py board.kicad_pcb out.png [x0 y0 x1 y1] [px_per_mm] [--layers F.Cu,In1.Cu,...]` | PNG of courtyards, pads coloured by net, refs, zones (rule areas red), tracks and vias of the chosen layers. Coordinates relative to the board outline's top-left. Look at it with the image viewer. |
| `scripts/drc_summary.py board.kicad_pcb [--baseline report.rpt]` | Runs `kicad-cli pcb drc --schematic-parity`, restores the `.kicad_pro` (kicad-cli rewrites it), prints violation counts by type, and the difference from a baseline report. |
| `scripts/check_routing_rules.py board.kicad_pcb [--vertical In2.Cu --horizontal In3.Cu --planes In1.Cu,In4.Cu]` | Checks `routing-discipline.md`: inner-layer direction, tracks/other-net zones/via-row slots on the planes, long outer-layer signal runs, signal vias without a GND via within 1 mm, and parts inside the fan-out ring of dense ICs (1.5 mm; 1 mm for small fine-pitch parts). Run it on the placement (fan-out room) and after every routing stage. |
| `scripts/net_extents.py board.kicad_pcb [regex]` | Pad count, bounding box and refs per net: the starting point for a pour plan and for sizing high-current paths. |

The field solvers (copper resistance, Kelvin taps, via current, loop inductance, coupling) and the scripted-edit
helpers are not in this folder. They are in `hardware/Production/groundup/` and its `compare/` folder, with tables
written for the Monolith board; `solver-verified-layout.md` §6 lists them and what to fill in for another board.

Read `kicad-practice.md` before scripting board edits: KiCad's python has sharp edges (saves rewrite the project
file, mass removals kill wrappers, `GetWidth()` on a via without a layer hangs).
