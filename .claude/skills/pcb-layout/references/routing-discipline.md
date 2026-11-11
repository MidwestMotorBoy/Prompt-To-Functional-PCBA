# Routing discipline: layer directions, fan-out first, untouchable planes

These rules come from the user's review of an earlier pour plan. They are the house rules for routing on this
project, and they are a good default on any multilayer board. `scripts/check_routing_rules.py` checks all of
them on a KiCad board. Run it after every routing stage, alongside DRC.

Layer names below use L-numbers for a 6-layer board. The KiCad equivalents are L1 = F.Cu, L2 = In1, L3 = In2,
L4 = In3, L5 = In4, L6 = B.Cu. On other layer counts, apply the same roles. Planes are the layers next to the
outer layers, and each pair of buried signal layers between them is a Manhattan pair.

## Contents
1. Inner signal layers are a Manhattan pair · 2. Outer layers are free-angle but local · 3. Fan out
fine-pitch parts first · 4. The ground planes are untouchable · 5. Reference changes · 6. Scripted routing ·
7. Width and shape: tracks that look intended · 8. Checklist

## 1. Inner signal layers are a Manhattan pair

- **L3 (In2) is vertical-preferred and L4 (In3) is horizontal-preferred.** Every segment on L3 runs along Y and
  every segment on L4 runs along X. There are no diagonals and no "just this once" jogs.
- **Change direction only by a via to the paired layer.** A net that must turn goes L3 vertical, then a via,
  then L4 horizontal. It never turns within one layer.
- Why:
  - Two buried signal layers with no plane between them couple broadside. Crossing at 90° keeps that coupling
    to a point at each crossing instead of a long parallel run.
  - Fixed directions keep the routing channels open. Each layer's tracks pack in parallel lanes, so the next
    net always has a lane, and the board stays routable to the end.
  - The result is predictable and easy to review by eye or by script.
- Plan lanes at the start: count how many nets must cross each region on each axis, and leave channels at
  placement for them.
- The direction rule covers traces only. A local copper pour on L3/L4 (GND fill, a small rail island) isn't a
  route. Pours still keep off the planes, as section 4 says.

## 2. Outer layers are free-angle but local

- L1 and L6 (F.Cu, B.Cu) allow any angle; use 45° or arcs, never acute angles. Use them for:
  - component escapes and fan-out stubs;
  - short local connections inside a block (a few mm, pad to pad, part to its via);
  - decoupling: cap to pin, cap to via;
  - power pours, hot loops, gate-drive pairs and Kelvin pairs, which belong at the parts.
- **Don't run long signals on the outer layers.** Anything that leaves its block drops to L3/L4 through a via
  near the part and travels in Manhattan style.
- Why: the 2 oz outer layers need wider minimum gaps, so traces there waste area. They also carry the power
  pours, sit nearest to probes, fingers and ESD, and radiate more than buried layers.
- Trace length is a goal, never a hard rule (the user's words). `check_routing_rules.py` lists outer-layer signal
  runs longer than `--outer-max` (default 15 mm) as advisory notes to review, not as violations.
  Power, gate-drive and Kelvin nets that must stay at their parts are exceptions, and you can whitelist them.

## 3. Fan out fine-pitch parts first

- **Keep 1–1.5 mm clear around any IC with more than 20 pins (1.5 mm), and ~1 mm round smaller ICs with a pin
  pitch under 0.8 mm.** (The user first set 3 mm, then cut it to 1–1.5 mm: 3 mm cost too much board space and
  placement time for little routing gain.) The clear
  area is measured from the IC's courtyard. No other part's courtyard enters it, so every pin has room to
  escape and drop a via.
- **Exception: decoupling caps** go as close to their pins as DRC allows, inside the ring. Nothing else is exempt: bootstrap, sense-filter and FB parts sit just
  outside the ring (still within a few mm of their pins), because a part parked against a pin row blocks every
  escape behind it and the router then fails there. The checker
  treats a cap that shares a supply/ground net with the IC as decoupling.
- **Fan out these ICs before routing any other nets.** Give each signal pin a short escape and a via, staggered,
  so each pin can reach L3/L4. Then route the rest of the board. If fan-out comes later, the vias of other nets
  fill the space, and the dense part becomes unroutable.
- This extends `placement.md` §7 (escape channels): the rule sets the channel at 1–1.5 mm all round.

## 4. The ground planes are untouchable

- **L2 and L5 (In1, In4) are solid GND planes.** They carry no traces, no splits, no other-net islands and no
  rows of vias.
- A second ground (battery-gauge VSS, AGND, chassis) **does not go on a plane layer**. Pour it as local fill on
  the outer layer under its parts, plus fill on the signal layers if needed. Keep L2/L5 solid system GND under
  it, and join the second ground only at its single point (shunt pad or net tie). The gauge's small currents
  don't need a plane of their own. What matters is that pack current never flows in the gauge's copper.
- **Vias through the planes:**
  - Through vias necessarily pierce L2/L5. Each one leaves an antipad, so arrange them so the plane stays whole.
  - Never put vias in a straight row whose antipads merge into a slot. Stagger high-current via arrays, and keep
    at least a 0.3 mm copper web between neighbouring antipads.
  - Keep via fields out from under critical traces on the adjacent layers.
  - Render each plane layer alone after placing any via array.
- **Don't route a signal across a gap in its adjacent plane.** That includes accidental gaps (antipad slots,
  cut-outs and keep-outs).

## 5. Reference changes

- A signal that changes layer usually changes reference plane. L1 and L3 reference L2; L4 and L6 reference L5.
- **Every such layer change gets a GND via within 1 mm of the signal via.** That via carries the return current
  between the planes. The checker reports signal vias with no GND via within 1 mm.
- L3 ↔ L4 swaps (a direction change) also change reference plane, from L2 to L5. They need the GND via too.

## 6. Scripted routing

- A script router must generate axis-aligned segments per layer: only vertical on L3, only horizontal on L4.
  At a turn it places a via, then continues on the other layer.
- On the outer layers, keep the router to short escapes. Cap the outer-layer path length for signal nets, and
  give each one a via down to the Manhattan pair near its pad.
- Put the plane layers out of bounds for the router. Never pass them as routing layers.
- Only a via whose net leaves on both sides of the stack needs a GND via within 1 mm: F and L3 both reference L2;
  L4 and B both reference L5. An F ↔ L3 via needs none. Choose the GND via site with the route's own copper in
  mind, before drawing it, then place it right after. Otherwise the route's own tracks take the room.
- Order (each step claims space the next would otherwise take):
  1. fan-out of the dense ICs (section 3);
  2. hand-planned links where pins face each other (e.g. a PD controller to its CC protector);
  3. Kelvin pairs, routed pad to pad from the sense resistor's own pads (never from its pour, which could start
     anywhere), the second leg drawn toward the first;
  4. gate-drive pairs on F and L3 only (one reference plane, so no GND reference vias), drive beside return,
     kept clear of the inductor and switch node;
  5. dense corners on a fine grid in a small region;
  6. the rest of the board;
  7. fills and stitching.
- Grid routers lose 0.4-0.5 mm-pitch pins: the clearance halos of the neighbouring pins cover every grid cell
  of the pin. Use exact escape stubs instead, checked against real shapes: straight out of the package, inward
  onto a same-net exposed pad, or a 45-degree dogleg past a neighbouring part. Offer them as extra route ends
  and lay one only when the route uses it. For a whole dense corner, run the router on that region alone at
  0.025 mm.
- When a connection fails on its own (nothing else routed), the cause is placement or a fixed obstacle, not
  congestion. Map failures to parts: when one part dominates, re-place or re-orient it so each side faces where
  its nets go. That beat every router tweak here.
- Hand routing by the user breaks these rules freely (563 direction deviations, a few segments on L5 at the
  end here). Report them with coordinates after their round; move nothing unless asked. When a segment on a
  plane has to come off, test each candidate layer with a real DRC on a copy (`kicad-practice.md` §7); two of
  three such paths moved cleanly to L3, the third needed a new path from the net's other end.

## 7. Width and shape: tracks that look intended

These came from the board's owner looking at a script-routed board that had passed DRC and every solver
(2026-11-10). His words: "this trace area makes no sense" and "the trace randomly switches size". Both were faults
of the method, and neither is visible to a rule check.

- **One width per net.** Signals 0.2 mm on this board, gate drives included. Narrower only for the escape from a
  fine-pitch pin, as one stretch from the pad. Power tracks: one width per run (between pads, vias and
  junctions), with a neck only where the run has to squeeze, and one neck width.
- **Never lower the width of single segments to satisfy DRC.** A widening pass that backs off segment by segment
  leaves 0.25 / 0.4 / 0.3 / 0.6 in one run. Decide the width for the whole run.
- **A track goes where it is going.** Length over the shortest tree across the net's pads: 1.0 to 1.4 is direct.
  Over 1.5 needs a reason (a keep-out, a pair, a corridor). Over 2 is a fault.
- **Few bends, all at multiples of 45°.** No staircases: a run of segments under 0.2 mm is a grid router's
  signature. No segment at an odd angle, pad escapes included.
- **A multi-pad net is one tree**, drawn as a tree. Not a chain of connections each made to whatever copper of
  the net was nearest at the time.
- **Vias only where the route needs a layer change**, and an existing hole is re-used before a new one is drilled.
- Measure all of this after every pass with `hardware/Production/groundup/compare/tidy.py` and put the table
  beside the DRC result. Method and the cleanup pass: the `pcb-scripted-routing` skill.

## 8. Checklist

- [ ] No segment on L3 that isn't vertical; none on L4 that isn't horizontal.
- [ ] No tracks and no non-GND zones on L2/L5; no via rows that slot them.
- [ ] Long signal runs on L1/L6 reviewed (advisory: length is a goal, not a rule).
- [ ] Every signal layer change has a GND via within 1 mm.
- [ ] One width per net (per run on power tracks); no width change in mid-run; no staircase; nothing off the
      45° grid; no net over 1.5× its shortest tree without a reason.
- [ ] Every IC with more than 20 pins or a pitch under 0.8 mm has 1–1.5 mm clear around it (decoupling excepted),
      and was fanned out first.
