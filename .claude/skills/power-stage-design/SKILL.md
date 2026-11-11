---
name: power-stage-design
description: Design or review a switching power stage (buck-boost charger, USB-PD source/sink port, DC-DC rail) for losses, gate drive, inductor and frequency, capacitor banks, sensing, port protection and fail-safe defaults. Use when choosing a power-stage architecture or ICs, cutting losses, sizing bulk caps, or asking "is GaN / an integrated part worth it".
---

# Power-stage design and review

This is drawn from a bidirectional 100 W USB-C PD port (TPS25751 PD controller + BQ25756 buck-boost + discrete 40 V half-bridges) on a 4S Li-ion pack. See `docs/spec.md` (Ports, charging and power policy; Decided: the four loss cuts) and `research_notes/Loss reduction/`. The method itself is general.

## 1. Loss budget before parts

Build a loss table for each element at several operating points: light load, nominal, full power, full power **near empty** (lowest source voltage, highest current), and charging.

| Element | Model |
|---|---|
| Conduction (FETs, inductor DCR, sense resistors, copper, fuse, cell interconnect) | I_rms² · R, with R at temperature (copper +0.4 %/K, FET R_DS(on) ×1.25–1.5 warm) |
| Switching | ½ · V · I · (t_r + t_f) · f_sw + Q_rr · V · f_sw + Coss terms |
| Gate drive | Q_g · V_drive · f_sw per FET (plus the regulator's dropout loss) |
| Inductor core | maker's calculator at the real ripple and frequency |
| Quiescent / fixed | each IC's I_q × rail, the always-on 5 V or VCONN rails |

- Rank the levers by watts saved at full power, and give the cost, area, height and the risk for each.
- **The near-empty case** is often the hottest: on a 4S pack, 100 W from 11.2 V is about 9 A, and cell resistance rises near empty. Firmware should derate at low pack voltage.
- Feed the board heat into the thermal model (see `thermal-derating`). In a sealed pack the stage heat often ends a high-power burst before the cells do.

## 2. Levers that worked (and those that didn't)

- **Lower-R_DS(on) protection and path FETs** in the same or a larger package, checked against short-circuit stress (see `battery-protection-config`).
- **Raise the gate drive** (5 V → about 9 V) for a high-side FET that's always on in the buck-boost's pass-through leg. Rules from the BQ25756 datasheet: DRV_SUP must be off whenever the converter is disabled, so derive its enable from REGN *and* a per-port control. An LDO's EN must never sit above its IN, so gate the enable on a minimum source voltage (PACK_P ≥ 10 V here). Fit it default-off and let firmware turn it on only for contracts ≥ 45 W.
- **Lower switching frequency with a better inductor in the same footprint** (here 3.3 µH XGL7030 at 500 kHz instead of a 2.2 µH part at a higher frequency). Lower frequency alone, with a bigger L in the same height, lost because DCR and saturation got worse.
- **Thicker cell interconnect** (nickel) and short wire tails.
- **Config-only:** PFM at light load while sourcing; route a low-voltage PDO through the most efficient path.
- Rejected after analysis: lower sense resistors (the controller scales its limits to 5 mΩ), a lower-value shunt (worse gauge offset for 35 mW), a lower-resistance fuse (≤ 60 mW, not stocked).

## 3. Bootstrap and high-side gotchas

- A high-side FET held at 100 % duty runs on a sagging bootstrap. Check whether the controller forces a refresh; the BQ25756 doesn't. Then check the FET's R_DS(on) is specified at the lowest bootstrap voltage (2.7 V refresh minimum here). One 40 V part couldn't carry 12.6 A at that gate voltage.
- Put the hot loop's 0.1 µF caps right at the half-bridge pins. Watch switch-node ringing at bring-up, with gate resistors and RC snubber pads fitted as 0 Ω / DNP options.

## 4. Capacitor banks (simulate, don't guess)

`hardware/DevBoard/tools/cap_sims.py`, `hardware/Production/tools/pack_bus_sims.py` and `low_profile_sims.py` model each bank as a network of R + jωL links with per-part C(V), ESR and ESL:
- **C_eff at the worst voltage** after DC bias, at or above the converter's minimum (BQ25756 C_OUT ≥ 80 µF after derating, per converter).
- **RMS current per capacitor** against its rating at temperature. Currents from unsynchronised converters add in quadrature.
- **Ripple** at each converter's node; worst-phase peak-to-peak.
- **Input-filter damping (Middlebrook).** A constant-power converter looks like a negative resistance, −V²/P. Keep the source-plus-bank |Z_out| well below V²/P across frequency, or add damping (a polymer cap's ESR). Here a polymer bank gave about 21 dB of margin.
- **Chemistry by rail:** MLCC only on always-live rails (leakage), polymer tantalum where the rail is off in sleep, never MnO2 tantalum.
- **Height:** in a tight enclosure the tallest cap often sets the board's height zone. Low-profile parts (2.0 mm polymer Ta) can free it.

## 5. Sensing

- Use the controller's required sense values (TI fixes BQ25756 RBAT at 5 mΩ).
- Route every sense pair Kelvin from the resistor pads (see `pcb-layout-review`). A tap on a plane or a cap moved current limits by 7–80 % on this board.
- Make sure a filter on a sense line doesn't also carry another block's supply current (VAC/REGN fed through ACP).

## 6. USB-C port protection

- CC lines: a short-to-VBUS protector (TPD6S300 / TPD4S201 class) unless the PD controller's CC pins are rated for it. The TPS25751's are 26 V abs max but only ±1 kV HBM. Keep the total CC capacitance (protector + caps) under the controller's limit (480 pF here).
- VBUS TVS: breakdown above 21 V PPS, clamp under the controller's 28 V abs max (TVS2200 class, TI's own pick for the TPS25751).
- Dead-battery Rd on CC while unpowered, if the protector doesn't build it in.

## 7. Fail-safe defaults

Ask what the stage does with blank firmware, a blank EEPROM, an MCU reset and a watchdog expiry:
- The PD controller with a blank EEPROM in SafeMode never closes its sink switch. Good, but the first boot then needs a bench supply.
- **Charge-current limit set to 0 Ω on the ICHG pin** (register-only limit) lets a cell change be a software change. That is acceptable only with backstops: the PD controller's config loads a safe ICHG at power-up, firmware reads back ICHG_REG / EN_ICHG_PIN / EN_CHG every second and before enabling charge, the gauge's charge-overcurrent trip sits just above the maximum, and the input current limit caps the worst case.
- A charge-inhibit line pulled to "inhibit", so a dead MCU stops charging.
- Port sharing: two sourcing ports must never add up to more than the shared budget, even briefly. Lower one contract before raising the other.

## 8. "Should we use GaN / an integrated chip?"

Check before recommending:
- **Does the controller support it?** For GaN that means adaptive dead time, a bootstrap clamp, a gate drive within the ~6 V GaN limit, and a frequency high enough to benefit. The BQ25756 fails all four, and the ~6 V gate limit also rules out the 9 V drive.
- **Does it fit the system?** Integrated-FET chargers can cap reverse (OTG) current. The BQ25798 tops out at 3.32 A, about 60–65 W per port. Some aren't supported by the PD controller's charger integration, so firmware would have to retune them on every contract.
- **Does the area saving matter?** If the board outline is set by something else (the cell face here), freeing area doesn't make the product smaller. Count grams and millimetres at the system level: any IC swap here saved at most about 1 g per port.
- Write the answer as "keep / change", with the watts, grams and risk.
