"""U405 TPD2S300 (WCSP-9) -> TPD6S300 (WQFN-20, 3 x 3 mm) on production (2026-10-18).

The TPD2S300's 0.4 mm-pitch centre ball needs a 0.15 mm via-in-pad, below JLC's no-surcharge hole size. The TPD6S300
is the same TI port-protector family in a WQFN with perimeter pads and an exposed pad, so it fans out with standard
0.3 mm vias. Datasheet: datasheets/tpd6s300.pdf (SLVSDK3C). JLC/LCSC C2649810 (TPD6S300RUKR).

CC keeps short-to-VBUS OVP (24 V DC tolerant) and IEC 61000-4-2 ESD (+-8 kV contact): the TPS25751's own CC pins are
26 V abs max but only +-1 kV HBM. CON_CC 60-120 pF (TPD2S300: 30-120 pF), so C401/C402 (220 pF) stay inside the
TPS25751's 480 pF CC limit. IVPWR 90 uA typ / 135 uA max (TPD2S300: 3.2 uA).
Pins (RUK WQFN-20):
  1 C_SBU1, 2 C_SBU2, 14 SBU2, 15 SBU1: no-connects (nothing uses SBU on production; the connector SBU pins are open).
  3 VBIAS: C451 (0.1 uF, >= 35 V). 4 C_CC1, 5 C_CC2: connector CC. 11 CC2, 12 CC1: TPS25751 CC.
  6 RPD_G2 -> C_CC2, 7 RPD_G1 -> C_CC1: dead-battery Rd while unpowered (the TPD2S300 had them built in).
  9 FLT (open drain) -> SBU_FLT (R441 -> GPIO3). 10 VPWR (2.7-4.5 V) -> LDO_3V3, C452 1 uF.
  7, 13, 18, 21 (EP) GND. 16, 17 N.C.: datasheet says connect to GND. 19 D2, 20 D1 (USB2 ESD): no-connects; D+/D- only
  meet each other (DPDN_DCP) and need no ESD path.
"""
import os
import re

import siz240dt as _s

LIB_ID = "MonolithDev:TPD6S300"
FP_NAME = "TI_RUK0020B_WQFN-20-1EP_3x3mm_P0.4mm_EP1.7x1.7mm_Via0.3"
FOOTPRINT = "MonolithDev:" + FP_NAME
LCSC, MPN, VALUE = "C2649810", "TPD6S300RUKR (TI)", "TPD6S300RUKR"
DATASHEET = "https://www.ti.com/lit/ds/symlink/tpd6s300.pdf"
DESCRIPTION = "USB Type-C CC/SBU short-to-VBUS OVP + IEC ESD, 6 channels, WQFN-20 3x3"
# pin number -> net label, "GND" (power symbol) or "NC" (no-connect flag); labels are the sheet's existing local nets
PIN_NETS = {"4": "C_CC1", "5": "C_CC2", "7": "C_CC1", "6": "C_CC2", "3": "VBIAS", "12": "CC1", "11": "CC2",
            "9": "SBU_FLT", "10": "LDO_3V3", "8": "GND", "13": "GND", "18": "GND", "21": "GND", "16": "GND",
            "17": "GND", "1": "NC", "2": "NC", "14": "NC", "15": "NC", "19": "NC", "20": "NC"}
PINS = [("bidirectional", -16.51, 11.43, 0, "C_CC1", "4"), ("bidirectional", -16.51, 8.89, 0, "C_CC2", "5"),
        ("bidirectional", -16.51, 3.81, 0, "RPD_G1", "7"), ("bidirectional", -16.51, 1.27, 0, "RPD_G2", "6"),
        ("bidirectional", -16.51, -3.81, 0, "C_SBU1", "1"), ("bidirectional", -16.51, -6.35, 0, "C_SBU2", "2"),
        ("bidirectional", -16.51, -8.89, 0, "D1", "20"), ("bidirectional", -16.51, -11.43, 0, "D2", "19"),
        ("bidirectional", 16.51, 11.43, 180, "CC1", "12"), ("bidirectional", 16.51, 8.89, 180, "CC2", "11"),
        ("bidirectional", 16.51, -3.81, 180, "SBU1", "15"), ("bidirectional", 16.51, -6.35, 180, "SBU2", "14"),
        ("open_collector", 16.51, -11.43, 180, "~{FLT}", "9"),
        ("power_in", -2.54, 16.51, 270, "VPWR", "10"), ("passive", 2.54, 16.51, 270, "VBIAS", "3"),
        ("power_in", -2.54, -16.51, 90, "GND", "8"), ("passive", -2.54, -16.51, 90, "GND", "13"),
        ("passive", -2.54, -16.51, 90, "GND", "18"), ("passive", -2.54, -16.51, 90, "GND", "21"),
        ("passive", 2.54, -16.51, 90, "N.C.", "16"), ("passive", 2.54, -16.51, 90, "N.C.", "17")]
KICAD_FP = (r"C:\Program Files\KiCad\10.0\share\kicad\footprints\Package_DFN_QFN.pretty"
            r"\Texas_RUK0020B_WQFN-20-1EP_3x3mm_P0.4mm_EP1.7x1.7mm.kicad_mod")
EP_VIAS = [(-0.45, -0.45), (0.45, -0.45), (-0.45, 0.45), (0.45, 0.45)]  # 0.3 mm drill / 0.5 mm pad: JLC standard


def lib_symbol(name='"MonolithDev:TPD6S300"', short="TPD6S300"):
    body = ('\t\t\t(symbol "%s_0_1"\n\t\t\t\t(rectangle\n\t\t\t\t\t(start -13.97 13.97)\n\t\t\t\t\t(end 13.97 -13.97)\n'
            '\t\t\t\t\t(stroke\n\t\t\t\t\t\t(width 0.254)\n\t\t\t\t\t\t(type default)\n\t\t\t\t\t)\n\t\t\t\t\t(fill\n'
            '\t\t\t\t\t\t(type background)\n\t\t\t\t\t)\n\t\t\t\t)\n\t\t\t)' % short)
    pins = "\n".join(_s._pin(k, x, y, a, n, num) for k, x, y, a, n, num in PINS)
    return "\n".join([
        "\t\t(symbol %s" % name,
        "\t\t\t(pin_names\n\t\t\t\t(offset 1.016)\n\t\t\t)",
        "\t\t\t(exclude_from_sim no)\n\t\t\t(in_bom yes)\n\t\t\t(on_board yes)\n\t\t\t(in_pos_files yes)",
        "\t\t\t(duplicate_pin_numbers_are_jumpers no)",
        _s._prop("Reference", "U", -13.97, 15.24, False),
        _s._prop("Value", "TPD6S300", -13.97, -15.24, False),
        _s._prop("Footprint", FOOTPRINT, 0, 0, True),
        _s._prop("Datasheet", DATASHEET, 0, 0, True),
        _s._prop("Description", DESCRIPTION, 0, 0, True),
        body,
        '\t\t\t(symbol "%s_1_1"\n%s\n\t\t\t)' % (short, pins),
        "\t\t\t(embedded_fonts no)",
        "\t\t)"])


def library_entry():
    txt = lib_symbol('"TPD6S300"')
    return "\n".join(ln[1:] if ln.startswith("\t") else ln for ln in txt.split("\n"))


def footprint():
    """KiCad's RUK0020B land pattern plus four 0.3 mm GND vias in the exposed pad (KiCad's own via version uses 0.2 mm)."""
    t = open(KICAD_FP, encoding="utf-8").read()
    old = os.path.splitext(os.path.basename(KICAD_FP))[0]
    t = t.replace('(footprint "%s"' % old, '(footprint "%s"' % FP_NAME, 1).replace('"%s"' % old, '"%s"' % FP_NAME)
    t = re.sub(r'\(descr "', '(descr "TPD6S300 U405/U505: EP with four 0.3/0.5 mm vias (make_production.py). ', t, count=1)
    vias = "".join('\t(pad "21" thru_hole circle\n\t\t(at %g %g)\n\t\t(size 0.5 0.5)\n\t\t(drill 0.3)\n'
                   '\t\t(layers "*.Cu")\n\t\t(remove_unused_layers no)\n\t\t(zone_connect 2)\n\t)\n' % xy
                   for xy in EP_VIAS)
    i = t.index("\t(embedded_fonts") if "\t(embedded_fonts" in t else t.rstrip().rindex(")")
    return t[:i] + vias + t[i:]
