# High current and thermal

Contents: 1. Sizing conductors · 2. Pours, not traces · 3. Vias for current · 4. Battery and pack paths ·
5. Solid vs thermal-relief connections · 6. Thermal pads and thermal vias · 7. Spreading heat · 8. Worked sizing ·
Sources

## 1. Sizing conductors

- Use IPC-2152 charts (or a calculator built on them); IPC-2221's older curves are conservative for external
  layers and wrong for internal ones. Secondary sources disagree in detail, so leave margin.
- Planning figures, outer layer, 10 °C rise:
  - 1 oz: ~1 A per 0.3 mm, ~3 A per 1.5 mm, ~6 A per 4 mm.
  - 2 oz: ≈2.3–2.5 A at 0.5 mm (20 mil), ≈4.8–4.9 A at 1.27 mm (50 mil), ~6 A at 1.8 mm, ~10 A at 3.5 mm.
  - Inner layers carry less: plan 50–70 % wider than outer for the same rise, and inner 0.5 oz copper is a
    quarter of 2 oz — keep high current off thin inner layers.
- The fab's track-width tolerance is about ±20 % (JLC): size so the thinnest-case track still meets the rise.
- Resistance check: sheet resistance ≈0.5 mΩ/sq (1 oz), ≈0.25 mΩ/sq (2 oz). A 3 mm × 30 mm 2 oz path is 10 squares
  = 2.5 mΩ: 25 mV and 0.25 W at 10 A. Compare with the shunt you are trying to measure.
- Short-time surges (inrush, fuse clearing) are limited by fusing (I²t), not by the steady rise chart.

## 2. Pours, not traces

- Carry high current in **copper pours** (zones) shaped like the current's path, not in thin traces. A pour
  spreads current and heat and lowers inductance.
- One pour per net per layer, in that net's region. Overlapping same-net zones with different priorities knock
  each other out in KiCad; same-net, same-priority overlaps raise DRC errors — draw one outline per net per layer.
- Mirror important pours on both outer layers and stitch them with via arrays along the length: doubles copper,
  halves resistance, and the stitching vias also carry heat.
- Make the path straight: orient parts (sense resistors, FETs, fuses) so current enters one end and leaves the
  other without a U-turn (TI SLVAFJ3 tips: "make the high current flow along a short and straightforward path.
  Prevent unnecessary zigzag patterns").
- Necks: the narrowest point sets the rise. Check each pour for necks between pads, vias and other nets' clearances
  — KiCad's minimum-width/connection-width DRC flags many of them.
- Keep vias inside the zone outline; a via sticking out of a zone's edge makes a narrow neck.
- Run go and return currents on adjacent layers or side by side to cancel fields.

## 3. Vias for current

- Per 0.3 mm plated via: estimates range ≈0.8–1.9 A at 10 °C rise depending on plating (20–25 µm). Plan ~1 A per
  via; TI's TPS25751 guidance uses 1 A per via.
- Layer changes on high-current paths need many vias: ~10–13 standard vias for 10 A. Spread them across the width
  of the path, not in a single row (current crowds into the first vias it meets).
- Too many vias crowded in one place cut the copper between them (SLVAFJ3). Use a staggered grid with at least
  0.3 mm of plane copper between neighbouring antipads, never an in-line row: the L2/L5 ground planes must not be
  slotted (`routing-discipline.md` §4; `check_routing_rules.py` reports via rows that slot them).
- Avoid vias in high-current paths unless needed; when needed, use enough.

## 4. Battery and pack paths

- Draw the whole path end to end first: cell− → shunt → system ground; cell+ → fuse → protection FETs → pack bus →
  loads. Every element in series must carry peak current: holder contacts, straps, fuse, FETs, shunt, connectors.
- Holders that can only be oriented one way force long series links between cells: make them wide diagonal bands
  on both outer layers under the holders, avoiding holder pegs and mounting holes.
- Protection FET bypass and pack-terminal capacitors: wide, short copper (TI BQ40Z50 §11.1.1) — their job is
  high-frequency, so their loop inductance matters.
- Keep pack current copper away from gauge and sense circuitry (§11 of the gauge datasheet: magnetic and capacitive
  coupling during surges and ESD can disturb or damage the gauge).
- The shunt: four-terminal connection; the gauge's ground connects only at the cell-side pad (see
  `return-paths-and-grounding.md`).

## 5. Solid vs thermal-relief connections

- **Solid** for anything that carries current or must shed heat: FET pads, inductor pads, sense resistors, power
  connectors, battery holder contacts, exposed pads, thermal vias, power-pour vias.
- **Thermal relief** for small passives sitting in big pours (unequal heating tombstones them) and for parts that
  will be hand-soldered to a plane (headers, test loops), where the iron can't heat a solid connection.
- Hand-soldered parts that carry current (e.g. battery holders) need solid connections anyway: use a large iron,
  preheat the board, or hot air.
- Make sure thermal spokes are wide enough for the current if you do use them; in KiCad the spoke width must not
  exceed the pad width and the zone minimum width must not exceed the spoke width.

## 6. Thermal pads and thermal vias

- Follow the IC's land pattern: exposed-pad size, solder-mask definition, paste windows (often a windowpane at
  50–80 % coverage) and the vendor's via count/pattern.
- Thermal vias: 0.2–0.3 mm drill at ~1.0–1.2 mm pitch across the pad, connected solid to the ground plane(s)
  (TI SLOA122: vias ≤0.3 mm, voiding < 50 %).
- Open vias in a pad wick solder away (voids, starved joints). Options: plugged/filled and capped (via-in-pad
  "POFV"; free on JLC 6+ layer boards), tented from the bottom, or small enough and few enough that the paste
  covers it. Plugging gives the best thermal result but costs on boards where it isn't free.
- A thermal via's thermal-relief ring to the plane blocks the heat path: set the pad/via to connect solid.
- Thermal vias also count as a ground connection for the IC; keep them inside the pad so they don't make the
  plane look like Swiss cheese around it.

## 7. Spreading heat

- Copper area on the outer layer around a hot part, connected solid, is the heatsink; the planes beneath, reached
  by vias, spread it further.
- Keep hot parts apart; don't stack two heat sources' copper.
- Electrolytic and polymer capacitor life halves for every ~10 °C; keep them out of the FET hot spot.
- Board temperature sensors (NTCs, I2C sensors) sit on the copper they measure, with their exposed pad/vias tied
  into that copper (usually ground copper next to the hot part).

## 8. Worked sizing example

10 A pack path on 2 oz outer copper with a mirrored bottom pour:
- Single 2 oz layer needs ≈3.5 mm for 10 °C; mirrored on two layers, 3.5 mm each gives margin for −20 % etch and
  for the bands' necks around holder pegs: draw ≥5 mm bands.
- Layer change from top to bottom at a fuse or connector: ≥12 × 0.3 mm vias spread across the band.
- Loss: a 5 mm × 80 mm band on two layers ≈ (16 squares × 0.25 mΩ) / 2 ≈ 2 mΩ → 0.2 W at 10 A. Fine.

## Sources

- IPC-2152 (charts) via secondary tables: AtlasPCB, Altium, NextPCB (they disagree slightly — keep margin).
- Via current estimates: instrumentationblog, tracewidthcalculator, QueenEMS; TI TPS25751 datasheet (1 A per via).
- TI SLVAFJ3 §2.7 and §3 (thermal vias, via counts, straight current paths).
- TI SLOA122 QFN layout (thermal via size, voiding); TI package land patterns (fill/plug/tent vias under paste).
- TI BQ40Z50-R2 datasheet §11 (bypass capacitors with wide copper, separation from gauge).
- JLCPCB capabilities (±20 % track tolerance; via-in-pad POFV on 6+ layers).
