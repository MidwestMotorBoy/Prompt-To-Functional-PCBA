# Stack-up and plane assignment

Contents: 1. Objectives · 2. Layer-count choices · 3. Assigning roles per layer · 4. Power: planes vs pours ·
5. Copper weights · 6. Writing a pour plan · 7. Worked example (6-layer power board) · Sources

## 1. Objectives (Henry Ott's five)

Ott's stack-up objectives, in his words, are the yardstick for any stack-up:

1. "A signal layer should always be adjacent to a plane."
2. "Signal layers should be tightly coupled (close) to their adjacent planes."
3. "Power and Ground planes should be closely coupled together."
4. "High-speed signals should be routed on buried layers located between planes."
5. "Multiple ground planes are very advantageous, since they will lower the ground (reference plane) impedance"
   and "reduce the common-mode radiation."

Ott notes that eight layers is the smallest count that meets all five; four- and six-layer boards are
compromises, and when objectives conflict, **signal-to-plane closeness (2) matters more than power-to-ground
closeness (3)**. Standard power/ground plane pairs give too little interplane capacitance to decouple below
roughly 500 MHz anyway, so decoupling is done with capacitors, not plane spacing.

Why these matter: a trace's return current flows in the nearest plane, spread over a width of a few dielectric
thicknesses either side of the trace. The thinner the dielectric to that plane, the tighter the return, the smaller
the loop, the lower the inductance, crosstalk and emissions. A signal layer with no adjacent plane has no defined
return at all.

Keep the stack **symmetrical** (if layer 2 is a plane, layer N−1 should be too) to avoid warp.

## 2. Layer-count choices

### 2 layers
Bottom mostly solid ground; route on top; any bottom trace cuts the plane — keep them short and perpendicular to
the currents above. Power stages suffer most (TI SLVAEP5 measured 4–10 dB less radiated EMI going to four layers
with ground planes under the outer layers).

### 4 layers
- **Sig / GND / GND / Sig** (or Sig / GND / PWR / Sig with power as pours): easiest for SI/EMI. Both outer layers
  have a close plane. Route power as pours on the outer layers.
- Sig / GND / PWR / Sig: common, but the bottom layer references the power plane, so any split in the power plane
  breaks bottom-layer returns. If you use it: keep the power plane unsplit under bottom-layer signals, and add
  stitching capacitors where returns must jump planes.
- Avoid Sig / Sig / GND / PWR style arrangements where an outer signal layer is far from any plane.

### 6 layers (Ott's comparison)
- **G-S-G/P-S-G (plus pads)**: meets all five objectives but has only two routing layers; rarely used.
- **S / S(hi-speed) / GND / PWR / S(hi-speed) / S**: "probably the most common six-layer stack-up"; meets 1, 2, 4.
  Power and ground are far apart (no useful interplane capacitance), so decoupling must be designed carefully.
- **S / GND / S / S / PWR / S** variants: good when signal layers sit very close to their planes and a thick core
  makes up the thickness (Ott's example for 0.060": 0.005/0.005/0.040/0.005/0.005").
- **Avoid S / S / GND / PWR / S / S**: "the planes provide no shielding for the signal layers".
- For power-heavy boards a practical choice is **Sig+power (2 oz) / GND / Sig / Sig / GND / Sig+power (2 oz)**:
  two solid ground planes (objective 5), each outer layer next to ground, inner signal layers each next to one
  ground. Power is carried as pours on the thick outer layers rather than as a dedicated power plane.

### 8+ layers
Can meet all objectives: e.g. S / G / S / P / G / S / G / S. Use when there are many high-speed nets or very dense
BGAs.

## 3. Assigning roles per layer

For each layer decide: **reference plane, routing layer, power layer, or mixed**. Rules of thumb:

- One layer (usually layer 2) is a **solid, unbroken ground plane** — no traces at all. It is the return for the
  outer layer above it and for both hot loops of a converter on that side. If you can afford two, make the second
  one solid too.
- Routing layers carry signals that reference the plane next to them. Route each signal on the layer adjacent to
  the plane it should reference; changing layers changes the reference (see `return-paths-and-grounding.md`).
- Sensitive analog (sense pairs, feedback, references) go on a buried layer directly against the ground plane,
  shielded from the switching copper on the outer layers.
- Gate-drive traces: low-side drive over solid PGND; high-side drive with its switch-node return stacked on the
  adjacent layer (TI SLVAFJ3: return "in the shadow of the drive trace on the adjacent layer").
- Leftover area on signal layers is filled with ground and stitched to the planes, except where a fill would
  create slivers or isolated islands.

## 4. Power: planes vs pours

- **Dedicated power plane**: good for many loads on one rail spread across a board (digital boards). It also
  becomes a reference plane for the adjacent layer — don't split it under signals that use it as reference.
- **Pours on outer layers**: better for a power board with a few high-current nets that each live in one region.
  Each net gets one pour per layer in its own region; the outer layers are usually thicker copper; mirror the pour
  on top and bottom and stitch with via arrays to double the copper.
- **Rails as wide traces** on an inner routing layer are fine for low-current rails (3.3 V logic etc.).
- Never route a high-current or switching net across the area of the board that holds sensitive analog, on any
  layer.

## 5. Copper weights

- Outer layers carry current: 1 oz (35 µm) or 2 oz (70 µm). 2 oz halves sheet resistance (≈0.5 → ≈0.25 mΩ/sq)
  but raises the fab's minimum track/space (JLC multilayer: 0.09/0.09 mm at 1 oz, 0.15/0.15 mm at 2 oz) and the
  annular ring (≥0.254 mm for plated holes at 2 oz). Check fine-pitch parts (0.4–0.5 mm pitch QFN/LGA) against the
  2 oz spacing before committing.
- Inner layers are often 0.5 oz: excellent planes (thin, flat), poor current carriers. Keep high current off them.

## 6. Writing a pour plan

A one-page plan agreed before routing saves days. Template:

| Layer | Copper | Role | Carries | Must never carry |
|---|---|---|---|---|
| L1 | 2 oz | parts + power | power pours per net in their block, GND fill elsewhere | sense pairs through power pours |
| L2 | 0.5 oz | **solid GND** | nothing but GND | any trace or split |
| ... | | | | |

Add: which nets are poured on which layers and in which regions; which nets get mirrored/stitched; where any
second ground (gauge VSS, chassis) lives and its single join point; antenna and mounting-hole keep-outs; via
sizes per net class; zone priorities.

## 7. Worked example: 6-layer battery-pack / charger board

Stack: F.Cu 2 oz / In1 0.5 oz / In2 0.5 oz / In3 0.5 oz / In4 0.5 oz / B.Cu 2 oz.

| Layer | Plan |
|---|---|
| F.Cu | parts; one pour per power net in its block (cell links, pack bus, each charger's input and battery banks, VBUS, 5 V); switch nodes only as large as needed; GND fill elsewhere stitched to In1 every 3–5 mm |
| In1 | solid GND, no traces; return for F.Cu and both converter hot loops |
| In2 (L3) | signals, **vertical only**: Kelvin pairs, cell taps, FB/ILIM, I2C, interrupts; 3.3 V as a local pour; GND fill where large |
| In3 (L4) | signals, **horizontal only**: long cross-board nets, gate-drive pairs that must leave F.Cu, 5 V local pours; GND fill where large |
| In4 (L5) | solid GND, no traces, splits or islands |
| B.Cu | mirror of the F.Cu high-current pours (2 × 2 oz), stitched; GND fill elsewhere; no switch-node copper |

Why this works: each outer layer has a solid ground 0.2 mm away; both inner signal layers have a ground on one
side; two ground planes lower ground impedance; current lives on the thick outer copper; the gauge's milliamp
ground never shares copper with pack current. The gauge's VSS is local fill on F.Cu (and B.Cu) under the gauge,
joined at the shunt pad by a net tie, never an island cut into In1/In4. The inner pair is Manhattan (see
`routing-discipline.md`), so a net that turns uses a via between In2 and In3, with a GND via beside it.

## Sources

- H. Ott, PCB Stack-Up parts 1, 3 and 6 (hott.shielddigitaldesign.com/techtips): objectives, 6-layer comparison,
  return-path discontinuities.
- TI SLVAEP5A, *Layer Design for Reducing Radiated EMI of DC-DC Buck-Boost Converters*: measured 4–10 dB from
  adding ground planes adjacent to the outer layers, up to 10 dB from minimising hot planes.
- JLCPCB capabilities page (track/space by copper weight, annular ring).
