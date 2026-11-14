# Schematic readability rubric

Judge the rendered sheets as a person who must review this circuit (an electrical engineer who did not write the code).
Score every criterion 0-5 for each sheet (3V3 Rail, Cells and Gauge, MCU, USB Port; the two USB port sheets count
as one). 0 = fails completely, 3 = acceptable to review from, 5 = as good as a careful human drawing.

1. **Flow.** Power and signals read left to right (inputs left, outputs right); a power path reads as a path
   (input caps, switch, inductor, output caps in order); supplies up, ground down.
2. **Grouping.** Each functional block sits together under a title; support parts sit next to the pin they serve
   (decoupling caps at their supply pin, pull-ups by their line, sense resistors in line with the current).
3. **Wires vs labels.** Short local connections are drawn as wires; labels are used for long or sheet-to-sheet
   nets. No parts floating alone tied only by labels when a wire would be clear; no long detours or "down wire"
   runs; no wire that wanders across the sheet.
4. **Clutter.** No overlapping text, symbols or labels; no wire crossing a symbol body; no text on top of wires;
   all reference designators and values legible.
5. **Space.** Sensible density: no large empty regions with everything crammed into a corner, no cramped clusters;
   the drawing fills the page in a balanced way.
6. **Recognisable circuits.** Known sub-circuits (buck converter, H-bridge/four-switch stage, divider, current
   sense, pi filter, pull-ups, protection) look like the textbook drawing of that circuit.
7. **Annotation.** Values visible; net names meaningful; section titles and short notes say what a block does.
8. **Reviewability (overall).** Could you check this circuit against the datasheets from this sheet without
   tracing nets by search? 0 = no, 5 = easily.

The netlist gate (sheets electrically identical to the code) is pass/fail and is checked separately.
