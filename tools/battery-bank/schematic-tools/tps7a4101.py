"""9 V gate-drive LDO for each BQ25756's DRV_SUP (loss cut 2, adopted 2026-10-23, added to the schematic 2026-10-28).

TI TPS7A4101DGNR: 7-50 V in, 50 mA, adjustable (VREF 1.161-1.185 V), HVSSOP-8 with PowerPAD (DGN). LCSC C111739.
Stable with C_IN >= 1 uF and C_OUT >= 4.7 uF ceramic. EN high > 1.5 V, low < 0.4 V; EN-to-IN and OUT-to-IN
abs max +0.3 V, so the output is diode-ORed onto DRV_SUP (it never sees REGN back through its pass device) and EN
is held low until firmware asks (it is never above IN by more than the 100k-limited current while PACK_P is up).
Pins: 1 OUT, 2 FB, 3/6/7 NC (open or GND), 4 GND, 5 EN, 8 IN, 9 PowerPAD (GND).
Datasheet: SBVS183B (not in datasheets/: ti.com is blocked from the cloud session that added it).
"""
import siz240dt as _s

LIB_ID = "MonolithDev:TPS7A4101"
FOOTPRINT = "Package_SO:HVSSOP-8-1EP_3x3mm_P0.65mm_EP1.57x1.89mm"
LCSC, MPN, VALUE = "C111739", "TPS7A4101DGNR (TI)", "TPS7A4101DGNR"
DATASHEET = "https://www.ti.com/lit/ds/symlink/tps7a4101.pdf"
DESCRIPTION = "50 V 50 mA adjustable LDO with enable, HVSSOP-8 PowerPAD"
# (type, x, y, angle, name, number, hidden): IN/EN left, OUT/FB right, GND + PowerPAD bottom, NC pins hidden in the body
PINS = [("power_in", -10.16, 5.08, 0, "IN", "8", False), ("input", -10.16, -2.54, 0, "EN", "5", False),
        ("power_out", 10.16, 5.08, 180, "OUT", "1", False), ("input", 10.16, -2.54, 180, "FB", "2", False),
        ("power_in", 0, -10.16, 90, "GND", "4", False), ("passive", 0, -10.16, 90, "GND", "9", True),
        ("no_connect", -2.54, 0, 0, "NC", "3", True), ("no_connect", 0, 0, 0, "NC", "6", True),
        ("no_connect", 2.54, 0, 0, "NC", "7", True)]


def lib_symbol(name='"MonolithDev:TPS7A4101"', short="TPS7A4101"):
    body = ('\t\t\t(symbol "%s_0_1"\n\t\t\t\t(rectangle\n\t\t\t\t\t(start -7.62 7.62)\n\t\t\t\t\t(end 7.62 -7.62)\n'
            '\t\t\t\t\t(stroke\n\t\t\t\t\t\t(width 0.254)\n\t\t\t\t\t\t(type default)\n\t\t\t\t\t)\n\t\t\t\t\t(fill\n'
            '\t\t\t\t\t\t(type background)\n\t\t\t\t\t)\n\t\t\t\t)\n\t\t\t)' % short)
    pins = "\n".join(_s._pin(k, x, y, a, n, num, hide) for k, x, y, a, n, num, hide in PINS)
    return "\n".join([
        "\t\t(symbol %s" % name,
        "\t\t\t(pin_names\n\t\t\t\t(offset 1.016)\n\t\t\t)",
        "\t\t\t(exclude_from_sim no)\n\t\t\t(in_bom yes)\n\t\t\t(on_board yes)\n\t\t\t(in_pos_files yes)",
        "\t\t\t(duplicate_pin_numbers_are_jumpers no)",
        _s._prop("Reference", "U", -7.62, 8.89, False),
        _s._prop("Value", VALUE, -7.62, -11.43, False),
        _s._prop("Footprint", FOOTPRINT, 0, 0, True),
        _s._prop("Datasheet", DATASHEET, 0, 0, True),
        _s._prop("Description", DESCRIPTION, 0, 0, True),
        body,
        '\t\t\t(symbol "%s_1_1"\n%s\n\t\t\t)' % (short, pins),
        "\t\t\t(embedded_fonts no)",
        "\t\t)"])


def library_entry():
    txt = lib_symbol('"TPS7A4101"')
    return "\n".join(ln[1:] if ln.startswith("\t") else ln for ln in txt.split("\n"))
