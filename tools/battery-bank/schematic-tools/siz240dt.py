"""Vishay SiZ240DT (40 V dual N half-bridge, PowerPAIR 3 x 3S): one part per BQ25756 leg (2026-10-17).

Datasheet: datasheets/siz240dt.pdf (Vishay doc 77182; land pattern doc 78115, rev 06-Aug-2020).
Pins (top view): 1 G1, 2-4 D1, 5-7 S2, 8 G2, 9 = S1/D2 paddle (switch node); a D1 paddle beside it joins pins 2-4.
Ch1 = high side (control FET), Ch2 = low side (sync FET). RDS(on) max 8.05/8.41 mOhm at 10 V, 12.25/13.30 at 4.5 V,
Qg 6.9/6.5 nC at 4.5 V.

The symbol has two units with the PGQ04N070 symbol's pin geometry (G left at (-6.35, 1.27), drain right-top at
(6.35, 1.27), source right-bottom at (6.35, -1.27)), so unit A replaces a leg's high-side FET and unit B its low-side
FET in place, wires untouched. Both units carry pin 9 (S1/D2): A as its source, B as its drain; it is one pad on one
net (SW1 / SW2).
"""
import re
import uuid

LIB_ID = "MonolithDev:SiZ240DT"
FOOTPRINT = "MonolithDev:Vishay_PowerPAIR_3x3S"
LCSC, MPN = "C3289403", "SiZ240DT-T1-GE3 (Vishay)"
VALUE = "SiZ240DT"
# legs: (high-side ref -> unit A, low-side ref -> unit B), port 1 refs; port 2 is the same sheet
LEGS = [("Q401", "Q407"), ("Q402", "Q408")]
# check_netlist: new (ref, pin) -> old (ref, pin) on the same net, port 1 refs
PIN_REMAP = {}
for hs, ls in LEGS:
    PIN_REMAP.update({(hs, "1"): (hs, "4"), (hs, "2"): (hs, "5"), (hs, "3"): (hs, "5"), (hs, "4"): (hs, "5"),
                      (hs, "9"): (hs, "1"), (hs, "8"): (ls, "4"), (hs, "5"): (ls, "1"), (hs, "6"): (ls, "1"),
                      (hs, "7"): (ls, "1")})


def _pin(kind, x, y, ang, name, num, hide=False):
    h = "\n\t\t\t\t\t(hide yes)" if hide else ""
    return ('\t\t\t\t(pin %s line\n\t\t\t\t\t(at %g %g %d)\n\t\t\t\t\t(length 2.54)%s\n\t\t\t\t\t(name "%s"\n'
            '\t\t\t\t\t\t(effects\n\t\t\t\t\t\t\t(font\n\t\t\t\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t\t\t\t)\n\t\t\t\t\t\t)\n'
            '\t\t\t\t\t)\n\t\t\t\t\t(number "%s"\n\t\t\t\t\t\t(effects\n\t\t\t\t\t\t\t(font\n\t\t\t\t\t\t\t\t(size 1.27 1.27)\n'
            '\t\t\t\t\t\t\t)\n\t\t\t\t\t\t)\n\t\t\t\t\t)\n\t\t\t\t)' % (kind, x, y, ang, h, name, num))


def _prop(name, value, x, y, hide):
    h = "\n\t\t\t\t(hide yes)" if hide else ""
    return ('\t\t\t(property "%s" "%s"\n\t\t\t\t(at %g %g 0)%s\n\t\t\t\t(show_name no)\n\t\t\t\t(do_not_autoplace no)\n'
            '\t\t\t\t(effects\n\t\t\t\t\t(font\n\t\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t\t)\n\t\t\t\t)\n\t\t\t)'
            % (name, value, x, y, h))


def lib_symbol(name='"MonolithDev:SiZ240DT"', short="SiZ240DT"):
    """Symbol text at sheet lib_symbols depth (two tabs)."""
    body = ('\t\t\t(symbol "%s_0_1"\n\t\t\t\t(rectangle\n\t\t\t\t\t(start -3.81 3.81)\n\t\t\t\t\t(end 3.81 -3.81)\n'
            '\t\t\t\t\t(stroke\n\t\t\t\t\t\t(width 0.254)\n\t\t\t\t\t\t(type default)\n\t\t\t\t\t)\n\t\t\t\t\t(fill\n'
            '\t\t\t\t\t\t(type background)\n\t\t\t\t\t)\n\t\t\t\t)\n\t\t\t)' % short)
    u1 = "\n".join([_pin("input", -6.35, 1.27, 0, "G1", "1"),
                    _pin("passive", 6.35, 1.27, 180, "D1", "2"),
                    _pin("passive", 6.35, 1.27, 180, "D1", "3", True),
                    _pin("passive", 6.35, 1.27, 180, "D1", "4", True),
                    _pin("passive", 6.35, -1.27, 180, "SW", "9")])
    u2 = "\n".join([_pin("input", -6.35, 1.27, 0, "G2", "8"),
                    _pin("passive", 6.35, 1.27, 180, "SW", "9"),
                    _pin("passive", 6.35, -1.27, 180, "S2", "5"),
                    _pin("passive", 6.35, -1.27, 180, "S2", "6", True),
                    _pin("passive", 6.35, -1.27, 180, "S2", "7", True)])
    return "\n".join([
        "\t\t(symbol %s" % name,
        "\t\t\t(pin_names\n\t\t\t\t(offset 1.016)\n\t\t\t)",
        "\t\t\t(exclude_from_sim no)\n\t\t\t(in_bom yes)\n\t\t\t(on_board yes)\n\t\t\t(in_pos_files yes)",
        "\t\t\t(duplicate_pin_numbers_are_jumpers no)",
        _prop("Reference", "Q", -3.81, 5.08, False),
        _prop("Value", "SiZ240DT", -3.81, -5.08, False),
        _prop("Footprint", FOOTPRINT, 0, 0, True),
        _prop("Datasheet", "https://www.vishay.com/docs/77182/siz240dt.pdf", 0, 0, True),
        _prop("Description", "40 V dual N-MOSFET half-bridge, PowerPAIR 3x3S; unit A = Ch1 high side, unit B = Ch2 "
              "low side, pin 9 = S1/D2", 0, 0, True),
        body,
        '\t\t\t(symbol "%s_1_1"\n%s\n\t\t\t)' % (short, u1),
        '\t\t\t(symbol "%s_2_1"\n%s\n\t\t\t)' % (short, u2),
        "\t\t\t(embedded_fonts no)",
        "\t\t)"])


def library_entry():
    """The same symbol for MonolithDev.kicad_sym (one tab less, unprefixed name)."""
    txt = lib_symbol('"SiZ240DT"')
    return "\n".join(ln[1:] if ln.startswith("\t") else ln for ln in txt.split("\n"))


def footprint():
    """Vishay PowerPAIR 3 x 3S land pattern (doc 78115), centred on the package; top view, pin 1 top left."""
    pads = []
    ys = [-0.975, -0.325, 0.325, 0.975]
    for num, y in zip(("1", "2", "3", "4"), ys):                 # left row: 0.62 x 0.44, -1.95 .. -1.33
        pads.append('\t(pad "%s" smd rect (at -1.64 %g) (size 0.62 0.44) (layers "F.Cu" "F.Paste" "F.Mask"))' % (num, y))
    for num, y in zip(("8", "7", "6", "5"), ys):                 # right row: 0.59 x 0.44, 1.33 .. 1.92
        pads.append('\t(pad "%s" smd rect (at 1.625 %g) (size 0.59 0.44) (layers "F.Cu" "F.Paste" "F.Mask"))' % (num, y))
    # paddles 2.80 tall: D1 0.935 wide (-1.13 .. -0.195), S1/D2 1.005 wide (0.055 .. 1.06); 0.25 apart
    pads.append('\t(pad "2" smd rect (at -0.6625 0) (size 0.935 2.8) (layers "F.Cu" "F.Mask") (zone_connect 2))')
    pads.append('\t(pad "9" smd rect (at 0.5575 0) (size 1.005 2.8) (layers "F.Cu" "F.Mask") (zone_connect 2))')
    # paste on the paddles as 2 x 3 windows each (~65 % coverage) to limit voiding and float
    for cx, w in ((-0.6625, 0.935), (0.5575, 1.005)):
        for i in range(3):
            for j in range(2):
                pads.append('\t(pad "" smd rect (at %.4f %.3f) (size %.3f 0.72) (layers "F.Paste"))'
                            % (cx + (j - 0.5) * w / 2, (i - 1) * 0.93, w / 2 - 0.1))
    return "\n".join([
        '(footprint "Vishay_PowerPAIR_3x3S"', "\t(version 20241229)", '\t(generator "make_production.py")',
        '\t(layer "F.Cu")',
        '\t(descr "Vishay PowerPAIR 3x3S (SiZ240DT), 3.3x3.3 mm, recommended land pattern doc 78115 (06-Aug-2020)")',
        '\t(tags "PowerPAIR 3x3S SiZ240DT dual MOSFET half-bridge")',
        '\t(property "Reference" "REF**" (at 0 -2.6 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))',
        '\t(property "Value" "Vishay_PowerPAIR_3x3S" (at 0 2.6 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))',
        "\t(attr smd)"] + pads + [
        '\t(fp_rect (start -1.65 -1.65) (end 1.65 1.65) (stroke (width 0.1) (type solid)) (fill no) (layer "F.Fab"))',
        '\t(fp_line (start -1.65 -1.25) (end -1.25 -1.65) (stroke (width 0.1) (type solid)) (layer "F.Fab"))',
        '\t(fp_line (start -1.1 -1.78) (end 1.1 -1.78) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))',
        '\t(fp_line (start -1.1 1.78) (end 1.1 1.78) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))',
        '\t(fp_circle (center -2.2 -1.4) (end -2.1 -1.4) (stroke (width 0.2) (type solid)) (fill yes) (layer "F.SilkS"))',
        '\t(fp_rect (start -2.2 -1.9) (end 2.17 1.9) (stroke (width 0.05) (type solid)) (fill no) (layer "F.CrtYd"))',
        '\t(fp_text user "${REFERENCE}" (at 0 0 0) (layer "F.Fab") (effects (font (size 0.6 0.6) (thickness 0.1))))',
        ")", ""])


def _pins_block(nums):
    return "".join('\n\t\t(pin "%s"\n\t\t\t(uuid "%s")\n\t\t)' % (n, uuid.uuid4()) for n in nums)


def convert(blk, unit, ref):
    """Turn a placed PGQ04N070 symbol block into SiZ240DT unit `unit` (1 or 2) with reference `ref`."""
    blk = blk.replace('(lib_id "MonolithDev:PGQ04N070")', '(lib_id "%s")' % LIB_ID, 1)
    blk = re.sub(r"\n\t\t\(unit \d+\)", "\n\t\t(unit %d)" % unit, blk, count=1)
    blk = re.sub(r'(\(property "Reference" )"[^"]*"', r'\1"%s"' % ref, blk, count=1)
    for k, v in (("Value", VALUE), ("Footprint", FOOTPRINT), ("LCSC", LCSC), ("MPN", MPN)):
        blk = re.sub(r'(\(property "%s" )"[^"]*"' % k, lambda m: m.group(1) + '"%s"' % v, blk, count=1)
    a = blk.index('\n\t\t(pin "')
    b = blk.index("\n\t\t(instances")
    blk = blk[:a] + _pins_block(("1", "2", "3", "4", "9") if unit == 1 else ("8", "9", "5", "6", "7")) + blk[b:]

    def inst(m):  # port 1 path keeps 4xx, port 2 path 5xx
        port2 = m.group(1)[-3] == "5"
        r = ref if not port2 else ref[:-3] + "5" + ref[-2:]
        return '(reference "%s")\n\t\t\t\t\t(unit %d)' % (r, unit)
    return re.sub(r'\(reference "(Q\d+)"\)\n\t\t\t\t\t\(unit \d+\)', inst, blk)
