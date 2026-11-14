"""Cells and Gauge sheet: pack power path, BQ40Z50 gauge with its cell inputs, second-level protector and fuse driver."""
from layouts import layout
from sch import Port, snap
import patterns as P
import lay_cells1, lay_cells2, lay_cells3

GAP = 7.0


@layout("cells_gauge")
def cells_gauge(S, p):
    X0, Y0 = 20.32, 30.48
    notes = S.ctx.cons.get("notes", {}).get(S.ctx.block, [])
    k = 3                                                     # notes 1 to 3 are about the power path and the gauge, the rest about the protector
    # row 1: the power path, the notes in the free space at its right (they open with the power path)
    s1, b1 = P.fit(S, lambda T, x, y: lay_cells1.power_path(T, x, y), X0, Y0)
    xn = b1[2] + GAP + 3
    yn = P.notes_block(S, xn, b1[1] + 1, notes[:k], width=56.0)
    # row 2: the gauge, the thermistor inputs standing at its right (they feed its TS pins)
    y2 = max(b1[3], yn) + GAP
    s2, b2 = P.fit(S, lambda T, x, y: lay_cells2.gauge(T, x, y), X0, y2)
    s3, b3 = P.fit(S, lambda T, x, y: lay_cells3.thermistors(T, x, y), b2[2] + GAP, y2)
    s2.min_y1 = s3.min_y1 = max(b2[3], b3[3])                # one bottom edge for the row
    s1.min_x1 = s2.min_x1 = max(b1[2], b2[2])                # and one right edge for the two wide frames
    # row 3: second-level protector and fuse driver
    s4, b4 = P.fit(S, lambda T, x, y: lay_cells3.protector(T, x, y), X0, max(b2[3], b3[3]) + GAP)
    s1.max_x0 = s2.max_x0 = s4.max_x0 = min(b1[0], b2[0], b4[0])    # one left edge for the column
    # the rest of the notes stand beside the protector they describe, in the space under the thermistor inputs
    xr = b4[2] + GAP + 3
    P.notes_block(S, xr, b4[1] + 1, notes[k:], width=b3[2] - xr, title="Notes, continued", first=k + 1)
    S.finish()
