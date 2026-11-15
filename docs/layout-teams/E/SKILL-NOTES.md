# Team E skill notes: what a single agent learned taking the hand board to a full route

Each note says what to do, why, and where the tool or the evidence is. Paths are under `docs/layout-teams/E/`.

## Routing against generated power copper

1. **A generated pour is not a wall.** On the hand board 40 of 43 pins the trial router could never reach were shut
   in by generated pours, not by parts. Let a track cross a pour of another net and let KiCad refill round it, at a
   price that grows with the depth into the pour (`er.py`, `zcost`), and refuse any route that would split the pour
   or cut one of its pads off (`cuts_pour`). Hand board: 50 open signal connections became 20 with this alone.
2. **Power first, pinned.** A router left to close power paths with signal-width tracks turns 0.85 W into 2.5 W.
   Join the pieces that hold current-carrying pads before any signal, with a width from the terminal current
   (0.4 mm to 1 A, 0.8 mm to 2 A, else 1.2 mm), and pin them (`eroute.py --power`, terminals from `go.sh`).
3. **Score the routed board with its own copper.** The plan's loss number assumes the soft pack pour on In2 stays
   whole. Signal tracks on In2 cut it into strips; the pack current then crowds onto whatever the In4 copy offers.
   On run p9 that was a 1.2 mm neck beside the pack switch's via group (8 A/mm, loss 0.92 W became 1.39 W). Give
   the In4 copy the full width wherever the source's vias land (`recipe.sh`, BUS4 box) and look at
   `peak_A_per_mm` in `dc.json` of the routed board, not only at the total.
4. **A soft pour that carries current needs a price.** The router's soft pours (the In2 pack sheet, the In3 3V3
   sheet, the ground planes) cost nothing to cross, so 824 of 2047 mm of routed track went onto In2. One unit per
   cell for other nets' tracks on the pack sheet (`eroute.py --softpen=PACK_P:2:1.0`, default in `full.sh`) left 418
   mm there and sent the rest to the bottom layer and In3, same total length: routed loss 1.27 W became 1.14 W
   (PACK_P 0.38 W to 0.23 W; before routing 0.175 W). At 2 per cell SDA stays open in every pass. The other sheets
   pay a little: ground 0.29 W to 0.31 W, and the 3V3 sheet needs 15 short joins, some 0.15 mm wide.
5. **A pour that only touches a pad along its edge is not connected.** KiCad wants overlap. The router's raster
   said "one piece" for CELL_P at R118 and 3V3 at R304 through three passes while KiCad kept them open. Pull every
   pour in by one cell before labelling pieces (`er.py`, `net_copper`), and between passes take every pour as KiCad
   really filled it on the last routed board (`eroute.py --fills=`), hard pours included.

## Getting out of fine-pitch parts

6. **Pin access has a price.** The strip in front of a fine-pitch IC pin (0.7 mm outward, on the pad's layer) is
   dear for every other net, and a foreign via within 0.45 mm of it is dearer still, because a via that close shuts
   the strip. Signal connections open after the first pass fell from 24 to 14 with this cost alone (`er.py`, `acc`).
7. **Do not park a two-pad part in front of a pin row unless its pads are those pins' own nets.** The charger's
   REGN capacitor sat 0.6 mm above pins 28 to 25 (SW1, HIDRV1, BTST1, LODRV1) and trapped all four. Moved 1.7 mm
   along the row and turned, its pads sit straight above the REGN and GND pins it decouples; the one pin between its
   pads (DRV_SUP) gets a hand via in the band. All charger chip knots of both ports closed after this move.
8. **Pull-up rows need 2.5 mm from the pin row.** Four pull-ups 1.5 mm under the PD chip leave room for two vias,
   and the row needs four (each signal leaves for another part). Moving the row is cheaper than any router trick.
9. **Keep the channel between a chip and its capacitor row for the vias of the signals that end there.** The second
   VBUS pin's bottom-layer track ran along the channel between the CC capacitors and the PD chip and shut every via
   site the CC nets had. Laid 0.9 mm further up, under the capacitor pads, it costs nothing and CC2 closes.
10. **Knots are an ordering problem.** Where rip-up and swap give up, pull every loose route of the nets that have a
   pad in the box round the failed connection and lay them again in every order, keeping the first order that
   closes all of them (`eroute.py`, `knot`). It closed the Port 2 connector CC knot in one try (CC2 first). Cap the
   time per knot: a net that spans the board makes every order slow.

11. **Three pins in a row that go to three targets in the other order have one planar solution; lay it by hand.**
    The Port 1 protector's pins 5, 4, 3 (C_CC2, C_CC1, VBIAS) face the connector, and C_CC2's connector pad is the
    westmost target. The router gives the first net the straight line and shuts the next one in, in any order it
    tries. By hand: C_CC2 comes down first on a diagonal, C_CC1 and VBIAS leave east under it, 0.33 mm apart
    (`place/copper.txt`). The planner's VBUS track from the connector pad had to move 0.3 mm west for it.
12. **A via window narrower than the router's grid is a hand via.** Between the 0.8 mm bottom-layer VBUS track
    (0.25 mm rule) and the PD chip's pin row, Port 2 had 0.05 mm of room for the centre of CC2's via; Port 1, laid
    0.07 mm differently, had 0.12 mm and routed. The router left CC2 open through two runs and the picture
    showed a free channel. Compute the window (track edge + rule + via radius to pad edge - rule - via radius)
    before blaming the router; here the track went to 0.7 mm and the via was placed by hand.

## Kelvin taps

13. **Lay the taps before anything else, as their own kind of route.** A tap goes from the filter resistor's pad to a
    hand via at the inner edge of the shunt pad, arrives on an inner layer, and treats every other piece of its own
    net as an obstacle (`place/routes.txt`, `eroute.py --taps=`). Pinned.
14. **A tap via through a pour of its own net is not a tap.** The pour connects to the via and the amplifier senses
    the pour there. For PACK_P the In2 sheet and the In4 copy are everywhere, so every tap via gets a pour void (a
    rule area, 0.52 mm radius, all layers) written when the routes are applied (`eapply.py`), and the router's model
    knows the void. The tap's start pad must also be clear of its net's pour (`dropz` in `place/copper.txt`).

## Planner and scorecard gaps found on the way

15. Capacitors are not scored terminals, so the planner left the input shunt and the left bulk capacitors of both
    ports off the input FET's drain and the scorecard said nothing. Hand copper closes it (0.03 W per port).
16. The planner pours to every pad a net has unless told which ones carry current: a 28 mm PPHV corridor to the
    charger's VAC capacitor, and a VBUS tree through the channel the CC pins need. Planner-only terminal overrides
    (`place/constraints_plan.json`) fix both without touching the shared scoring constraints.
17. The seven hot-loop solves take about five minutes each on a routed board. Run them side by side
    (`sc.sh`, HOTJOBS).

## Finishing

18. **Read the warnings of the finished board, not only the error count.** With 0 errors and 0 unconnected the
    routed board still had four pairs of same-net vias drilled into each other (a hand via beside a planner via;
    `unvia` in `place/copper.txt`), one via that joined nothing and one track stub left by rip-up.
19. **Trim what rip-up leaves** (`etidy.py`, last step of `full.sh`): a routed track end that touches nothing of its
    net is cut back to the last junction. Test the end with its cap (width/2), not the centre point: the router
    ends tracks on a pad's edge, and a point test calls about 350 good ends dangling. Leave the plane nets out.

## Working method that held up

- One loop: `go.sh <run>` (moves, planner, hand copper, DRC, loss, dump: 2 min), `full.sh <run>` (pass 1 taps, power,
  signals; later passes everything with real fills; then the trim; 6 to 10 min), `eview.py --drc=` on each knot. Two
  or three runs side by side on four cores.
- Do not edit a shell script while a run is reading it; bash reads scripts as it goes.
- Every placement move and every piece of hand copper is one line in a text file with its reason
  (`place/moves.txt`, `place/copper.txt`, `place/routes.txt`). The run folders do not survive the container; these
  three files and `tools/` rebuild them.
- Look at the picture of a failed connection before changing the router. Most of the fixes that mattered were a part
  or a hand track 0.1 to 1 mm from where it should be, not a router fault.
