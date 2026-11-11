"""3D models for the production board's parts that KiCad doesn't ship (2026-10-22).

Writes STEP files into Production/3dmodels/ with step_mesh.py (pure Python) and attaches them:
  * from LCSC's EasyEDA library (OBJ meshes in 3dmodels/source/, fetched 2026-10-22; EasyEDA's STEP endpoint is gone):
      - Vishay_PowerPAIR_3x3S.step   SiZ240DT, LCSC C3289403 (EasyEDA 'POWERPAIR-8_L3.0-W3.0-P0.65-BL-EP')
      - Texas_RUK0020B_WQFN-20-1EP_3x3mm_P0.4mm.step   TPD6S300, LCSC C2649810 ('WQFN-20_L3.0-W3.0-H0.8-P0.40-TL-EP1.7')
    EasyEDA's PowerPAIR mesh is 3.0 x 3.0; Vishay's outline is 3.3 x 3.3 x 0.75, so it is scaled 1.1 in x and y
    (2026-10-29). Both meshes are turned -90 deg about Z: in EasyEDA's frame the PowerPAIR paddles stack along Y and the
    WQFN pin-1 dot sits bottom-left; here they match the footprints (paddles along X, larger one on +X; pin 1 top-left).
  * stand-ins (no model from TI, Coilank or LCSC; envelope only, from the datasheets):
      - TI_MHA0024A_CC2340R5MODA_7x10mm.step  CC2340R5MODA, SWRS349A MHA0024A: 7 x 10 mm substrate, 6.5 x 6.3 mm
        shield, 2.3 mm max; the antenna end (footprint y -5 .. -1.8) is bare substrate with a gold meander.
      - L_Coilank_APS0730.step  APS0730M2R2F, datasheets/aps0730.pdf: 7.6 x 7.8 x 3.1 mm molded body, end terminals.
      - L_Coilank_APS0530.step  APS0530M3R3H (L402/L502), same datasheet: 5.3 x 5.5 x 3.1 mm, terminals 1.1 x 4.3
        (2026-10-29; it used the 2.8 mm Bourns SRP5030T).
      - L_COILMX_MS0520.step  MS0520-3R3M (L402/L502 from 2026-10-30), datasheets/COILMX MS0520-3R3M.pdf: A 5.45 (along
        the terminals) x B 5.2 x C 2.0 max, bottom terminals E 1.0 x D 2.3. Replaced the 3.1 mm APS0530, which hit the cup
        corner fillet at L502.
      - SolderWire-0.15sqmm_1x02_P4mm_standin.step / SolderWire-0.5sqmm_1x01_standin.step: insulated wire stubs for
        the NTC and learning-cycle load wire pads (KiCad has no Connector_Wire models).
      - SolderWire-18AWG_PTFE_from_BCu.step (J108 / J112 PACK wires) and SolderWire-28AWG_PTFE_from_BCu.step (J109-J111,
        J115 / J116 sense wires), 2026-10-29: the pack wires come up from the cells, so these hang below B.Cu (z -1.6):
        the PTFE stub across the SB_BCU_H gap (2.3 mm, B.Cu to the 0.3 mm insulator on the front cells; the wire turns
        along the gap there, mechanical/monolith_shell.py sb_wire_runs), 0.3 mm of bare conductor under B.Cu, the
        conductor through the hole and a 0.5 mm solder fillet and tip on F.Cu. 18 AWG: TE 100G0111-1.00-0, 1.8 mm OD
        (SB_PWIRE_OD), 19/0.25 strand ~1.22 mm. 28 AWG: TE 55A0111-28-9, 0.75 mm OD (SB_KWIRE_OD), ~0.38 mm conductor.
      - Peg_PA12_TPU_sleeve.step (H101-H104), 2026-10-29: the carrier's peg post through its slot (mechanical/
        monolith_cup.py rails(): Ø2.0 CUP_PEG_D, from the rail on B.Cu to POST_GAP 0.3 under the board-face wall, i.e.
        SB_OUT_H 3.2 + 0.5 - 0.3 = 3.4 mm above F.Cu; monolith_shell.py's CUP_PEG_PROUD 0.6 predates the posts reaching
        the wall) and the TPU retaining sleeve on F.Cu (SLEEVE: outer r 2.0, 1.0 mm tall; its r 0.85 bore stretched
        over the r 1.0 post). Centred in the slot (the board floats +-0.3 mm in footprint x).
      - TagConnect_TC2030-IDC-NL_envelope.step (J301 / J302), 2026-10-29: nothing is fitted; an envelope of the
        TC2030-IDC-NL plug-of-nails head for clearance checks, attached hidden ((hide yes): switch it on in the
        footprint's 3D settings). From Tag-Connect's TC2030-IDC-NL datasheet Rev B, sheet 2, whose dimension labels
        didn't survive text extraction, so this is a best reading: nose 0.285 x 0.150 in (7.24 x 3.81) and 0.125 in
        (3.18) tall on the board, head 0.39 x 0.24 in (9.91 x 6.10) to 1.235 in (31.37) overall, three Ø0.9 guide
        pins in the footprint's Ø0.99 NPTH holes, drawn to B.Cu (how far they stand out below it isn't given).
  * copied from DevBoard/3dmodels/ (made by DevBoard/tools/make_3d_*.py): the M24512 UFDFPN-8, the TLC WSFB fuse and
    the ShouHan USB-C 1.6 mm.
No model on purpose: test pads (TestPoint_Pad_D1.0mm: bare copper, nothing fitted).

Run (any Python 3):  python hardware/Production/tools/make_3d_models.py            -> writes the STEP files
                     python hardware/Production/tools/make_3d_models.py --board  -> also sets the model paths on the board's
                                                                           footprints (as text; board closed in KiCad)
make_production.py calls attach_library() so the generated MonolithDev footprints carry the same models.
"""
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROD = os.path.normpath(os.path.join(HERE, ".."))
DEV = os.path.normpath(os.path.join(PROD, "..", "DevBoard"))
OUT = os.path.join(PROD, "3dmodels")
SRC = os.path.join(OUT, "source")
sys.path.insert(0, HERE)
from step_mesh import Mesh, read_obj, write_step  # noqa: E402

P = "${KIPRJMOD}/3dmodels/"
STOCK = "${KICAD10_3DMODEL_DIR}/"
# footprint lib id -> model path. MonolithDev ones also go into the .kicad_mod files (attach_library).
MODELS = {
    "MonolithDev:Vishay_PowerPAIR_3x3S": P + "Vishay_PowerPAIR_3x3S.step",
    "MonolithDev:TI_RUK0020B_WQFN-20-1EP_3x3mm_P0.4mm_EP1.7x1.7mm_Via0.3": P + "Texas_RUK0020B_WQFN-20-1EP_3x3mm_P0.4mm.step",
    "MonolithDev:TI_MHA0024A_CC2340R5MODA_7x10mm": P + "TI_MHA0024A_CC2340R5MODA_7x10mm.step",
    "MonolithDev:L_Coilank_APS0730": P + "L_Coilank_APS0730.step",
    "MonolithDev:ST_UFDFPN-8-1EP_2x3mm_P0.5mm_EP1.2x1.4mm": P + "ST_UFDFPN-8-1EP_2x3mm_P0.5mm.step",
    "MonolithDev:TLC_WSFB_4x3mm": P + "TLC_WSFB_4x3mm.step",
    "MonolithDev:USB_C_Receptacle_ShouHan_TYPE-C_16PCB1.6_IP68": P + "USB_C_Receptacle_ShouHan_TYPE-C_16PCB1.6_IP68.step",
    # stock footprints whose stock model name doesn't exist in KiCad 10's library (board only)
    "Package_SON:Texas_DSG0008A_WSON-8-1EP_2x2mm_P0.5mm_EP0.9x1.6mm":
        STOCK + "Package_SON.3dshapes/WSON-8-1EP_2x2mm_P0.5mm_EP0.9x1.6mm.step",
    "Connector_Wire:SolderWire-0.15sqmm_1x02_P4mm_D0.5mm_OD1.5mm": P + "SolderWire-0.15sqmm_1x02_P4mm_standin.step",
    "Connector_Wire:SolderWire-0.5sqmm_1x01_D0.9mm_OD2.1mm": P + "SolderWire-0.5sqmm_1x01_standin.step",
    "MonolithDev:SolderWire-18AWG_PTFE_1x01_D1.5mm_OD2.3mm": P + "SolderWire-18AWG_PTFE_from_BCu.step",
    "MonolithDev:SolderWire-28AWG_PTFE_1x01_D0.8mm_Pad1.5x1.4mm": P + "SolderWire-28AWG_PTFE_from_BCu.step",
    "MonolithDev:Peg_NPTH_Slot2.6x2.2mm": P + "Peg_PA12_TPU_sleeve.step",
    "Connector:Tag-Connect_TC2030-IDC-NL_2x03_P1.27mm_Vertical": P + "TagConnect_TC2030-IDC-NL_envelope.step",
    "MonolithDev:L_Coilank_APS0530": P + "L_Coilank_APS0530.step",
    "MonolithDev:L_COILMX_MS0520": P + "L_COILMX_MS0520.step",
    # stock models that fit better than the footprint's own (2026-10-29): KiCad's PG-TDSON-8 and HVSSOP-8 footprints
    # name models that aren't in kicad-packages3D (the parts rendered empty), and the C421/C456 T593V is 2.0 mm (V case), not the Kemet D 3.1
    "MonolithDev:Infineon_PG-TDSON-8_6.15x5.15mm_D5-8": STOCK + "Package_TO_SOT_SMD.3dshapes/TDSON-8-1.step",
    "Package_SO:HVSSOP-8-1EP_3x3mm_P0.65mm_EP1.57x1.89mm":
        STOCK + "Package_SO.3dshapes/MSOP-8-1EP_3x3mm_P0.65mm_EP1.95x2.15mm.step",
    "Capacitor_Tantalum_SMD:CP_EIA-7343-31_Kemet-D": STOCK + "Capacitor_Tantalum_SMD.3dshapes/CP_EIA-7343-20_Kemet-V.step",
}
HIDDEN = {"Connector:Tag-Connect_TC2030-IDC-NL_2x03_P1.27mm_Vertical"}   # attached with (hide yes): nothing fitted
FROM_DEV = ["ST_UFDFPN-8-1EP_2x3mm_P0.5mm.step", "TLC_WSFB_4x3mm.step", "USB_C_Receptacle_ShouHan_TYPE-C_16PCB1.6_IP68.step"]

GOLD, SILVER, TIN, WHITE = (0.83, 0.67, 0.13), (0.78, 0.78, 0.8), (0.85, 0.85, 0.85), (0.95, 0.95, 0.95)
SUBSTRATE, MOLD, BLACK = (0.13, 0.32, 0.2), (0.22, 0.22, 0.24), (0.08, 0.08, 0.08)
PTFE, PA12, TPU = (0.92, 0.92, 0.88), (0.45, 0.45, 0.47), (0.15, 0.15, 0.17)
PCB_T = 1.6                                         # board thickness: B.Cu is at z -1.6 in a footprint's model frame


def cc2340r5moda():
    m = Mesh()
    t = 0.9                                         # substrate (the 2.3 mm max height is substrate + shield)
    m.box(SUBSTRATE, -3.5, 3.5, -5.0, 5.0, 0.0, t)
    m.box(SILVER, -3.25, 3.25, -4.75, 1.55, t, 2.2)  # 6.5 x 6.3 shield over the radio, clear of the antenna end
    for i in range(9):                               # castellated pads 1-9 / 16-24 on the long sides, 1.0 mm pitch
        y = 4.4 - i
        m.box(GOLD, -3.5, -3.3, y - 0.3, y + 0.3, 0.0, t)
        m.box(GOLD, 3.3, 3.5, y - 0.3, y + 0.3, 0.0, t)
    for i in range(6):                               # pads 10-15 along the end opposite the antenna
        x = -2.5 + i
        m.box(GOLD, x - 0.3, x + 0.3, -5.0, -4.8, 0.0, t)
    zt = (t, t + 0.03)                               # printed antenna: a meander across the bare end
    for k, y in enumerate((2.2, 2.8, 3.4, 4.0, 4.6)):
        m.box(GOLD, -2.6, 2.6, y - 0.12, y + 0.12, *zt)
        x = 2.6 if k % 2 == 0 else -2.6
        if k < 4:
            m.box(GOLD, x - 0.12, x + 0.12, y, y + 0.6, *zt)
    m.cylinder(WHITE, -2.9, 4.55, 0.15, t, t + 0.02, 12)   # pin-1 mark (pad 1 is at footprint (-3.25, -4.4))
    return m


def aps0730():
    m = Mesh()
    m.box(MOLD, -3.8, 3.8, -3.9, 3.9, 0.12, 3.1)
    for s in (-1, 1):                                # bottom terminals over the pads (x +-2.55, 2.3 x 7.2), up the ends
        m.box(SILVER, s * 1.45, s * 3.85, -3.6, 3.6, 0.0, 0.12)
        m.box(SILVER, s * 3.8, s * 3.85, -3.6, 3.6, 0.12, 1.2)
    return m


def aps0530():
    m = Mesh()
    m.box(MOLD, -2.65, 2.65, -2.75, 2.75, 0.12, 3.1)
    for s in (-1, 1):                                # bottom terminals (E 1.1 x D 4.3), up the ends
        m.box(SILVER, s * 1.55, s * 2.7, -2.15, 2.15, 0.0, 0.12)
        m.box(SILVER, s * 2.65, s * 2.7, -2.15, 2.15, 0.12, 1.0)
    return m


def ms0520():
    m = Mesh()
    m.box(MOLD, -2.725, 2.725, -2.6, 2.6, 0.1, 2.0)
    for s in (-1, 1):                                # bottom terminals (E 1.0 x D 2.3), up the ends
        m.box(SILVER, s * 1.725, s * 2.775, -1.15, 1.15, 0.0, 0.1)
        m.box(SILVER, s * 2.725, s * 2.775, -1.15, 1.15, 0.1, 0.8)
    return m


def wire(pitch, n, od, cond):
    m = Mesh()
    for k in range(n):
        x = k * pitch
        m.cylinder(BLACK, x, 0, od / 2, 0.0, 6.0, 16)
        m.cylinder(TIN, x, 0, cond / 2, 6.0, 6.6, 12)
    return m


def wire_from_bcu(od, cond, fillet_r):
    """A PTFE wire soldered in a plated hole from the B.Cu side (the pack wires come up from the cells)."""
    m = Mesh()
    gap, bare, fillet, tip = 2.3, 0.3, 0.35, 0.5     # B.Cu to the cell insulator, strip under B.Cu, fillet, tip height
    m.cylinder(PTFE, 0, 0, od / 2, -PCB_T - gap, -PCB_T - bare, 16)
    m.cylinder(TIN, 0, 0, cond / 2, -PCB_T - bare, fillet, 12)
    m.frustum(TIN, 0, 0, fillet_r, cond / 2, 0.0, fillet, 16)    # solder cone from the pad up the conductor
    m.cylinder(TIN, 0, 0, cond / 2, fillet, tip, 12)
    return m


def peg_sleeve():
    m = Mesh()
    m.cylinder(PA12, 0, 0, 1.0, -PCB_T, 3.4, 24)    # Ø2.0 post, B.Cu (rail face) to 0.3 under the board-face wall
    m.tube(TPU, 0, 0, 2.0, 1.0, 0.0, 1.0, 24)       # TPU sleeve on F.Cu, bore stretched over the post
    return m


def tc2030_idc_nl():
    m = Mesh()
    m.box(MOLD, -3.62, 3.62, -1.905, 1.905, 0.0, 3.18)       # nose on the board over the 2 x 3 pads
    m.box(MOLD, -4.953, 4.953, -3.048, 3.048, 3.18, 31.37)   # head body up to the ribbon
    for x, y in ((-2.54, 0.0), (2.54, 1.016), (2.54, -1.016)):   # guide pins in the NPTH holes (footprint y = -Y here)
        m.cylinder(SILVER, x, y, 0.45, -PCB_T, 0.0, 12)
    return m


def easyeda(src, sxy=1.0):
    m = Mesh()
    m.merge(read_obj(os.path.join(SRC, src)), rot_z=-90)
    if sxy != 1.0:                                   # mesh drawn undersize: scale the body in x and y only
        m.parts = {c: [[(x * sxy, y * sxy, z) for x, y, z in p] for p in ps] for c, ps in m.parts.items()}
    return m


BUILD = {
    "Vishay_PowerPAIR_3x3S.step": lambda: easyeda("POWERPAIR-8_L3.0-W3.0-P0.65-BL-EP_C3289403_easyeda.obj", 1.1),
    "Texas_RUK0020B_WQFN-20-1EP_3x3mm_P0.4mm.step": lambda: easyeda("WQFN-20_L3.0-W3.0-H0.8-P0.40-TL-EP1.7_C2649810_easyeda.obj"),
    "TI_MHA0024A_CC2340R5MODA_7x10mm.step": cc2340r5moda,
    "L_Coilank_APS0730.step": aps0730,
    "L_Coilank_APS0530.step": aps0530,
    "L_COILMX_MS0520.step": ms0520,
    "SolderWire-0.15sqmm_1x02_P4mm_standin.step": lambda: wire(4.0, 2, 1.5, 0.5),
    "SolderWire-0.5sqmm_1x01_standin.step": lambda: wire(0.0, 1, 2.1, 0.9),
    "SolderWire-18AWG_PTFE_from_BCu.step": lambda: wire_from_bcu(1.8, 1.22, 1.1),     # pad Ø2.3
    "SolderWire-28AWG_PTFE_from_BCu.step": lambda: wire_from_bcu(0.75, 0.38, 0.65),   # pad 1.5 x 1.4
    "Peg_PA12_TPU_sleeve.step": peg_sleeve,
    "TagConnect_TC2030-IDC-NL_envelope.step": tc2030_idc_nl,
}


def model_block(path, indent, hide=False):
    """KiCad 10's model block; hide=True adds (hide yes), as KiCad writes it for a model switched off."""
    t = indent
    h = "%s\t(hide yes)\n" % t if hide else ""
    return ('%s(model "%s"\n%s%s\t(offset\n%s\t\t(xyz 0 0 0)\n%s\t)\n%s\t(scale\n%s\t\t(xyz 1 1 1)\n%s\t)\n'
            '%s\t(rotate\n%s\t\t(xyz 0 0 0)\n%s\t)\n%s)' % ((t, path, h) + (t,) * 10))


def _end(s, i):
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


def set_model(blk, path, indent, hide=False):
    """Replace every (model ...) at this indent in a footprint block with one model, or add it before the end."""
    spans = [(m.start(), _end(blk, m.start() + len(indent) + 1)) for m in re.finditer(r"\n%s\(model " % indent, blk)]
    for a, b in reversed(spans):
        blk = blk[:a] + blk[b:]
    i = blk.rstrip().rfind(")")
    return blk[:i].rstrip() + "\n" + model_block(path, indent, hide) + "\n" + indent[:-1] + blk[i:]


def attach_library(pretty):
    """Set the model on each MonolithDev footprint in MODELS (called by make_production.py)."""
    for lib, path in MODELS.items():
        nick, name = lib.split(":", 1)
        f = os.path.join(pretty, name + ".kicad_mod")
        if nick != "MonolithDev" or not os.path.exists(f):
            continue
        s = open(f, encoding="utf-8").read()
        s = set_model(s.rstrip() + "\n", path, "\t", lib in HIDDEN)
        open(f, "w", encoding="utf-8", newline="\n").write(s)


def attach_board(pcb):
    """Set the model paths on the board's footprint instances (text edit, so KiCad 10's python isn't involved)."""
    lock = os.path.join(os.path.dirname(pcb), "~" + os.path.basename(pcb) + ".lck")
    if os.path.exists(lock):
        sys.exit("%s is open in KiCad: save and close the PCB editor first" % pcb)
    s = open(pcb, encoding="utf-8").read()
    reps, count = [], {}
    for m in re.finditer(r'\n\t\(footprint "([^"]+)"', s):
        if m.group(1) in MODELS:
            a = m.start() + 1
            b = _end(s, a)
            reps.append((a, b, set_model(s[a:b], MODELS[m.group(1)], "\t\t", m.group(1) in HIDDEN)))
            count[m.group(1)] = count.get(m.group(1), 0) + 1
    for a, b, t in reversed(reps):
        s = s[:a] + t + s[b:]
    open(pcb, "w", encoding="utf-8", newline="\n").write(s)
    for k, n in sorted(count.items()):
        print("%-75s x%d" % (k, n))


def main():
    os.makedirs(OUT, exist_ok=True)
    for name in FROM_DEV:
        shutil.copy2(os.path.join(DEV, "3dmodels", name), os.path.join(OUT, name))
        print("copied   %s" % name)
    for name, build in BUILD.items():
        n = write_step(os.path.join(OUT, name), name[:-5], build())
        print("wrote    %-50s %5d faces" % (name, n))
    if "--board" in sys.argv:
        attach_board(os.path.join(PROD, "Monolith.kicad_pcb"))


if __name__ == "__main__":
    main()
