---
name: component-sourcing
description: Select, compare and source electronic parts (FETs, TVS, capacitors, inductors, ICs) for a board built at JLCPCB/LCSC or from Mouser/DigiKey, including drop-in replacement checks for out-of-stock parts and clones. Use when picking a part, replacing one that's out of stock, judging a clone or a new silicon revision, or checking stock and price.
---

# Component selection and sourcing

Pick parts from the requirement down, verify every claim in the maker's datasheet, and record the decision where the BOM lives. Examples come from this repo: `research_notes/protection-fets/options.md`, `ordering/parts-tracker.csv` and the swap notes in `docs/spec.md`.

## 1. Write the requirement first

Derive numbers from the worst case, not the typical one:
- **Voltage:** the highest the net reaches in any state, including hot-plug overshoot (a USB-C 20 V hot plug reaches about 27–29 V) and inductive kick at turn-off.
- **Current:** continuous at the worst operating point (a power bank at 100 W near empty, not at nominal), pulse, and fault current. Take fault current from the source's real impedance over the trip window. For Li-ion cells use the datasheet's AC impedance, because the 1 kHz figure is what a 100 µs short sees.
- **Thermal:** allowed loss at the hottest ambient. **Size:** land pattern and height zone in the enclosure. **Leakage:** against the sleep-current budget, if the part sits on an always-live rail.

## 2. Compare candidates in a table

One row per part, with the figures that decide it: rating, R_DS(on) or ESR at the real conditions, charges (Qg, Qgd), pulse ratings, package, stock and price, and the modelled result for your case (loss, ΔTj). Say what you couldn't read, such as SOA or Zth graphs that didn't come through as text, and add "check the graph before ordering" as an open item.

Lessons that generalise:
- **Bigger isn't always better for protection FETs.** A gauge's weak gate drive (5.1 kΩ) turns a FET off slowly through its Miller plateau, so a big die with a large Qgd sits longer in the linear region during a short. The pick was the lowest-R_DS(on) part with the smallest Qgd (0.70 mΩ, 11.2 nC), not the biggest die.
- **MLCC capacitance under DC bias.** Read the maker's curve at the working voltage. A "22 µF 35 V" 1210 keeps about 10 µF at 16.8 V and about 6 µF at 20 V. A taller, higher-voltage part can hold more than a "bigger" low-voltage one.
- **Bulk capacitor chemistry.** Polymer tantalum or polymer aluminium has low ESR, but its leakage (0.1–0.3 CV, hundreds of µA) rules it out on an always-live rail with a µA sleep budget. Use MLCCs there and polymer only on rails that are off in sleep. Avoid MnO2 tantalum on low-impedance inputs: it fails short, can ignite, and needs 50 % voltage derating.
- **TVS on VBUS.** Minimum breakdown above the highest legal voltage (21 V PPS); clamp below every part's absolute maximum at the surge current.
- **Sense resistors** are often fixed by the IC (TI fixes BQ25756 RBAT at 5 mΩ, and the PD controller writes limits scaled for it). Don't "optimise" them.

## 3. Check stock and price

From a cloud container, `curl` to distributor sites is often blocked by the proxy; WebFetch usually works.
- **LCSC:** `https://www.lcsc.com/product-detail/C<number>.html` gives stock, price breaks and basic specs. Stock can disagree between fetches or sit only in the page metadata, so treat it as approximate.
- **JLC parts library:** `hardware/Production/tools/jlc.py KEYWORD` searches JLC's parts API (code, basic/extended, stock, price, package). jlcpcb.com part pages show basic or extended but not stock.
- **Datasheets:** the maker's PDF (find it by web search) or `datasheet.lcsc.com/...pdf?productCode=C...` from the product page. `lcsc.com/datasheet/C....pdf` returns a JavaScript shell.
- **Mouser / DigiKey / Newark / Farnell** for parts JLC doesn't stock. Note the lead time and the next restock date, not just today's stock. Distributor "short links" and carts can't be read from the cloud; ask for a CSV export.
- Some maker sites (TE drawings, for example) block cloud fetches. Farnell/element14 mirror many datasheets.

## 4. Replacing a part (out of stock, cheaper, clone, new revision)

A "drop-in" has to pass all of these, checked against both datasheets:
1. **Pinout,** pin for pin against *your symbol*, including the exposed pad's net.
2. **Land pattern:** pad sizes, pitch, EP size (±0.1 mm), and the body size against neighbours and the height zone.
3. **Ratings** at your worst case, not the headline numbers.
4. **Behaviour that firmware depends on.** A new silicon revision of a configurable IC can need a different configuration bundle or tool version, and may drop a supported companion part from its datasheet. On this project the TPS25751**A** was pin-identical to the **D** but needed a new GUI bundle, and its datasheet no longer named the BQ25756 charger. The verdict was to stay on D and never mix revisions on one board.
5. **Clones** (same MPN from a second-source maker): expect a short datasheet with typical values only and no min/max or temperature data. Check the pinout and EP from the drawing, and flag the pin-1 orientation in the assembler's placement preview (a rotated TVS shorts VBUS to GND).
6. **Same family, different voltage class:** check whether the higher-voltage sibling costs R_DS(on) and Qrr. Here the 70 V sibling of a 40 V half-bridge FET had 1.9× the R_DS(on) and 2× the Qrr, about +1 W per port.

If nothing passes, the fallback options are: buy the real part from a distributor and consign it to the assembler, mark it DNP and hand-fit it, or ask the assembler for a sourcing quote. Don't change the design while a quote is pending.

## 5. Record the decision

- Update the schematic fields (LCSC, MPN, Datasheet, Notes with date and reason) by script (see `kicad-schematic-scripting`). Keep the footprint only if step 4.2 passed.
- Update the assembler BOM (`jlc-fab-files`), the parts tracker (`ordering/parts-tracker.csv`, then `python ordering/update_readme.py`) and the spec.
- Put the maker's datasheet in `datasheets/` under a name that says which part it is, and index it in `datasheets/README.md`.
- If a part becomes hand-fitted or consigned, add it to the hand-solder / consign list and to the order notes.
