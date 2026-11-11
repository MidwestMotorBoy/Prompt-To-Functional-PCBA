# ESD, TVS and connectors

Contents: 1. Why placement dominates · 2. Placing TVS/ESD parts · 3. Ground connection · 4. Connector areas ·
5. USB-C specifics · 6. Battery/bench inputs · Sources

## 1. Why placement dominates

TI SLVA680A gives the clamping voltage the protected IC sees as
`V = Vbr(TVS) + I_ESD·R_dyn + (L2 + L3)·dI/dt`, where L2 is any stub between the protected line and the TVS and L3
is the TVS's path to ground. ESD edges are ~1 ns, so a few nH adds tens of volts. The layout must **eliminate L2
and minimise L3**.

## 2. Placing TVS/ESD parts

- At the connector, before anything else on the line: the protected line runs **from the connector pin straight
  through the TVS pad** to the rest of the circuit, ideally with no vias (no stub).
- Place the protected IC much farther from the TVS than the TVS is from the connector.
- Don't route unprotected traces next to the connector-to-TVS segment (that segment carries the ESD current and
  couples into neighbours).
- Gentle corners on the ESD path (≤45°, ideally curved).
- Rohm's failure example: TVS parts placed afterwards in an empty corner of the board protected nothing. Place them
  in the path during placement, not as an afterthought.
- Don't park the TVS across the connector's signal pin rows; put it beside the pins it protects so the other pins
  can escape.

## 3. Ground connection

- TVS ground pad straight to the ground plane with its own via(s) right at the pad; wide and short.
- If a chassis ground exists, protect to chassis per the system design; otherwise to the low-impedance board ground
  plane (Altium, Cadence).

## 4. Connector areas

- Keep fast and switching nets away from connectors (cables are antennas).
- Ground fill and stitching around the connector; many vias on shell/ground pads.
- Filter (RC, ferrite, common-mode choke) at the connector, on the board side of the TVS.
- Mechanical: connector pads need strong copper (plated slots, large lands); check the maker's land pattern
  against the fab's edge clearance (mid-mount USB-C needs a notch).

## 5. USB-C specifics

- VBUS: many vias, wide copper, TVS beside the VBUS pins; bulk and HF caps per the PD controller's datasheet.
- CC and SBU: if a CC/SBU protector is used (e.g. TPD4S201), the CC lines pass through it from the connector; keep
  CC traces ≥0.25 mm (10 mil) wide, short, over ground; CC capacitance limits (connector + protector + caps) per the
  PD controller.
- D+/D−: protector in-line at the connector; see `signals-and-interfaces.md` §6.
- Shell: to ground with many vias (or to chassis per design).

## 6. Battery and bench inputs

- Reverse-polarity protection (series diode or ideal-diode) and an overvoltage clamp at bench inputs; put the
  clamp on the header side of the series diode so it doesn't load the pack.
- Communication lines to a pack connector: spark gaps (0.2 mm) and series resistors.

## Sources

- TI SLVA680A, *ESD Protection Layout Guide* (clamping equation, stubs, placement, corners).
- Rohm *PCB layout for TVS diodes*; Toshiba ESD FAQ; Altium and Cadence TVS placement articles.
- TI BQ40Z50-R2 datasheet §11.1.2 (spark gap).
