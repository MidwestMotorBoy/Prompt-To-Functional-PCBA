"""USB-C PD port sheet (used for both ports): sections drawn by lay_usb1..5 and packed on one page."""
from layouts import layout
from sch import Port, snap
import patterns as P
import lay_usb1, lay_usb2, lay_usb3, lay_usb4, lay_usb5

GAP = 7.0


@layout("usb_port")
def usb_port(S, p):
    n = p["n"]
    ldo = S.disp(S.ctx.pinnet[(f"U{n + 5}", "10")])          # the PD controller's own 3.3 V rail (VPWR of the CC protector)
    X0, Y0 = 20.32, 30.48
    # row 1: connector and protection, PD controller (the VBUS rail runs from one into the other)
    (s1, vbus), b1 = P.fit(S, lambda T, x, y: lay_usb1.connector(T, n, x, y, ldo), X0, Y0)
    (s2, _), b2 = P.fit(S, lambda T, x, y: lay_usb2.pd_controller(T, n, x, y, ldo, vbus), b1[2] + GAP, Y0)
    # row 2: charger controller; the two small supplies stand one above the other beside it
    s1.min_y1 = s2.min_y1 = max(b1[3], b2[3])                # one bottom edge for the row
    y2 = max(b1[3], b2[3]) + GAP
    (s3, _), b3 = P.fit(S, lambda T, x, y: lay_usb3.charger(T, n, x, y, ldo), X0, y2)
    s5, b5 = P.fit(S, lambda T, x, y: lay_usb5.ldo9(T, n, x, y, ldo), b3[2] + GAP, y2)
    s6, b6 = P.fit(S, lambda T, x, y: lay_usb5.buck5(T, n, x, y, ldo), b5[0], b5[3] + GAP)
    s5.min_x1 = s6.min_x1 = s2.min_x1 = max(b2[2], b5[2], b6[2])    # one right edge for the right-hand column
    # row 3: the power path
    y3 = max(b3[3], b6[3]) + GAP
    s4, b4 = P.fit(S, lambda T, x, y: lay_usb4.power_stage(T, n, x, y, ldo), X0, y3)
    s1.max_x0 = s3.max_x0 = s4.max_x0 = min(b1[0], b3[0], b4[0])    # one left edge for the left column
    s5.max_x0 = s6.max_x0 = min(b5[0], b6[0])                       # and for the right-hand column
    # notes: each one next to the circuit it describes where there is room: the CC protector note in the empty band over the
    # VBUS rail of the connector frame, the charger and gate-drive notes in the strip under the charger frame, the two
    # general ones along the bottom, left of the title block. Numbered in reading order.
    right = max(b[2] for b in (b1, b2, b3, b4, b5, b6))
    notes = S.ctx.cons.get("notes", {}).get(S.ctx.block, [])
    if len(notes) == 5:
        P.notes_block(S, X0 + 3.0, s1.oy - 1.0, notes[:1], width=125.0)
        P.notes_block(S, X0 + 3.0, b3[3] + 5.0, notes[1:3], width=b3[2] - X0 - 6.0, title="Notes, continued", cols=2, first=2)
        P.notes_block(S, X0 + 1.27, b4[3] + GAP, notes[3:], width=right - 112.0 - 8.0 - X0, title="Notes, continued", cols=2, first=4)
    else:
        P.notes_block(S, X0 + 1.27, b4[3] + GAP, notes, width=right - 112.0 - 8.0 - X0, cols=2)
    S.finish()
