# Manufacturing (DFM / DFA), JLCPCB-oriented

Contents: 1. Copper rules · 2. Vias · 3. Holes and annular rings · 4. Edges and outline · 5. Solder mask and
paste · 6. Assembly: fiducials, rails, footprints · 7. Silkscreen · 8. Cost levers · 9. Before ordering · Sources

Always confirm against the fab's current capabilities page — numbers change.

## 1. Copper rules (JLCPCB capabilities page)

| Copper / layers | Min track / space |
|---|---|
| 1 oz, 1–2 layers | 0.10 / 0.10 mm |
| 1 oz, multilayer | 0.09 / 0.09 mm (3 mil in BGA fan-outs) |
| 2 oz, 2 layers | 0.16 / 0.16 mm |
| 2 oz, multilayer | 0.15 / 0.15 mm |

- Track width tolerance ±20 %.
- Pad-to-track clearance ≥0.1 mm (stay well above when possible); BGA pad-to-trace 0.09 mm on multilayer.
- Don't design at the minimum: use 0.15–0.2 mm general clearance on outer 2 oz layers; extra clearance (≥0.25 mm)
  between high-current copper and small signals.
- Copper-to-board-edge ≥0.2 mm (routed edge); more is safer (0.25–0.3 mm), except where a connector's land pattern
  must reach the edge. V-cut edges 0.4 mm.
- Third-party summaries (and JLC's own blog) quote 0.2 / 0.2 mm for 2 oz; the live capabilities page (fetched
  2026-10-17) says 0.15 / 0.15 mm multilayer. Fetch the page, don't trust a summary, when a board is designed at
  the 2 oz limit.

## 2. Vias

- Standard: 0.3 mm drill / 0.45–0.5 mm pad on multilayer; smaller vias (0.15–0.25 mm) cost extra.
- Via-in-pad needs filling and capping (POFV) — free on JLC 6+ layer boards, extra otherwise. Without it, solder
  wicks into the via (JLC disclaims via-in-pad paste problems on open vias).
- Tenting vias (mask over) avoids accidental solder bridges and helps under parts; filled-and-capped is cleanest.
- Via-to-via hole spacing and via-to-pad clearance per the capabilities page. Live page 2026-10-17: via hole
  ≥0.15 mm / diameter ≥0.25 mm (0.2 mm hole preferred; 0.3/0.45 is the no-surcharge standard), via-to-via hole
  spacing ≥0.2 mm, via-to-track ≥0.2 mm, PTH-to-track ≥0.28 mm (0.35 recommended), component hole-to-hole
  ≥0.45 mm. Keep the project's own `min_hole_to_hole` at 0.25 mm so a 0.508 mm via pitch (0.208 mm web) is
  caught before the fab sees it.

## 3. Holes and annular rings

- Plated holes on 2 oz multilayer: annular ring ≥0.254 mm (JLC). Generally ≥0.20 mm, with absolute minimums of
  0.15–0.18 mm by stack.
- Non-plated holes ≥0.5 mm; mounting holes with a copper keep-out ring.
- Slots per the fab's minimum; plated slots for connector shells. Live page: plated slot width ≥0.35 mm
  multilayer (0.5 mm two-layer), oval only, length ≥2× width (JLC's blog prefers ≥2.5×); the USB-C shell slots
  (0.5 × 1.0 mm in 0.9 × 1.4 mm pads) pass. PTH annular ring 2 oz: 0.254 mm; 1 oz multilayer 0.20 mm
  recommended, 0.15 mm absolute.

## 4. Edges and outline

- Closed outline on Edge.Cuts; connector notches drawn in the footprint or outline.
- Keep parts ≥3–5 mm from edges that will be V-scored or held by rails; add rails if needed (below).
- Pull plane and fill copper back from the edge (inset ~0.5 mm for whole-board planes).

## 5. Solder mask and paste

- Mask dams between fine-pitch pads: 0.075–0.125 mm preferred (fab-dependent); check fine-pitch parts' pad gaps.
- Mask expansion per fab default (often 0.05 mm); solder-mask-defined vs non-mask-defined pads as the land pattern
  says.
- Exposed pads: windowpane paste (50–80 % coverage) to control voiding and float.
- Large copper pours exposed for solder (bus bars) only if you mean it.

## 6. Assembly: fiducials, rails, footprints

- Fiducials (~1 mm copper dot, ~2 mm mask opening) — at least 3, asymmetric, ≥3.5 mm from the edge including the
  clearance (JLC blog). JLC standard assembly requires edge rails and fiducials (help centre); rails ≥5 mm.
- Footprints to IPC-7351B medium or low density (JLC does not support high density).
- Parts' courtyards must not overlap; leave room around tall parts for the nozzle and for rework.
- Polarity marks visible after placement (pin 1, diode cathode, polarised caps).
- Hand-fit parts: exclude from the position file and BOM upload; keep their `Sourcing` info.

## 7. Silkscreen

- Minimum text height ~0.8 mm, line ≥0.15 mm; nothing on pads or exposed copper; refdes readable in at most two
  orientations; block labels and connector pinouts help bring-up.

## 8. Cost levers (JLC)

- Each unique "extended" part costs a fixed loading fee per order; at low board quantities this can exceed the
  parts cost. Prefer basic/preferred library parts, consolidate values, and hand-fit dev-only parts.
- Smaller vias, blind/buried vias, special stack-ups, impedance control, gold fingers and non-standard copper add
  cost; 6-layer often gets free via filling.
- Consigned parts must be shipped to the assembler before the order.

## 9. Before ordering

- [ ] DRC clean against the fab's rules (copy them into the board's design rules and custom rules).
- [ ] Schematic parity clean.
- [ ] Gerbers viewed in a gerber viewer (every layer, drill file aligned).
- [ ] Position file rotations checked in the fab's viewer (KiCad and JLC disagree on some footprints' zero rotation).
- [ ] BOM: every assembled part has an LCSC/MPN, footprints match packages, DNP parts excluded.
- [ ] BOM has **one line per LCSC number** (JLC's tool flags shared parts as "Unconfirmed") and every number was
      stock-checked through the parts API the same day; parts without a number are on the hand-fit list.
- [ ] Parts the docs say the assembler places are not `exclude_from_bom`/`exclude_from_pos` on the board.
- [ ] Zones refilled before the gerbers were plotted; custom rules file present (compare with git).
- [ ] Board thickness, copper weights, finish, via covering, colour as intended.
- File recipes (kicad-cli flags, BOM/CPL columns, stock API): `kicad-practice.md` section 11.

## Sources

- JLCPCB capabilities page (track/space, tolerance, annular rings, BGA rules).
- JLCPCB blog (fiducials 3.5 mm from edge), help centre (edge rails ≥5 mm, rails and fiducials required for
  standard assembly), assembly terms (IPC-7351B medium/low density; via-in-pad paste disclaimer).
- Generic DFM guides (mask dams).
