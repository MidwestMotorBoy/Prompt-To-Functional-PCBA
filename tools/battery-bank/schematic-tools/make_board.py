"""Create the production board file with its stack-up and outline (2026-10-17; side outline and 1.6 mm 2026-10-18).
Run once; later runs patch an existing board that has no copper yet.

Stack-up: 6 layers, 1.6 mm (chosen 2026-10-18 for cost; was 0.8 mm), 2 oz outer / 0.5 oz inner, ENIG, vias filled
and capped (JLC default on 6+ layers). The dielectric split is a symmetric approximation that sums to 1.6 mm; no net
here is impedance-controlled, so set it to JLC's stack at order time. JLC multilayer vias at 1.6 mm: 0.15 mm hole /
0.25 mm via minimum (surcharge below 0.2 mm or under a 0.45 mm via); the 0.1 mm hole option needs a board <= 1 mm.

Outline: the side board of the one-piece tray, from mechanical/monolith_shell.py (sb_* values, also written to
mechanical/monolith_side_pcb.dxf): 43.2 mm wide, its bottom corners notched around the tray's screw pillars, centred on
(100, 100). KiCad x = the tray's y (left = the C1 / PACK- side), KiCad y = down the pack (top edge = the port end).
F.Cu faces the cup wall (outer face), B.Cu faces the cells. The outline leaves gaps for the connector notches
(PORTS_X), and place_ports() puts J401/J501 there.
(History: 40.5 mm then 45.5 mm top-cap boards, 2026-10-17. The old bottom end board with the vent,
monolith_bottom_pcb.dxf, is not this board; it was removed from the repo on 2026-10-29 and is in Production 5cf521e.)

Run: "C:/Program Files/KiCad/10.0/bin/python.exe" -I hardware/Production/tools/make_board.py [--force] [--keep-copper]
     ... make_board.py --mech        (only places the sense wire holes, PACK wire holes, front-cell SMD NTCs and peg holes, after Update PCB
                                      from Schematic)
     ... make_board.py --keepouts    (redraws the KO_* mechanical keep-out rule areas from mechanical/monolith_shell.py)
Enclosure (2026-10-21): the cup (mechanical/monolith_cup.py). The board rides on the PA12 carrier's rails and pegs, F.Cu
faces the cup wall (0.5 mm over the tallest part), B.Cu faces the cells, and a gap filler joins B.Cu to the two front
cells over the power stages. The aluminium cover, its standoffs and the side tray are retired.
"""
import os
import shutil
import sys
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
PROD = os.path.normpath(os.path.join(HERE, ".."))
DEV = os.path.normpath(os.path.join(PROD, "..", "DevBoard"))
OUT = os.path.join(PROD, "Monolith.kicad_pcb")
sys.path.insert(0, os.path.normpath(os.path.join(PROD, "..", "mechanical")))
import monolith_shell as M  # noqa: E402  (side-board geometry: one source for the cup and the board)
sys.path.insert(0, HERE)
import make_production as MP  # noqa: E402  (slot and peg-hole references)

CX, CY = 100.0, 100.0
HALF_W = M.sb_board_w / 2                     # 21.6
Z_MID = (M.sb_zb0 + M.sb_zb1) / 2             # tray z of the board centre
def Y(z):                                     # tray z -> KiCad y (port end at the top)
    return CY - (z - Z_MID)
Y_TOP, Y_BOT, Y_NOTCH = Y(M.sb_zb1), Y(M.sb_zb0), Y(M.sb_notch_z)
NOTCH_X = M.sb_notch_y                        # bottom corners cut away for |x - CX| > NOTCH_X, below Y_NOTCH
# USB-C notches on the top edge: connector centres along x, 13 mm apart. The footprint's own Edge.Cuts draws the
# 10.2 x 5.65 notch (origin = board edge), so the board outline leaves a 10.2 mm gap at each.
PORTS_X = {"J501": CX - M.SB_PORT_Y, "J401": CX + M.SB_PORT_Y}
NOTCH_HALF = 5.1

COPPER = [("F.Cu", 0.07), ("In1.Cu", 0.0175), ("In2.Cu", 0.0175), ("In3.Cu", 0.0175), ("In4.Cu", 0.0175), ("B.Cu", 0.07)]
DIELECTRIC = [("prepreg", 0.20, 4.4), ("core", 0.30, 4.6), ("prepreg", 0.39, 4.4), ("core", 0.30, 4.6), ("prepreg", 0.20, 4.4)]
THICK = round(sum(t for _, t in COPPER) + sum(t for _, t, _ in DIELECTRIC), 4)
assert abs(THICK - M.SB_PCB_T) < 1e-6, "stack-up %g mm != mechanical SB_PCB_T %g mm" % (THICK, M.SB_PCB_T)


LAYERS = """\t(layers
\t\t(0 "F.Cu" signal)
\t\t(4 "In1.Cu" power "In1.Cu (GND)")
\t\t(6 "In2.Cu" signal "In2.Cu (signal V + 3V3)")
\t\t(8 "In3.Cu" signal "In3.Cu (signal H + 5V)")
\t\t(10 "In4.Cu" power "In4.Cu (GND)")
\t\t(2 "B.Cu" signal)
\t\t(9 "F.Adhes" user "F.Adhesive")
\t\t(11 "B.Adhes" user "B.Adhesive")
\t\t(13 "F.Paste" user)
\t\t(15 "B.Paste" user)
\t\t(5 "F.SilkS" user "F.Silkscreen")
\t\t(7 "B.SilkS" user "B.Silkscreen")
\t\t(1 "F.Mask" user)
\t\t(3 "B.Mask" user)
\t\t(17 "Dwgs.User" user "User.Drawings")
\t\t(19 "Cmts.User" user "User.Comments")
\t\t(21 "Eco1.User" user "User.Eco1")
\t\t(23 "Eco2.User" user "User.Eco2")
\t\t(25 "Edge.Cuts" user)
\t\t(27 "Margin" user)
\t\t(31 "F.CrtYd" user "F.Courtyard")
\t\t(29 "B.CrtYd" user "B.Courtyard")
\t\t(35 "F.Fab" user)
\t\t(33 "B.Fab" user)
\t)"""


def u():
    return str(uuid.uuid4())


def stackup():
    s = ['\t\t(stackup',
         '\t\t\t(layer "F.SilkS"\n\t\t\t\t(type "Top Silk Screen")\n\t\t\t)',
         '\t\t\t(layer "F.Paste"\n\t\t\t\t(type "Top Solder Paste")\n\t\t\t)',
         '\t\t\t(layer "F.Mask"\n\t\t\t\t(type "Top Solder Mask")\n\t\t\t\t(thickness 0.01)\n\t\t\t)']
    for i, (name, t) in enumerate(COPPER):
        s.append('\t\t\t(layer "%s"\n\t\t\t\t(type "copper")\n\t\t\t\t(thickness %g)\n\t\t\t)' % (name, t))
        if i < len(DIELECTRIC):
            kind, dt, er = DIELECTRIC[i]
            s.append('\t\t\t(layer "dielectric %d"\n\t\t\t\t(type "%s")\n\t\t\t\t(thickness %g)\n\t\t\t\t(material "FR4")\n'
                     '\t\t\t\t(epsilon_r %g)\n\t\t\t\t(loss_tangent 0.02)\n\t\t\t)' % (i + 1, kind, dt, er))
    s += ['\t\t\t(layer "B.Mask"\n\t\t\t\t(type "Bottom Solder Mask")\n\t\t\t\t(thickness 0.01)\n\t\t\t)',
          '\t\t\t(layer "B.Paste"\n\t\t\t\t(type "Bottom Solder Paste")\n\t\t\t)',
          '\t\t\t(layer "B.SilkS"\n\t\t\t\t(type "Bottom Silk Screen")\n\t\t\t)',
          '\t\t\t(copper_finish "ENIG")\n\t\t\t(dielectric_constraints no)', '\t\t)']
    return "\n".join(s)


def line(x0, y0, x1, y1):
    return ('\t(gr_line\n\t\t(start %g %g)\n\t\t(end %g %g)\n\t\t(stroke\n\t\t\t(width 0.05)\n\t\t\t(type default)\n'
            '\t\t)\n\t\t(layer "Edge.Cuts")\n\t\t(uuid "%s")\n\t)' % (x0, y0, x1, y1, u()))


def outline():
    """Top edge with the two connector gaps, straight sides, bottom corners notched around the screw pillars."""
    xl, xr = CX - HALF_W, CX + HALF_W
    xs = [xl] + [x for c in sorted(PORTS_X.values()) for x in (c - NOTCH_HALF, c + NOTCH_HALF)] + [xr]
    g = [line(x0, Y_TOP, x1, Y_TOP) for x0, x1 in zip(xs[0::2], xs[1::2])]
    pts = [(xr, Y_TOP), (xr, Y_NOTCH), (CX + NOTCH_X, Y_NOTCH), (CX + NOTCH_X, Y_BOT),
           (CX - NOTCH_X, Y_BOT), (CX - NOTCH_X, Y_NOTCH), (xl, Y_NOTCH), (xl, Y_TOP)]
    g += [line(*p, *q) for p, q in zip(pts[:-1], pts[1:])]
    return "\n".join(g)


def block_end(s, i):
    d = 0
    while True:
        c = s[i]
        if c == '"':
            i += 1
            while s[i] != '"':
                i += 2 if s[i] == "\\" else 1
        elif c == "(":
            d += 1
        elif c == ")":
            d -= 1
            if d == 0:
                return i + 1
        i += 1


def patch(path, layers):
    """Put the stack-up, 6-layer table, thickness and outline into an existing board, leaving footprints alone."""
    s = open(path, encoding="utf-8").read()
    copper = __import__("re").findall(r"\n\t\((segment|via|arc|zone)\b", s)
    assert not copper or "--keep-copper" in sys.argv, \
        "board has %d copper items; patch it in KiCad, or pass --keep-copper to leave them where they are" % len(copper)
    if copper:
        print("kept %d copper items as they are (not moved with the outline or the ports)" % len(copper))
    s = __import__("re").sub(r"\(general\n\t\t\(thickness [\d.]+\)", "(general\n\t\t(thickness %g)" % THICK, s, count=1)
    a = s.index("\n\t(layers") + 1
    s = s[:a] + layers.lstrip("\n") + s[block_end(s, a + 1):]
    a = s.index("\n\t(setup") + 1
    st = s.find("\n\t\t(stackup", a, block_end(s, a + 1))
    if st >= 0:
        s = s[:st + 1] + stackup().lstrip("\n") + s[block_end(s, st + 3):]
    else:
        s = s[:a] + "\t(setup\n" + stackup() + s[a + len("\t(setup"):]
    # redraw the outline: drop top-level Edge.Cuts lines/arcs (footprint notches stay with their footprints)
    re = __import__("re")
    spans = []
    for m in re.finditer(r"\n\t\((gr_line|gr_arc)\b", s):
        a = m.start() + 2
        b = block_end(s, a)
        if '(layer "Edge.Cuts")' in s[a:b]:
            spans.append((m.start(), b))
    for a, b in reversed(spans):
        s = s[:a] + s[b:]
    s = s.rstrip()[:-1].rstrip() + "\n" + outline() + "\n)\n"
    open(path, "w", encoding="utf-8", newline="\n").write(s)
    print("patched %s: %g mm, 6 layers, stack-up and side outline %.1f x %.2f mm; footprints untouched"
          % (path, THICK, 2 * HALF_W, Y_BOT - Y_TOP))


def place_ports(path):
    """Put J401/J501 on the top edge: footprint origin on the edge, notch pointing into the board (180 deg), locked."""
    import pcbnew
    b = pcbnew.LoadBoard(path)
    for ref, x in PORTS_X.items():
        f = b.FindFootprintByReference(ref)
        if f is None:
            print("no %s on the board (run Update PCB from Schematic)" % ref)
            continue
        if f.IsFlipped():
            f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        f.SetOrientationDegrees(180)
        f.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(Y_TOP)))
        f.SetLocked(True)
        print("%s at (%.2f, %.2f) 180 deg, locked" % (ref, x, Y_TOP))
    pcbnew.SaveBoard(path, b)


def place_mech(path):
    """Put the five slots (J109-J111, J115, J116) at sb_slots(), the PACK wire holes (J108, J112) at sb_pack_holes(),
    the front-cell SMD NTCs (TH101, TH104) at sb_ntc_smd() and the four carrier peg holes (H101-H104) at CUP_PEGS,
    from mechanical/monolith_shell.py: F.Cu, 0 deg (NTCs on B.Cu, 90 deg), locked. Only moves those footprints; run after Update PCB
    from Schematic, with the board closed in KiCad (or reload it afterwards)."""
    import pcbnew
    lock = os.path.join(os.path.dirname(path), "~" + os.path.basename(path) + ".lck")
    if os.path.exists(lock):
        sys.exit("%s is open in KiCad (lock file %s): save and close the PCB editor first" % (path, lock))
    want = {MP.SLOT_REFS[n]: M.kicad(y, z) for n, (y, z, _) in M.sb_slots().items()}
    want.update({MP.WIRE_REFS[n]: M.kicad(y, z) for n, (y, z, _) in M.sb_pack_holes().items()})
    want.update({ref: M.kicad(y, z) for ref, (y, z) in zip(MP.PEGS, M.CUP_PEGS)})
    want.update({MP.NTC_REFS[c]: M.kicad(y, z) for c, (y, z) in M.sb_ntc_smd().items()})
    turn = {ref: 90 for ref in MP.NTC_REFS.values()}   # the 0402's pads one above the other, along KiCad y
    bcu = set(MP.NTC_REFS.values())
    b = pcbnew.LoadBoard(path)
    missing = [r for r in want if b.FindFootprintByReference(r) is None]
    if missing:
        sys.exit("not on the board: %s. In the PCB editor run Tools > Update PCB from Schematic (F8), drop the new "
                 "footprints anywhere, save, close the PCB editor, then run this again. Board not written." % ", ".join(missing))
    for ref, (x, y) in want.items():
        f = b.FindFootprintByReference(ref)
        if f.IsFlipped() != (ref in bcu):
            f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        f.SetOrientationDegrees(turn.get(ref, 0))
        f.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)))
        f.SetLocked(True)
        print("%s at (%.3f, %.3f) %d deg, %s, locked" % (ref, x, y, turn.get(ref, 0), "B.Cu" if ref in bcu else "F.Cu"))
    pro = path[:-len(".kicad_pcb")] + ".kicad_pro"   # KiCad 10's SaveBoard rewrites the project file: keep ours
    keep = open(pro, "rb").read()
    pcbnew.SaveBoard(path, b)
    open(pro, "wb").write(keep)


def keepout_list():
    """Mechanical keep-outs for the cup as (name, layers, polygon, rules), all from mechanical/monolith_shell.py.
    rules: subset of footprints / tracks / vias / pour (each one is 'not allowed' inside). The peg holes need none:
    their footprints carry courtyards on both faces."""
    k = M.kicad

    def rect(x0, y0, x1, y1):
        y0, y1 = max(min(y0, y1), Y_TOP), min(max(y0, y1), Y_BOT)   # clipped to the board
        return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]

    def yz(y0, y1, z0, z1):  # monolith_shell (y, z) span -> KiCad rect
        (xa, ya), (xb, yb) = k(y0, z1), k(y1, z0)
        return rect(xa, ya, xb, yb)
    out = []
    # (no KO_F_cup_vent: the cup has no vent since 2026-10-28)
    # (no KO_F_above_antenna: Logan removed it from the board on 2026-10-23)
    # both faces: the top edge bears on the top wall's inside face beyond |x| = SB_STOP_Y0
    for side, (x0, x1) in (("L", (CX - HALF_W, CX - M.SB_STOP_Y0)), ("R", (CX + M.SB_STOP_Y0, CX + HALF_W))):
        out.append(("KO_top_stop_" + side, ["F.Cu", "B.Cu"], rect(x0, Y_TOP, x1, Y_TOP + 1.0), {"footprints"}))
    # B.Cu: the carrier rails bear on the board along the front cells' tangents, split where the gap filler is
    for y0, y1, z0, z1 in M.cup_rails():
        name = "KO_B_rail_%s_%s" % ("L" if y0 < 0 else "R", "bottom" if z1 <= M.CUP_RAIL_GAP[0] else "top")
        out.append((name, ["B.Cu"], yz(y0, y1, z0, z1), {"footprints"}))
    # B.Cu: the gap filler from the board to the two front cells (solid copper and thermal vias there, no parts)
    # except a notch at the zone's outer edge round each front-cell SMD NTC (sb_ntc_smd()), which sits under the gel
    ntc = M.sb_ntc_smd()
    for side, sy, c in (("L", -1, "C1"), ("R", 1, "C4")):
        y0, y1 = sorted((sy * M.CUP_FILL_Y[0], sy * M.CUP_FILL_Y[1]))
        poly = yz(y0, y1, *M.CUP_FILL_Z)                    # x0 y0, x1 y0, x1 y1, x0 y1 (KiCad, y down)
        (xa, ya), (xb, _), (_, yb) = poly[0], poly[1], poly[2]
        _, cy = k(*ntc[c])
        d, h = M.SB_NTC_NOTCH
        if sy > 0:   # notch in the right edge, x = xb
            poly = [(xa, ya), (xb, ya), (xb, cy - h), (xb - d, cy - h), (xb - d, cy + h), (xb, cy + h), (xb, yb), (xa, yb)]
        else:        # notch in the left edge, x = xa
            poly = [(xa, ya), (xb, ya), (xb, yb), (xa, yb), (xa, cy + h), (xa + d, cy + h), (xa + d, cy - h), (xa, cy - h)]
        out.append(("KO_B_gap_filler_" + side, ["B.Cu"], poly, {"footprints"}))
    # B.Cu: nickel tails behind the board (the CELL2 tail and its kink, CELL1 / CELL3 down the gap)
    for n, (y0, y1, z0, z1) in zip(["CELL2", "CELL1", "CELL3"], M.sb_tail_runs()):   # sb_tail_runs() order
        out.append(("KO_B_tail_" + n, ["B.Cu"], yz(y0, y1, z0, z1), {"footprints"}))
    # B.Cu: the PACK power and Kelvin wires cross the gap to their holes and slots (BCU_WIRE_RUNS): no parts at all
    for n, (y0, y1, z0, z1) in zip(["PACK-", "PACK+", "1N", "4P"], M.sb_wire_runs()):   # sb_wire_runs() order
        out.append(("KO_B_wire_" + n.replace("+", "P").replace("-", "N"), ["B.Cu"], yz(y0, y1, z0, z1), {"footprints"}))
    return out


def zone_text(name, layers, poly, rules):
    """One keep-out rule area as board-file text (the format KiCad 10 writes)."""
    def r(k):
        return "not_allowed" if k in rules else "allowed"
    pts = " ".join("(xy %g %g)" % (round(x, 4), round(y, 4)) for x, y in poly)
    return ('\t(zone\n\t\t(layers %s)\n\t\t(uuid "%s")\n\t\t(name "%s")\n\t\t(hatch edge 0.5)\n'
            '\t\t(connect_pads yes\n\t\t\t(clearance 0)\n\t\t)\n\t\t(min_thickness 0.25)\n'
            '\t\t(keepout\n\t\t\t(tracks %s)\n\t\t\t(vias %s)\n\t\t\t(pads allowed)\n\t\t\t(copperpour %s)\n'
            '\t\t\t(footprints %s)\n\t\t)\n\t\t(placement\n\t\t\t(enabled no)\n\t\t\t(sheetname "")\n\t\t)\n'
            '\t\t(fill\n\t\t\t(thermal_gap 0.5)\n\t\t\t(thermal_bridge_width 0.5)\n\t\t\t(island_removal_mode 0)\n\t\t)\n'
            '\t\t(polygon\n\t\t\t(pts\n\t\t\t\t%s\n\t\t\t)\n\t\t)\n\t)'
            % (" ".join('"%s"' % l for l in layers), u(), name, r("tracks"), r("vias"), r("pour"), r("footprints"), pts))


def add_keepouts(path):
    """Draw keepout_list() as named rule areas (replacing earlier KO_* areas) plus a B.Cu height note on
    Cmts.User, so DRC flags parts that land on them. Board must be closed in KiCad. Edits the file as text: KiCad 10's
    python can't build zone outlines or iterate the board's drawings."""
    import re
    lock = os.path.join(os.path.dirname(path), "~" + os.path.basename(path) + ".lck")
    if os.path.exists(lock):
        sys.exit("%s is open in KiCad (lock file %s): save and close the PCB editor first" % (path, lock))
    s = open(path, encoding="utf-8").read()
    spans = []
    for m in re.finditer(r"\n\t\((zone|gr_text)\b", s):
        e = block_end(s, m.start() + 2)
        blk = s[m.start():e]
        if (m.group(1) == "zone" and '(name "KO_' in blk and "(keepout" in blk) or \
                blk.startswith('\n\t(gr_text "KO_NOTE'):
            spans.append((m.start(), e))
    for a, e in reversed(spans):
        s = s[:a] + s[e:]
    add = []
    for name, layers, poly, rules in keepout_list():
        add.append(zone_text(name, layers, poly, rules))
        print("%-22s %-14s %s" % (name, "+".join(layers), ", ".join(sorted(rules)) + " not allowed"))
    note = ("KO_NOTE B.Cu (faces the cells, hand-soldered): parts <= %g mm tall; up to ~5 mm only in the centre strip "
            "x 96-104 or beyond 18 mm from centre. No heat sources on B.Cu. Gap filler zones: solid copper + thermal vias "
            "to the power stages. F.Cu: parts <= %g mm (cup wall 0.5 mm above)." % (M.SB_BCU_H, M.SB_OUT_H))
    add.append('\t(gr_text "%s"\n\t\t(at %g %g 0)\n\t\t(layer "Cmts.User")\n\t\t(uuid "%s")\n\t\t(effects\n'
               '\t\t\t(font\n\t\t\t\t(size 0.8 0.8)\n\t\t\t)\n\t\t)\n\t)' % (note, CX, round(Y_BOT + 4, 4), u()))
    s = s.rstrip()[:-1].rstrip() + "\n" + "\n".join(add) + "\n)\n"
    open(path, "w", encoding="utf-8", newline="\n").write(s)
    print("removed %d old KO_* items, wrote %d keep-outs and the KO_NOTE" % (len(spans), len(add) - 1))


def main():
    if "--mech" in sys.argv:
        place_mech(OUT)
        return
    if "--keepouts" in sys.argv:
        add_keepouts(OUT)
        return
    if os.path.exists(OUT) and "--force" not in sys.argv:
        patch(OUT, LAYERS)
        place_ports(OUT)
        if not os.path.exists(os.path.join(PROD, "Monolith.kicad_dru")):
            shutil.copy2(os.path.join(DEV, "MonolithDev.kicad_dru"), os.path.join(PROD, "Monolith.kicad_dru"))
        return
    dev = open(os.path.join(DEV, "MonolithDev.kicad_pcb"), encoding="utf-8").read()
    a = dev.index("\t(pad_to_mask_clearance")  # the setup block after the stack-up, up to its end
    b = dev.index("\n\t(footprint")
    rest_of_setup = dev[a:b].rstrip()
    rest_of_setup = rest_of_setup[:rest_of_setup.rfind(")")].rstrip()  # drop the closing ')' of (setup
    layers = LAYERS
    text = "\n".join([
        "(kicad_pcb", "\t(version 20260206)", '\t(generator "pcbnew")', '\t(generator_version "10.0")',
        "\t(general\n\t\t(thickness %g)\n\t\t(legacy_teardrops no)\n\t)" % THICK, '\t(paper "A4")',
        '\t(title_block\n\t\t(title "Monolith production board")\n\t\t(date "2026-10-17")\n\t\t(rev "P0")\n'
        '\t\t(company "Monolith 100 W battery bank")\n\t)',
        layers, "\t(setup", stackup(), rest_of_setup, "\t)", '\t(net 0 "")', outline(), ")", ""])
    open(OUT, "w", encoding="utf-8", newline="\n").write(text)
    shutil.copy2(os.path.join(DEV, "MonolithDev.kicad_dru"), os.path.join(PROD, "Monolith.kicad_dru"))
    print("wrote %s: %g mm, 6 layers; side outline %.1f x %.2f mm" % (OUT, THICK, 2 * HALF_W, Y_BOT - Y_TOP))


if __name__ == "__main__":
    main()
