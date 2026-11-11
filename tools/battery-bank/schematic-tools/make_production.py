"""Build the production schematic from the dev board schematic (re-runnable).

Copies the DevBoard schematic sheets, symbol/footprint libraries and project file into Production/ as the
'Monolith' project, then strips everything the production board doesn't carry (decided 2026-10-17):

  * removes dev-only parts by reference and prunes the wires, labels, junctions, no-connects and power
    symbols left dangling;
  * replaces 0 ohm links and jumpers with a wire between their two pins;
  * cell holders -> plated slots for the welded pack's nickel tails (CELL1-3 and the 1N / 4P Kelvin wires on their own
    nets) and plated holes for the 18 AWG PACK+/- power wires (2026-10-24), NTC headers -> 2-pad wire footprints, EV2400 header -> three gauge pogo pads,
    SWD header J301 -> Tag-Connect TC2030-NL;
  * keeps a few dev test points as factory test pads (PACK_P, GND, 3V3, VBUS per port).

Run from the repo root or anywhere:  "C:/Program Files/KiCad/10.0/bin/python.exe" hardware/Production/tools/make_production.py
Then check:                          ... hardware/Production/tools/check_netlist.py
"""
import os
import re
import shutil
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from schlib import anchors, new_uuids, on_segment, sheet_pins, symbols, top_blocks, wires  # noqa: E402
import siz240dt  # noqa: E402
import tpd6s300  # noqa: E402
import tps7a4101  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PROD = os.path.normpath(os.path.join(HERE, ".."))
DEV = os.path.normpath(os.path.join(PROD, "..", "DevBoard"))
sys.path.insert(0, os.path.normpath(os.path.join(PROD, "..", "mechanical")))
import monolith_shell as MS  # noqa: E402  (slot sizes and peg holes: one source for the cup and the board)
KICAD_SYM = r"C:\Program Files\KiCad\10.0\share\kicad\symbols\Connector.kicad_sym"

SHEETS = ["gauge.kicad_sch", "power.kicad_sch", "mcu.kicad_sch", "usb_port.kicad_sch"]
ROOT_DEV, ROOT = "MonolithDev.kicad_sch", "Monolith.kicad_sch"

# ------------------------------------------------------------------ what goes
REMOVE = {
    "gauge.kicad_sch": [
        "BT101", "BT102", "BT103", "BT104",          # cell holders -> wire pads (added below)
        "J103",                                      # EV2400 header -> pogo pads (added below)
        "J104", "D104", "D105",                      # bench PACK_P supply
        "R127",                                      # DNP fuse bypass
        "R114",                                      # DNP BTP pull-up
        "SW101", "R118",                             # gauge wake button
        "C109", "D102",                              # DNP Q102 options
        "TP101", "TP102", "TP103", "TP104", "TP105", "TP107", "TP108",
    ],
    "power.kicad_sch": [
        "U201", "U202", "U203", "JP201", "JP202",    # sleep-current amps and their supply
        "R202", "R203", "R204", "R205", "R206", "R208",
        "C201", "C202", "C203", "C204", "C205",
        "TP201", "TP202", "TP203", "TP204", "TP205", "TP206", "TP207", "TP208", "TP209",
        "#FLG201",                                   # PACK_LP flag (net is PACK_P now)
    ],
    "mcu.kicad_sch": [
        "J301",                                      # 10-pin SWD -> TC2030-NL (added below)
        "J302", "R322", "R323",                      # UART header
        "J303", "R317", "R318", "R319", "R324",      # spare-GPIO header
        "SW301",                                     # reset button
        "D301", "R306", "R307",                      # status LED
        "R315",                                      # DNP pull-up
        "TP302", "TP303", "TP304", "TP307", "TP308", "TP309",
        "#FLG302",                                   # 3V3_MCU flag (net is 3V3 now)
    ],
    "usb_port.kicad_sch": [
        "J402",                                      # I2Cc logic-analyser header
        "C447",                                      # DNP feed-forward cap
        "C435",                                      # battery-side bank 3 -> 2 x 22u (cap sims 2026-10-17, B2)
        "Q403", "Q404", "Q405", "Q406",              # liquid detection removed (2026-10-17): SBU pull FETs
        "R436", "R437", "R438", "R439",              # ... SBU sense resistors
        "R442", "R443",                              # ... FET gate holds
        "R421", "R422", "R423",                      # STAT1/STAT2/PG pull-ups: nothing reads them (status via I2C)
        "U405",                                      # TPD4S201 -> TPD6S300 (CC used, SBU open), added by add_tpd6s300
        "C432",                                      # per-port hybrid -> shared PACK_P MLCCs C208-C213 (low_profile_sims N1)
        "C445",                                      # buck input 2 -> 1 x 10u 50V on the shared bus (pack_bus_sims A2)
        "D406", "D407", "D408", "D409",              # gate turn-off diodes: gates driven directly
        "#FLG404", "#FLG406",                        # 3V3_PD / 5V_IN flags (nets are 3V3 / PACK_P now)
    ] + ["TP4%02d" % n for n in range(2, 22) if n not in (2, 3, 4, 5, 6, 12)],  # P0 keeps PPHV/PP5V/REGN/SW1/SW2/GND probes
}
LINKS = {  # two-pin parts replaced by a wire
    ROOT: ["R1", "R2", "R3", "R4"],
    "power.kicad_sch": ["R201", "R207"],
    "mcu.kicad_sch": ["R301", "R312"],
    "usb_port.kicad_sch": ["R401", "R431", "R440", "R448", "R449"],  # R444-R447 back as 0R gate links on P0
}
# labels renamed after a link joins two named nets (old -> new), per sheet
RENAME = {  # labels on nets a link joined: new label name, ("pwr", net) to put that power symbol there instead,
    #          or "" to delete a label left on a single pin (the pin then gets a no-connect)
    ROOT: {"P1_ADCIN1": "P1_LDO_3V3", "P1_ADCIN2": ("pwr", "GND"), "P2_ADCIN1": ("pwr", "GND"),
           "P2_ADCIN2": ("pwr", "GND")},
    "power.kicad_sch": {"PACK_LP": ("pwr", "PACK_P"), "3V3_BUCK": ("pwr", "3V3"), "LDO_IN": ""},
    "mcu.kicad_sch": {"3V3_MCU": ("pwr", "3V3"), "SMB_PU": ("pwr", "3V3"),
                      "UART_TX": "", "UART_RX": "", "LED_DRV": ""},
    "usb_port.kicad_sch": {"DP": "DPDN_DCP", "DN": "DPDN_DCP", "BTST1_C": "BTST1", "BTST2_C": "BTST2",
                           "STAT1": "", "STAT2": "", "PG": "", "SBU1": "", "SBU2": "",
                           "3V3_PD": ("pwr", "3V3"), "5V_IN": ("pwr", "PACK_P")},
}
NEW_PARTS = {**{c: {"1": ("TP106", "1"), "2": ("TP109", "1")} for c in ("C208", "C209", "C210", "C211", "C212", "C213")},
             # 1N / 4P Kelvin slots (2026-10-21): new nets, with the pins in KELVIN
             "J115": {"1": "new CELL_1N"}, "J116": {"1": "new CELL_4P"},
             # low-profile USB-side bulk (2026-10-18): new per-port caps on AC_SNS_N
             **{c % p: {"1": ("C%s20" % p, "1"), "2": ("TP109", "1")} for c in ("C%s56",) for p in "45"},
             # P0 training parts (2026-10-18); a string value names a net that is new on production
             "J113": {"1": ("TP106", "1")}, "J114": {"1": ("TP109", "1")},
             "R118": {"1": ("F102", "2"), "2": "new WAKE"}, "TP113": {"1": "new WAKE"},
             "J302": {"1": ("J103", "3"), "2": ("R319", "1"), "3": ("J301", "10"), "4": "new J302.4",
                      "5": ("J103", "1"), "6": ("J103", "2")}}
for _p in ("4", "5"):  # TPD6S300 U405/U505 (tpd6s300.py): pin -> a dev pin on the net it joins (check_netlist)
    _u = "U%s05" % _p
    NEW_PARTS[_u] = {"4": ("J%s01" % _p, "A5"), "8": ("J%s01" % _p, "A5"), "5": ("J%s01" % _p, "B5"),
                     "6": ("J%s01" % _p, "B5"), "3": ("C%s51" % _p, "1"), "12": ("U%s01" % _p, "28"),
                     "11": ("U%s01" % _p, "29"), "9": ("U%s01" % _p, "19"), "10": ("U%s01" % _p, "1")}
    NEW_PARTS[_u].update({n: ("TP109", "1") for n, net in tpd6s300.PIN_NETS.items() if net == "GND"})
    NEW_PARTS[_u].update({n: "unconnected %s.%s" % (_u, n) for n, net in tpd6s300.PIN_NETS.items() if net == "NC"})
# labels left on single pins after liquid detection went: per label name, what happens at each pin's owner.
# TPS25751 GPIO4-7 unused -> GND (datasheet pin table); TPD4S201 system-side SBU pins -> no-connect (grounding them
# would short a cable's SBU lines whenever the SBU switch is on).
PIN_ACTIONS = {"usb_port.kicad_sch": {
    "SBU1_SNS": {"U401": "GND", "U405": "NC"}, "SBU2_SNS": {"U401": "GND", "U405": "NC"},
    "LIQ_PU": {"U401": "GND"}, "LIQ_PD": {"U401": "GND"}}}
# Kelvin split (2026-10-21; wires since 2026-10-24): each PACK pad carries a power wire (plated hole) and a Kelvin
# wire (slot), and these pins move from the power nets to the Kelvin nets (BQ40Z50 SLUSCS4C 9.2.2.1.3, SLUA660 2.3-2.4).
# CELL_1N: the gauge's low-current ground (VSS star, its strapped pins and decoupling), the BQ294700's VSS and the NTC
#   returns, joined to the pack only at the 1N tab. The shunt (RS101, SRP filter R107) and the fuse-heater FET Q104
#   (up to 1.5 A, with its gate resistor R125) stay on CELL_N with the PACK- power wire.
# CELL_4P: VC4, the BQ294700's V4 / VDD filters and the BAT diode (TI fig. 9-12: D1 on 4P). F102 stays on CELL_P_RAW.
KELVIN = {
    "CELL_1N": ["U101.9", "U101.33", "U101.16", "U101.17", "U101.23", "U101.24", "U102.6", "U102.9", "C104.2", "C105.2",
                "C115.2", "C116.2", "C117.1", "C118.2", "R117.2", "J102.2", "J105.2", "J106.2", "J107.2"],
    "CELL_4P": ["R104.1", "R119.1", "R123.2", "D101.2"],
}
KELVIN_FROM = {"CELL_1N": "CELL_N", "CELL_4P": "CELL_P_RAW"}   # the power net each one leaves
# gauge sheet, beside where J108 / J112 end up (outside layout_production's moves, which bring J108 to y 99.06)
KELVIN_AT = {"J115": ("CELL_1N", (55.88, 96.52)), "J116": ("CELL_4P", (55.88, 58.42))}
# check_netlist: pins that deliberately change net (port 1 refs; port 2 follows). "GND", None (left unconnected) or
# "new NAME" (a net that is new on production)
NET_MOVES = {("U401", "26"): "GND", ("U401", "27"): "GND", ("U401", "36"): "GND", ("U401", "37"): "new DRV9_OFF",
             ("J401", "A8"): None, ("J401", "B8"): None,
             **{tuple(rp.split(".")): "new " + net for net, rps in KELVIN.items() for rp in rps}}
TC2030_AT = (297.18, 106.68)  # under the SWD heading on the MCU sheet (was the DEBUG HEADERS area)
EXTRA_NC = {ROOT: [(220, 124.46)]}  # port 2's LDO_3V3 sheet pin: only port 1's strap used it
PAD = "TestPoint:TestPoint_Pad_D1.0mm"  # P0: small probe pads (2026-10-18)
FOOTPRINT = {  # kept parts whose footprint changes
    "gauge.kicad_sch": {"TP106": PAD, "TP109": PAD,
                        "J102": "Connector_Wire:SolderWire-0.15sqmm_1x02_P4mm_D0.5mm_OD1.5mm",
                        "J105": "Connector_Wire:SolderWire-0.15sqmm_1x02_P4mm_D0.5mm_OD1.5mm",
                        "J106": "Connector_Wire:SolderWire-0.15sqmm_1x02_P4mm_D0.5mm_OD1.5mm",
                        "J107": "Connector_Wire:SolderWire-0.15sqmm_1x02_P4mm_D0.5mm_OD1.5mm"},
    "mcu.kicad_sch": {"TP301": PAD},
    "usb_port.kicad_sch": {t: PAD for t in ("TP401", "TP402", "TP403", "TP404", "TP405", "TP406", "TP412")},
}
VALUE = {
    "gauge.kicad_sch": {"J102": "Cell 1 NTC wires", "J105": "Cell 2 NTC wires",
                        "J106": "Cell 3 NTC wires", "J107": "Cell 4 NTC wires"},
}
GMK_PROPS = {"Value": "22u 35V", "Footprint": "Capacitor_SMD:C_1210_3225Metric", "LCSC": "C778721",
             "MPN": "GMK325BJ226MM-P"}
SWAP = {  # parts changed in place: new lib_id and properties (pins land on the same points)
    "usb_port.kicad_sch": {
        "C443": ("Device:C", {
            "Value": "22u 25V", "Footprint": "Capacitor_SMD:C_1206_3216Metric", "LCSC": "C12891",
            "MPN": "CL31A226KAHNNNE",
            "Notes": "PP5V bulk, third 22 uF 1206 with C441/C442 (about 33 uF effective at 5.16 V; was a 100 uF polymer "
                     "on the dev board). Each port's PP5V is a dedicated supply, so USB PD cSrcBulk (10 uF min) applies, "
                     "not cSrcBulkShared (120 uF): docs/devboard/cap-reduction-sims-2026-10-17.md, P3"}),
        # low-profile bulk (2026-10-18): nothing taller than the inductors (3.1 mm), low_profile_sims.py C2 / N1
        "C421": (None, {
            "Value": "68u 35V", "Footprint": "Capacitor_Tantalum_SMD:CP_EIA-7343-31_Kemet-D", "LCSC": "",
            "Datasheet": "https://yageogroup.com/download/specsheet/T593V686M035APE070", "MPN": "KEMET T593V686M035APE070 (polymer tantalum)",
            "Notes": "USB-side bulk with C456 (two KEMET T593V 68 uF 35 V polymer tantalum, 70 mOhm, 1.69 A rms at 85 C, 7343-20, 2.0 mm max, on the 7343 D land pattern; was CCTC CA55 47 uF until 2026-10-31) and four 22u 35V 1210: 133 uF worst case at 20 V (BQ25756 >= 80 uF). Polymer, not MnO2: no ignition on failure, 20 % derating (20 V on 35 V). AC_SNS_N is dead in sleep, so the 0.1 CV leakage rating (238 uA) does not matter here: Production/tools/low_profile_sims.py option C4"}),
        **{c: (None, {**GMK_PROPS, "Notes": "Battery-side MLCC at the charger FETs, 22u 35V 1210 (about 10 uF at 16.8 V): "
                      "shared PACK_P bulk is C208-C213, Production/tools/low_profile_sims.py option N1"})
           for c in ("C431", "C434")},
        "C444": (None, dict(GMK_PROPS)),  # TPS62933 input: 22u 35V 1210 keeps ~10 uF at 16.8 V (the 10u 50V ~4 uF)
    },
}


def P(fp, lcsc, mpn, value=None):
    """Footprint/part swap that keeps the symbol (production passive downsizing, 2026-10-17)."""
    props = {"Footprint": fp, "LCSC": lcsc, "MPN": mpn}
    if value:
        props["Value"] = value
    return (None, props)


R413_NOTES = ("ICHG hardware ceiling 50/11.8 = 4.24 A per port (4.07-4.45 A over K_ICHG and 1 %), under the FEB 21700G "
              "cell's 4.55 A charge maximum (2026-10-21; was 9.1k for the EVE 58E). Firmware keeps the sum of both ports "
              "at 4.55 A max and follows the cell-temperature charge ramp (docs/firmware/charge-and-thermal-policy.md; "
              "TPS25751 config default ICHG_REG 2.8 A; MCU raises the only charging port). EN_CHG_BIT_RESET_BEHAVIOR = 0 "
              "so a watchdog expiry stops charging instead of falling back to this pin")
# sheet text changed in place: (old, new), each must occur once (the sheet notes are tidy_production.py's)
TEXT_EDITS = {"usb_port.kicad_sch": [("ICHG 5.5 A max, ILIM", "ICHG 4.4 A max (FEB cell), ILIM"),
                                     ("CONTROLLER  (600 kHz,", "CONTROLLER  (500 kHz,")]}
# Q101/Q102 BSC007N04LS6 land pattern: KiCad's PG-TDSON-8 (SuperSO8) with the four drain leads numbered 5-8 to match
# the AGM404AP1 symbol (KiCad numbers them all 5). Check it against the datasheet's footprint drawing before fab.
TDSON_FP = "Infineon_PG-TDSON-8_6.15x5.15mm_D5-8"
KICAD_TDSON = r"C:\Program Files\KiCad\10.0\share\kicad\footprints\Package_SON.pretty\Infineon_PG-TDSON-8_6.15x5.15mm.kicad_mod"
R0201, R0402, C0201, C0402 = ("Resistor_SMD:R_0201_0603Metric", "Resistor_SMD:R_0402_1005Metric",
                              "Capacitor_SMD:C_0201_0603Metric", "Capacitor_SMD:C_0402_1005Metric")
SOD882 = P("Diode_SMD:D_SOD-882", "C549279", "BAT54L,315 (Nexperia)")
DOWNSIZE = {  # extended parts and 0201 allowed on production; 0201 only where both nets stay <= 5.5 V
    "gauge.kicad_sch": {
        **{r: P(R0402, "C25076", "0402WGF1000TCE") for r in ("R101", "R102", "R103", "R104")},  # no open holders
        "R110": P(R0402, "C26086", "0402WGJ0106TCE", "10M 5%"),
        "R112": P(R0402, "C26086", "0402WGJ0106TCE", "10M 5%"),
        "R117": P(R0402, "C25790", "0402WGF4703TCE"),
        "R115": P(R0201, "C270366", "0201WMF1000TEE"),
        "R116": P(R0201, "C270366", "0201WMF1000TEE"),
        "RS101": P("Resistor_SMD:R_1206_3216Metric", "C154629", "LR1206-21R001F4 (Ralec, 75 ppm)", "1m 1% 1W"),
        "D101": SOD882,
        # loss cut 1 (2026-10-23, 65E short circuit): 0.70 mOhm 5 x 6 OptiMOS 6, spec/protection-fet-options.md
        **{q: (None, {"Value": "BSC007N04LS6", "Footprint": "MonolithDev:" + TDSON_FP, "LCSC": "C534274",
                      "MPN": "BSC007N04LS6ATMA1 (Infineon)", "Datasheet": "https://www.lcsc.com/datasheet/C534274.pdf",
                      "Description": "40 V 0.7 mOhm N-MOSFET, TDSON-8 FL 5x6"})
           for q in ("Q101", "Q102")},
        "U102": (None, {"Notes": "Independent of the gauge: 4.35 V/cell OVP (hysteresis 0.30 V), active-high OUT (~7 V) "
                                 "after the CD delay. RIN must be 1k (device calibrated with it). Exposed pad to VSS "
                                 "(CELL_1N, the Kelvin ground at the 1N tab)."}),
    },
    "mcu.kicad_sch": {
        **{c: P(C0201, "C307380", "CL03A104KO3NNNC", "0.1u 16V") for c in ("C302", "C303", "C304")},
        "R302": P(R0201, "C270364", "0201WMF1003TEE"),
        "R304": P(R0201, "C270350", "0201WMF3301TEE"),
        "R305": P(R0201, "C270350", "0201WMF3301TEE"),
        "R313": P(R0201, "C473458", "0201WMF2203TEE"),
        "R314": P(R0201, "C270345", "0201WMF4702TEE"),
    },
    "usb_port.kicad_sch": {
        "R402": P(R0201, "C270350", "0201WMF3301TEE"),
        "R403": P(R0201, "C270350", "0201WMF3301TEE"),
        "R404": P(R0201, "C473048", "0201WMF1002TEE"),
        "R410": P(R0402, "C25893", "0402WGF4022TCE"),
        # loss cut 3 (2026-10-23): 598 -> ~500 kHz with the XGL7030-332 (bq25756.pdf eq. 3). LCSC code still to look up
        "R412": (None, {**P(R0201, "", "0201WMF4992TEE", "49.9k 1%")[1],
                        "Notes": "FSW ~500 kHz (loss cut 3, with L401 XGL7030-332); the oscillator is +/-15 %, so 1 % is plenty"}),
        "R413": (None, {**P(R0402, "C93752", "0402WGF1182TCE", "11.8k 1%")[1], "Notes": R413_NOTES}),  # was 9.1k C25926
        "R414": P(R0402, "C25891", "0402WGF3601TCE"),
        "R415": P(R0402, "C25871", "0402WGF1801TCE"),
        "R416": P(R0402, "C25908", "0402WGF5601TCE"),
        "R417": P(R0201, "C270345", "0201WMF4702TEE"),
        # P0 hedges (no dev board, 2026-10-18): gate links fitted at 0R, snubbers DNP; tune on P0 without a respin
        **{r: P(R0402, "C17168", "0402WGF0000TCE", "0R") for r in ("R444", "R445", "R446", "R447")},
        "R450": P(R0402, "C270612", "0402WGF330KTCE", "3R3"),
        "R451": P(R0402, "C270612", "0402WGF330KTCE", "3R3"),
        "C454": P(C0402, "C1562", "0402CG330J500NT", "33p C0G"),
        "C455": P(C0402, "C1562", "0402CG330J500NT", "33p C0G"),
        "R424": P("Resistor_SMD:R_0805_2012Metric", "C728267", "PA0805FRE470R005L", "5m 0.5W (RAC)"),
        "R427": P("Resistor_SMD:R_1206_3216Metric", "C252653", "MA120610FR005MZ (50 ppm)", "5m 1W (RBAT)"),
        "R432": P(R0201, "C270364", "0201WMF1003TEE"),
        "R433": P(R0402, "C25750", "0402WGF1203TCE"),
        "R435": P(R0201, "C270365", "0201WMF1001TEE"),
        **{r: P(R0201, "C270364", "0201WMF1003TEE") for r in ("R441", "R442", "R443")},
        "C408": P(C0201, "C307380", "CL03A104KO3NNNC", "0.1u 16V"),
        "C410": P(C0402, "C23733", "CL05A475MP5NRNC", "4.7u 10V"),
        "C411": P("Capacitor_SMD:C_0805_2012Metric", "C1779", "CL21A475KAQNNNE", "4.7u 25V"),  # DRV_SUP up to ~9.6 V
        "C414": P(C0402, "C92361", "CL05A474KA5NNNC"),
        "C417": P(C0402, "C92361", "CL05A474KA5NNNC"),
        "C439": P(C0402, "C7419416", "FCC0402B333K500AT"),
        "TH401": P(R0402, "C77131", "NCP15XH103F03RC"),
        # 1.6 mm board (2026-10-18, for cost; 0.8 mm before): the 1.6 mm version of the IP68 connector, same land pattern
        "J401": P("MonolithDev:USB_C_Receptacle_ShouHan_TYPE-C_16PCB1.6_IP68", "C55629729",
                  "TYPE-C 16PCB1.6 IP68 (Shou Han)", "TYPE-C 16PCB1.6 IP68"),
        # 10x10 -> 7.8x7.6x3.1 mm: 13.7 mOhm max, Irms 13 A (40 C rise), Isat 17 A at a 40 % drop. Worst case (20 V 5 A
        # reverse from a 10 V pack) ~10.7 A rms, ~12.4 A peak: ~1.6 W DCR loss, L near 1.7 uH at the peak (L/RSNS
        # 0.34 uH/mOhm, inside TI's 0.05-1.26 stability range). Measure inductor temperature on the dev board.
        # Loss cut 3 (2026-10-23): Coilcraft XGL7030-332MEC on the APS0730 pads (they cover its terminals; same 3.1 mm
        # height). Stays >= 2.2 uH (the BQ25756 minimum) to 13 A; the APS0730 sags to ~1.7 uH. Not stocked at JLC:
        # consigned like the SiZ240DT.
        "L401": (None, {**P("MonolithDev:L_Coilank_APS0730", "", "XGL7030-332MEC (Coilcraft)", "3.3u")[1],
                        "Notes": "Coilcraft XGL7030-332MEC, 3.3 uH, 10.4/12.5 mOhm typ/max, >= 2.2 uH at 13 A; with R412 "
                                 "49.9k (~500 kHz). Consigned (not at JLC). Fits the APS0730 land pattern. Loss cut 3, "
                                 "docs/spec.md"}),
    },
}
for _sheet, _parts in DOWNSIZE.items():
    SWAP.setdefault(_sheet, {}).update(_parts)
SLOT_W, SLOT_RING = MS.SB_SLOT_W, MS.SB_SLOT_RING   # sense pad: the old plated slot's width and ring (mechanical/monolith_shell.py)
SENSE_D = MS.SB_SWIRE_HOLE                           # sense wires (2026-10-24): 28 AWG PTFE wire in a round hole, 1.5 x 1.4 pad


def slot_name(length):
    return "SolderWire-28AWG_PTFE_1x01_D%gmm_Pad%gx%gmm" % (SENSE_D, round(length, 2) + 2 * SLOT_RING, SLOT_W + 2 * SLOT_RING)


SLOTS = {n: "MonolithDev:" + slot_name(v[2]) for n, v in MS.sb_slots().items()}   # sense lead name -> footprint
# PACK- / PACK+ power leads (option C wire tails, 2026-10-24): an 18 AWG thin-wall PTFE wire into a plated hole
WIRE_D, WIRE_RING, WIRE_OD = MS.SB_PWIRE_HOLE, MS.SB_PWIRE_RING, MS.SB_PWIRE_OD
WIRE_FP = "SolderWire-18AWG_PTFE_1x01_D%gmm_OD%gmm" % (WIRE_D, WIRE_D + 2 * WIRE_RING)
# new one-pin pads on the gauge sheet: (ref, value, footprint, (old ref, old pin) whose position it takes)
GAUGE_PADS = [
    ("J108", "PACK- power wire", "MonolithDev:" + WIRE_FP, ("BT101", "2")),
    ("J109", "CELL1 sense wire", SLOTS["CELL1"], ("BT101", "1")),
    ("J110", "CELL2 sense wire", SLOTS["CELL2"], ("BT102", "1")),
    ("J111", "CELL3 sense wire", SLOTS["CELL3"], ("BT103", "1")),
    ("J112", "PACK+ power wire", "MonolithDev:" + WIRE_FP, ("BT104", "1")),
]
SLOT_REFS = {"CELL1": "J109", "CELL2": "J110", "CELL3": "J111", "1N": "J115", "4P": "J116"}   # make_board.py --mech
WIRE_REFS = {"PACK-": "J108", "PACK+": "J112"}   # places these at sb_slots() and sb_pack_holes()
NTC_REFS = {"C1": "TH101", "C4": "TH104"}     # and the front-cell SMD NTCs at sb_ntc_smd(), on B.Cu, 90 deg
# the pogo pads get their own spaced row (J103's pins were 2.54 mm apart), tied by a global label or GND symbol
POGO_AT = {}  # P0: gauge SMBus moved to the GAUGE Tag-Connect J302 on the MCU sheet (2026-10-18)


def uid():
    return str(uuid.uuid4())


def cut(s, spans):
    for a, b in sorted(set(spans), reverse=True):
        ls = s.rfind("\n", 0, a)
        s = s[:ls] + s[b:]
    return s


def insert_top(s, text):
    """Insert depth-1 items before the sheet's closing block (sheet_instances / embedded_fonts / end)."""
    for tail in ("\n\t(sheet_instances", "\n\t(embedded_fonts"):
        i = s.find(tail)
        if i >= 0:
            return s[:i] + text + s[i:]
    i = s.rstrip().rfind(")")
    return s[:i] + text.lstrip("\n") + "\n" + s[i:]


def wire_text(p, q):
    return ('\n\t(wire\n\t\t(pts\n\t\t\t(xy %g %g) (xy %g %g)\n\t\t)\n\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n'
            '\t\t)\n\t\t(uuid "%s")\n\t)' % (p[0], p[1], q[0], q[1], uid()))


def label_text(name, p, angle=0):
    just = "left bottom" if angle == 0 else "right bottom"
    return ('\n\t(label "%s"\n\t\t(at %g %g %d)\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n'
            '\t\t\t(justify %s)\n\t\t)\n\t\t(uuid "%s")\n\t)' % (name, p[0], p[1], angle, just, uid()))


def nc_text(p):
    return '\n\t(no_connect\n\t\t(at %g %g)\n\t\t(uuid "%s")\n\t)' % (p[0], p[1], uid())


def set_prop(blk, prop, value):
    return re.sub(r'(\(property "%s" )"[^"]*"' % prop, lambda m: m.group(1) + '"%s"' % value, blk, count=1)


def clone(template, ref, value, footprint, at, old_ref):
    """Copy a placed symbol block to a new position/reference."""
    blk = new_uuids(template)
    x0, y0 = map(float, re.search(r"\n\t\t\(at ([-\d.]+) ([-\d.]+)", blk).groups())
    dx, dy = at[0] - x0, at[1] - y0

    def shift(m):
        return "(at %g %g" % (round(float(m.group(1)) + dx, 2), round(float(m.group(2)) + dy, 2))
    blk = re.sub(r"\(at ([-\d.]+) ([-\d.]+)", shift, blk)
    blk = set_prop(blk, "Reference", ref)
    blk = set_prop(blk, "Value", value)
    blk = set_prop(blk, "Footprint", footprint)
    return blk.replace('(reference "%s")' % old_ref, '(reference "%s")' % ref)


def connection_state(s):
    syms = symbols(s)
    ws = wires(s)
    ends = {}
    for w in ws:
        for p in w["p"]:
            ends[p] = ends.get(p, 0) + 1
    labels = []
    for h in ("label", "global_label", "hierarchical_label"):
        labels += anchors(s, h)
    pins = {}
    for y in syms:
        for n, p in y["pins"].items():
            pins.setdefault(p, []).append(y)
    return syms, ws, ends, labels, pins


def split_wires(s):
    """Split wires at interior labels, T-joins and pins, so pruning a dangling end keeps what hangs mid-wire."""
    syms, ws, ends, labels, pins = connection_state(s)
    pts = set(ends) | {x["p"] for x in labels} | set(pins) | {x["p"] for x in anchors(s, "junction")}
    spans, add = [], ""
    for w in ws:
        mid = [p for p in pts if on_segment(p, w["p"])]
        if not mid:
            continue
        a = w["p"][0]
        mid.sort(key=lambda p: abs(p[0] - a[0]) + abs(p[1] - a[1]))
        chain = [a] + mid + [w["p"][1]]
        spans.append((w["a"], w["b"]))
        add += "".join(wire_text(p, q) for p, q in zip(chain, chain[1:]))
    return insert_top(cut(s, spans), add), len(spans)


def prune(s):
    """Remove wires/labels/junctions/no-connects/power symbols that no longer connect anything. Repeat to a fixpoint."""
    total = 0
    while True:
        syms, ws, ends, labels, pins = connection_state(s)
        sheet_pts = set(sheet_pins(s))
        lab_pts = {x["p"] for x in labels} | sheet_pts
        spans = []

        def through(p, skip=None):
            return any(on_segment(p, w["p"]) for w in ws if w is not skip)
        for w in ws:
            for p in w["p"]:
                if ends[p] > 1 or p in lab_pts or p in pins or through(p, w):
                    continue
                spans.append((w["a"], w["b"]))
                break
        for x in labels:
            p = x["p"]
            if p not in ends and p not in pins and p not in sheet_pts and not through(p):
                spans.append((x["a"], x["b"]))
        for y in syms:
            if not y["power"]:
                continue
            p = list(y["pins"].values())[0]
            if p not in ends and len(pins[p]) == 1 and p not in lab_pts and not through(p):
                spans.append((y["a"], y["b"]))
        for x in anchors(s, "junction"):
            p = x["p"]
            deg = ends.get(p, 0) + len(pins.get(p, [])) + 2 * sum(on_segment(p, w["p"]) for w in ws)
            if deg < 3:
                spans.append((x["a"], x["b"]))
        for x in anchors(s, "no_connect"):
            if x["p"] not in pins and x["p"] not in sheet_pts:
                spans.append((x["a"], x["b"]))
        if not spans:
            return s, total
        total += len(set(spans))
        s = cut(s, spans)


def attached(s):
    """Set of (ref, pin) attached to something."""
    syms, ws, ends, labels, pins = connection_state(s)
    lab_pts = {x["p"] for x in labels} | set(sheet_pins(s)) | {x["p"] for x in anchors(s, "no_connect")}
    out = set()
    for y in syms:
        for n, p in y["pins"].items():
            if p in ends or p in lab_pts or len(pins[p]) > 1 or any(on_segment(p, w["p"]) for w in ws):
                out.add((y["ref"], n))
    return out


def edit_symbols(s, sheet):
    out, last = [], 0
    for y in symbols(s):
        blk = s[y["a"]:y["b"]]
        if y["ref"] in FOOTPRINT.get(sheet, {}):
            blk = set_prop(blk, "Footprint", FOOTPRINT[sheet][y["ref"]])
        if y["ref"] in VALUE.get(sheet, {}):
            blk = set_prop(blk, "Value", VALUE[sheet][y["ref"]])
        if y["ref"] in SWAP.get(sheet, {}):
            lib, props = SWAP[sheet][y["ref"]]
            if lib:
                blk = re.sub(r'\(lib_id "[^"]+"\)', '(lib_id "%s")' % lib, blk, count=1)
            for k, v in props.items():
                assert '(property "%s" ' % k in blk, (y["ref"], k)
                blk = set_prop(blk, k, v)
        out += [s[last:y["a"]], blk]
        last = y["b"]
    out.append(s[last:])
    return "".join(out)


PWR_N = [9000]


def clone_power(src, at):
    """Copy a power symbol block to `at` (rotation 0) with fresh hidden #PWR references."""
    b = new_uuids(src)
    x0, y0 = map(float, re.search(r"\n\t\t\(at ([-\d.]+) ([-\d.]+)", b).groups())
    b = re.sub(r"\(at ([-\d.]+) ([-\d.]+)",
               lambda m: "(at %g %g" % (round(float(m.group(1)) - x0 + at[0], 2), round(float(m.group(2)) - y0 + at[1], 2)), b)
    b = re.sub(r"\n\t\t\(at ([-\d.]+) ([-\d.]+) [-\d.]+\)", lambda m: "\n\t\t(at %s %s 0)" % m.groups(), b, count=1)

    def fresh(m):
        PWR_N[0] += 1
        return '%s"#PWR%04d"' % (m.group(1), PWR_N[0])
    return "\n\t" + re.sub(r'(\(property "Reference" |\(reference )"#PWR[^"]*"', fresh, b)


def power_template(s, value):
    for y in symbols(s):
        if y["power"] and '(property "Value" "%s"' % value in s[y["a"]:y["b"]]:
            return s[y["a"]:y["b"]]
    raise KeyError(value)


def add_tpd6s300(s, old, templates):
    """Place the TPD6S300 where U405 (TPD4S201) was and tie each pin to its net: label, GND symbol or no-connect."""
    if '(symbol "%s"' % tpd6s300.LIB_ID not in s:
        i = s.index("\n\t(lib_symbols") + len("\n\t(lib_symbols")
        s = s[:i] + "\n" + tpd6s300.lib_symbol() + s[i:]
    c451 = next(y for y in symbols(s) if y["ref"] == "C451")  # a 4xx part: both ports' instance paths
    tmpl = s[c451["a"]:c451["b"]]
    blk = new_uuids(tmpl)
    x0, y0 = map(float, re.search(r"\n\t\t\(at ([-\d.]+) ([-\d.]+)", blk).groups())
    at = old["U405"]["at"][:2]
    blk = re.sub(r"\(at ([-\d.]+) ([-\d.]+)", lambda m: "(at %g %g" % (
        round(float(m.group(1)) - x0 + at[0], 2), round(float(m.group(2)) - y0 + at[1], 2)), blk)
    blk = re.sub(r"\n\t\t\(at ([-\d.]+) ([-\d.]+) [-\d.]+\)", lambda m: "\n\t\t(at %s %s 0)" % m.groups(), blk, count=1)
    blk = re.sub(r"\n\t\t\(mirror \w\)", "", blk)
    blk = re.sub(r'\(lib_id "[^"]+"\)', '(lib_id "%s")' % tpd6s300.LIB_ID, blk, count=1)
    blk = re.sub(r"\n\t\t\(unit \d+\)", "\n\t\t(unit 1)", blk, count=1)
    for k, v in (("Reference", "U405"), ("Value", tpd6s300.VALUE), ("Footprint", tpd6s300.FOOTPRINT)):
        blk = set_prop(blk, k, v)
    for k, dx, dy in (("Reference", -13.97, 19.05), ("Value", -13.97, 21.59)):  # below-left of the body (free area)
        blk = re.sub(r'(\(property "%s" "[^"]*"\s*\(at )[-\d.]+ [-\d.]+ [-\d.]+\)' % k,
                     lambda m: m.group(1) + "%g %g 0)" % (round(at[0] + dx, 2), round(at[1] + dy, 2)), blk, count=1)
    for k, v in (("LCSC", tpd6s300.LCSC), ("MPN", tpd6s300.MPN), ("Datasheet", tpd6s300.DATASHEET),
                 ("Description", tpd6s300.DESCRIPTION)):
        if '(property "%s" ' % k in blk:
            blk = set_prop(blk, k, v)
    for k in ("Notes", "Sourcing"):
        if '(property "%s" ' % k in blk:
            blk = set_prop(blk, k, "")
    a = blk.index('\n\t\t(pin "')
    b = blk.index("\n\t\t(instances")
    blk = blk[:a] + "".join('\n\t\t(pin "%s"\n\t\t\t(uuid "%s")\n\t\t)' % (p, uid()) for p in tpd6s300.PIN_NETS) + blk[b:]

    def inst(m):
        port2 = m.group(1)[-3] == "5" if len(m.group(1)) >= 3 and m.group(1)[-3].isdigit() else False
        return '(reference "%s")\n%s(unit 1)' % ("U505" if port2 else "U405", m.group(2))
    blk = re.sub(r'\(reference "([^"]+)"\)\n(\t+)\(unit \d+\)', inst, blk)
    s = insert_top(s, "\n\t" + blk)
    pins = {y["ref"]: y for y in symbols(s)}["U405"]["pins"]
    add, grounded = "", set()
    for num, net in tpd6s300.PIN_NETS.items():
        p = pins[num]
        if net == "GND":
            if tuple(p[:2]) not in grounded:  # stacked GND pins share one symbol
                grounded.add(tuple(p[:2]))
                add += clone_power(templates["GND"], p)
        elif net == "NC":
            add += nc_text(p)
        else:
            add += label_text(net, p, 180 if p[0] < at[0] else 0)
    return insert_top(s, add)


def swap_fets(s):
    """Each BQ25756 leg's two PGQ04N070 -> one SiZ240DT: high side becomes unit A, low side unit B (siz240dt.py)."""
    if '(symbol "%s"' % siz240dt.LIB_ID not in s:
        i = s.index("\n\t(lib_symbols") + len("\n\t(lib_symbols")
        s = s[:i] + "\n" + siz240dt.lib_symbol() + s[i:]
    syms = {y["ref"]: y for y in symbols(s)}
    reps = []
    for hs, ls in siz240dt.LEGS:
        for ref, unit in ((hs, 1), (ls, 2)):
            y = syms[ref]
            reps.append((y["a"], y["b"], siz240dt.convert(s[y["a"]:y["b"]], unit, hs)))
    for a, b, txt in sorted(reps, reverse=True):
        s = s[:a] + txt + s[b:]
    return s


def pin_actions(s, sheet, templates):
    """Apply PIN_ACTIONS to labels sitting directly on a pin: GND symbol in their place, or a no-connect flag."""
    acts = PIN_ACTIONS.get(sheet, {})
    if not acts:
        return s
    owner = {}
    for y in symbols(s):
        for p in y["pins"].values():
            owner.setdefault(p, y["ref"])
    spans, add, to_gnd = [], "", []
    for x in anchors(s, "label"):
        if x["name"] not in acts:
            continue
        what = acts[x["name"]].get(owner.get(x["p"]))
        assert what, (x["name"], x["p"], owner.get(x["p"]))
        spans.append((x["a"], x["b"]))
        if what == "GND":
            to_gnd.append(x["p"])
        else:
            add += nc_text(x["p"])
    if to_gnd:  # U401 GPIO4-7 sit in the rows above GPIO11, whose wire already runs left to GND: join that wire
        g11 = {y["ref"]: y for y in symbols(s)}["U401"]["pins"]["13"]
        corner = next(q for w in wires(s) if g11 in w["p"] for q in w["p"] if q != g11)
        assert corner[1] == g11[1] and all(p[0] == g11[0] for p in to_gnd), (corner, g11, to_gnd)
        for p in to_gnd:
            add += wire_text(p, (corner[0], p[1]))
        rail = sorted({(corner[0], p[1]) for p in to_gnd} | {corner}, key=lambda q: q[1])
        for a, b in zip(rail, rail[1:]):  # end-to-end segments, so every stub meets a wire end (no mid-wire T)
            add += wire_text(a, b)
        add += "".join('\n\t(junction\n\t\t(at %g %g)\n\t\t(diameter 0)\n\t\t(color 0 0 0 0)\n\t\t(uuid "%s")\n\t)'
                       % (q[0], q[1], uid()) for q in rail[1:])
    return insert_top(cut(s, spans), add)


def rename_labels(s, sheet, templates):
    spans, adds = [], ""
    for x in anchors(s, "label"):
        if x["name"] in RENAME.get(sheet, {}):
            new = RENAME[sheet][x["name"]]
            spans.append((x["a"], x["b"]))
            if isinstance(new, tuple) and x["p"] in set(sheet_pins(s)):
                # sheet pins sit off the 1.27 mm grid: step out to the grid with a short wire
                q = (round(round((x["p"][0] + 2.54) / 1.27) * 1.27, 2), x["p"][1])
                adds += wire_text(x["p"], q) + clone_power(templates[new[1]], q)
            elif isinstance(new, tuple):
                adds += clone_power(templates[new[1]], x["p"])
            elif new:
                adds += "\n\t" + s[x["a"]:x["b"]].replace('(label "%s"' % x["name"], '(label "%s"' % new, 1)
    s = cut(s, spans)
    return insert_top(s, adds) if adds else s


def add_tc2030(s, old):
    """J301 (10-pin Cortex SWD) -> J301 Tag-Connect TC2030-NL, wired by labels and power symbols."""
    lib = open(KICAD_SYM, encoding="utf-8").read()
    m = re.search(r'\n\t\(symbol "Conn_ARM_SWD_TagConnect_TC2030"\n', lib)
    a = m.start() + 2
    from schlib import block_end
    sym = lib[a:block_end(lib, a)]
    sym = sym.replace('(symbol "Conn_ARM_SWD_TagConnect_TC2030"', '(symbol "Connector:Conn_ARM_SWD_TagConnect_TC2030"', 1)
    sym = "\n".join("\t" + ln for ln in sym.split("\n"))
    i = s.index("\n\t(lib_symbols") + len("\n\t(lib_symbols")
    s = s[:i] + "\n\t" + sym + s[i:]

    syms = {y["ref"]: y for y in symbols(s)}
    tmpl = s[syms["TP301"]["a"]:syms["TP301"]["b"]]          # any symbol on this sheet for the instance path
    blk = clone(tmpl, "J301", "TC2030-NL", "Connector:Tag-Connect_TC2030-IDC-NL_2x03_P1.27mm_Vertical", TC2030_AT, "TP301")
    blk = blk.replace('(lib_id "Connector:TestPoint")', '(lib_id "Connector:Conn_ARM_SWD_TagConnect_TC2030")')
    blk = set_prop(blk, "Description", "Tag-Connect TC2030-NL footprint (no part fitted); XDS110 via TC2030-CTX cable")
    blk = re.sub(r'\n\t\t\(pin "1"\n\t\t\t\(uuid "[^"]+"\)\n\t\t\)',
                 "".join('\n\t\t(pin "%d"\n\t\t\t(uuid "%s")\n\t\t)' % (n, uid()) for n in range(1, 7)), blk)
    s = insert_top(s, "\n\t" + blk)

    pins = {y["ref"]: y for y in symbols(s)}["J301"]["pins"]
    gnd = pins["5"]
    v33 = pins["1"]
    add = clone_power(power_template(s, "3V3"), v33) + clone_power(power_template(s, "GND"), gnd)
    add += label_text("SWDIO", pins["2"]) + label_text("NRST", pins["3"]) + label_text("SWCLK", pins["4"])
    add += nc_text(pins["6"])
    u = {y["ref"]: y for y in symbols(s)}["U301"]["pins"]
    add += label_text("SWDIO", u["20"], 180) + label_text("SWCLK", u["19"], 180)
    return insert_top(s, add)


LOAD_PAD = "Connector_Wire:SolderWire-0.5sqmm_1x01_D0.9mm_OD2.1mm"  # 20 AWG: learning-cycle load / bench wires
GAUGE_TC = ["SDA", "CHG_INH", "NRST", None, "GND", "SCL"]  # J302 pins 1-6 (None = no-connect)
GAUGE_TC_AT = (297.18, 137.16)                             # under J301 on the MCU sheet


def _rot(blk, angle):
    """Set a placed symbol block's own rotation (its first (at x y r) line)."""
    return re.sub(r"\n\t\t\(at ([-\d.]+) ([-\d.]+) [-\d.]+\)",
                  lambda m: "\n\t\t(at %s %s %d)" % (m.group(1), m.group(2), angle), blk, count=1)


def _fields(blk, at, ref_xy, val_xy):
    """Put Reference/Value at offsets from the symbol position, unrotated."""
    for k, (dx, dy) in (("Reference", ref_xy), ("Value", val_xy)):
        blk = re.sub(r'(\(property "%s" "[^"]*"\s*\(at )[-\d.]+ [-\d.]+ [-\d.]+\)' % k,
                     lambda m: m.group(1) + "%g %g 0)" % (round(at[0] + dx, 2), round(at[1] + dy, 2)), blk, count=1)
    return blk


def _text(txt, at, size=1.27):
    return ('\n\t(text "%s"\n\t\t(exclude_from_sim no)\n\t\t(at %g %g 0)\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size %g %g)\n'
            '\t\t\t)\n\t\t\t(justify left bottom)\n\t\t)\n\t\t(uuid "%s")\n\t)' % (txt, at[0], at[1], size, size, uid()))


def _glabel(s, name, p, angle):
    """Copy of an existing global label `name`, moved to p and pointing left (180) or right (0)."""
    a, b = next((a, b) for a, b in top_blocks(s, "global_label") if s[a:b].startswith('(global_label "%s"' % name))
    blk = new_uuids(s[a:b])
    x0, y0 = map(float, re.search(r"\(at ([-\d.]+) ([-\d.]+)", blk).groups())
    blk = re.sub(r"\(at ([-\d.]+) ([-\d.]+)", lambda m: "(at %g %g" % (
        round(float(m.group(1)) - x0 + p[0], 2), round(float(m.group(2)) - y0 + p[1], 2)), blk)
    blk = re.sub(r"\(at ([-\d.]+) ([-\d.]+) \d+\)", lambda m: "(at %s %s %d)" % (m.group(1), m.group(2), angle), blk, count=1)
    blk = re.sub(r"\(justify (left|right)", "(justify %s" % ("right" if angle == 180 else "left"), blk, count=1)
    return "\n\t" + blk


def add_gauge_tc2030(s):
    """J302 = second Tag-Connect TC2030-NL footprint for gauge training / golden-image loading (2026-10-18).
    Pinout chosen so the SWD cable plugged here by mistake drives nothing harmful (see GAUGE_TC and the README)."""
    import siz240dt as _s
    if '(symbol "MonolithDev:TC2030_GAUGE"' not in s:
        pins = "\n".join(_s._pin("passive", -5.08, 12.7 - 5.08 * i, 0, n or "NC", str(i + 1)) for i, n in enumerate(GAUGE_TC))
        body = ('\t\t\t(symbol "TC2030_GAUGE_0_1"\n\t\t\t\t(rectangle\n\t\t\t\t\t(start -2.54 15.24)\n\t\t\t\t\t(end 5.08 -15.24)\n'
                '\t\t\t\t\t(stroke\n\t\t\t\t\t\t(width 0.254)\n\t\t\t\t\t\t(type default)\n\t\t\t\t\t)\n\t\t\t\t\t(fill\n'
                '\t\t\t\t\t\t(type background)\n\t\t\t\t\t)\n\t\t\t\t)\n\t\t\t)')
        lib = "\n".join(["\t\t(symbol \"MonolithDev:TC2030_GAUGE\"", "\t\t\t(pin_names\n\t\t\t\t(offset 0.508)\n\t\t\t)",
                         "\t\t\t(exclude_from_sim no)\n\t\t\t(in_bom no)\n\t\t\t(on_board yes)\n\t\t\t(in_pos_files no)",
                         "\t\t\t(duplicate_pin_numbers_are_jumpers no)",
                         _s._prop("Reference", "J", 0, 8.89, False), _s._prop("Value", "TC2030-NL GAUGE", 0, -8.89, False),
                         _s._prop("Footprint", "Connector:Tag-Connect_TC2030-IDC-NL_2x03_P1.27mm_Vertical", 0, 0, True),
                         _s._prop("Datasheet", "", 0, 0, True),
                         _s._prop("Description", "Tag-Connect TC2030-NL pads for gauge SMBus + training signals", 0, 0, True),
                         body, '\t\t\t(symbol "TC2030_GAUGE_1_1"\n%s\n\t\t\t)' % pins, "\t\t\t(embedded_fonts no)", "\t\t)"])
        i = s.index("\n\t(lib_symbols") + len("\n\t(lib_symbols")
        s = s[:i] + "\n" + lib + s[i:]
    syms = {y["ref"]: y for y in symbols(s)}
    blk = clone(s[syms["TP301"]["a"]:syms["TP301"]["b"]], "J302", "TC2030-NL GAUGE",
                "Connector:Tag-Connect_TC2030-IDC-NL_2x03_P1.27mm_Vertical", GAUGE_TC_AT, "TP301")
    blk = blk.replace('(lib_id "Connector:TestPoint")', '(lib_id "MonolithDev:TC2030_GAUGE")')
    blk = re.sub(r"\n\t\t\(at ([-\d.]+) ([-\d.]+) [-\d.]+\)", lambda m: "\n\t\t(at %s %s 0)" % m.groups(), blk, count=1)
    blk = set_prop(blk, "Description", "Gauge training / golden image: TC2030-IDC-NL cable, 2x3 end to EV2400 + clips")
    blk = _fields(blk, GAUGE_TC_AT, (1.27, -17.78), (1.27, 17.78))
    blk = re.sub(r'\n\t\t\(pin "1"\n\t\t\t\(uuid "[^"]+"\)\n\t\t\)',
                 "".join('\n\t\t(pin "%d"\n\t\t\t(uuid "%s")\n\t\t)' % (n, uid()) for n in range(1, 7)), blk)
    s = insert_top(s, "\n\t" + blk)
    pins = {y["ref"]: y for y in symbols(s)}["J302"]["pins"]
    add = ""
    for i, net in enumerate(GAUGE_TC):
        p = pins[str(i + 1)]
        if net is None:
            add += nc_text(p)
        elif net == "GND":  # pointing left, clear of the SCL label below
            g = _rot(clone_power(power_template(s, "GND"), p).lstrip(), 270)
            g = re.sub(r'(\(property "Value" "GND"\s*\(at [^)]*\))', r"\1\n\t\t\t(hide yes)", g, count=1)
            add += "\n\t" + g
        elif net == "NRST":
            add += label_text("NRST", p, 180)
        else:
            add += _glabel(s, net, p, 180)
    add += _text("GAUGE: 1 SDA, 2 CHG_INH (GND = charge with MCU in reset), 3 NRST (GND = hold MCU), 4 nc, 5 GND, 6 SCL",
                 (GAUGE_TC_AT[0] - 10.16, GAUGE_TC_AT[1] + 20.32))
    return insert_top(s, add)


def add_training_gauge(s):
    """Gauge-sheet training parts (2026-10-18): learning-cycle load pads and the gauge WAKE resistor + pad."""
    syms = {y["ref"]: y for y in symbols(s)}
    tp = s[syms["TP106"]["a"]:syms["TP106"]["b"]]
    add = "\n\t" + clone(tp, "J113", "LOAD PACK_P", LOAD_PAD, (170.18, 264.16), "TP106")
    add += "\n\t" + clone(tp, "J114", "LOAD GND", LOAD_PAD, (185.42, 264.16), "TP106")
    add += "\n\t" + clone(tp, "TP113", "WAKE", PAD, (210.82, 264.16), "TP106")
    r = new_uuids(s[syms["R113"]["a"]:syms["R113"]["b"]])
    x0, y0 = syms["R113"]["at"][:2]
    r = re.sub(r"\(at ([-\d.]+) ([-\d.]+)", lambda m: "(at %g %g" % (
        round(float(m.group(1)) - x0 + 200.66, 2), round(float(m.group(2)) - y0 + 259.08, 2)), r)
    r = re.sub(r"\n\t\t\(at ([-\d.]+) ([-\d.]+) [-\d.]+\)", lambda m: "\n\t\t(at %s %s 0)" % m.groups(), r, count=1)
    r = re.sub(r"\n\t\t\(mirror \w\)", "", r)
    for k, v in (("Reference", "R118"), ("Value", "4.7k"), ("Footprint", R0402), ("LCSC", "C25900"),
                 ("MPN", "0402WGF4701TCE")):
        if '(property "%s" ' % k in r:
            r = set_prop(r, k, v)
    r = r.replace('(reference "R113")', '(reference "R118")')
    r = _fields(r, (200.66, 259.08), (3.81, -1.27), (3.81, 1.27))
    if '(property "Notes" ' in r:
        r = set_prop(r, "Notes", "Gauge wake: bridge TP113 (WAKE) to TP106 (PACK_P) with tweezers")
    add += "\n\t" + r
    s = insert_top(s, add)
    cur = {y["ref"]: y for y in symbols(s)}
    tp106_pin = cur["TP106"]["pins"]["1"]  # copy TP106's own (downward) PACK_P symbol, text placement included
    down = next(s[y["a"]:y["b"]] for y in symbols(s)
                if y["power"] and tp106_pin in y["pins"].values() and '"PACK_P"' in s[y["a"]:y["b"]])
    a = clone_power(down, cur["J113"]["pins"]["1"])
    a = re.sub(r"\n\t\t\(at ([-\d.]+) ([-\d.]+) 0\)", lambda m: "\n\t\t(at %s %s 180)" % m.groups(), a, count=1) \
        if "\n\t\t(at " in a and re.search(r"\n\t\t\(at [-\d.]+ [-\d.]+ 180\)", down) else a
    a += clone_power(power_template(s, "GND"), cur["J114"]["pins"]["1"])
    rp = cur["R118"]["pins"]
    top, bot = sorted((rp["1"], rp["2"]), key=lambda q: q[1])
    a += label_text("CELL_P", top) + label_text("WAKE", bot) + label_text("WAKE", cur["TP113"]["pins"]["1"])
    a += _text("Training: J113/J114 = learning-cycle load wires (20 AWG).\\nWAKE: bridge TP113 to TP106 (PACK_P).",
               (165.1, 275.59))
    return insert_top(s, a)


def add_gauge_pads(s, old):
    syms = {y["ref"]: y for y in symbols(s)}
    tmpl = s[syms["TP106"]["a"]:syms["TP106"]["b"]]
    add = ""
    glabel = {}
    for a, b in top_blocks(s, "global_label"):
        m = re.match(r'\(global_label "([^"]+)"[\s\S]*?\(at [-\d.]+ [-\d.]+ 180\)', s[a:b])
        if m:
            glabel.setdefault(m.group(1), s[a:b])
    gnd = next(s[y["a"]:y["b"]] for y in symbols(s) if y["lib"] == "power:GND")
    for ref, value, fp, (oref, opin) in GAUGE_PADS:
        if ref not in POGO_AT:
            add += "\n\t" + clone(tmpl, ref, value, fp, old[oref]["pins"][opin], "TP106")
            continue
        at, net = POGO_AT[ref]
        add += "\n\t" + clone(tmpl, ref, value, fp, at, "TP106")
        if net == "GND":
            add += clone_power(gnd, at)
        else:
            b = new_uuids(glabel[net])
            x0, y0 = map(float, re.search(r"\(at ([-\d.]+) ([-\d.]+)", b).groups())
            b = re.sub(r"\(at ([-\d.]+) ([-\d.]+)", lambda m: "(at %g %g" % (
                round(float(m.group(1)) - x0 + at[0], 2), round(float(m.group(2)) - y0 + at[1], 2)), b)
            add += "\n\t" + b
    return insert_top(s, add)


def group_pins(s, p):
    """'REF.pin' of every non-power pin wired to point p (wire ends, T-joins and pins along the wires)."""
    syms, ws, ends, labels, pins = connection_state(s)
    seen, todo = {p}, [p]
    while todo:
        q = todo.pop()
        for w in ws:
            if q in w["p"] or on_segment(q, w["p"]):
                for r in w["p"]:
                    if r not in seen:
                        seen.add(r)
                        todo.append(r)
    hit = set(seen)
    for w in ws:
        if any(q in w["p"] for q in seen):
            hit |= {q for q in pins if on_segment(q, w["p"])}
    return {"%s.%s" % (y["ref"], n) for q in hit for y in pins.get(q, []) if not y["power"]
            for n, pp in y["pins"].items() if pp == q}


def add_kelvin(s):
    """1N / 4P Kelvin split (KELVIN): each CELL_N power symbol or CELL_P_RAW label whose pins all move becomes a
    CELL_1N / CELL_4P label, and the two Kelvin slots J115 / J116 are added beside J108 / J112."""
    spans, add, moved = [], "", set()
    for y in symbols(s):
        if y["power"] and '(property "Value" "%s"' % KELVIN_FROM["CELL_1N"] in s[y["a"]:y["b"]]:
            p = list(y["pins"].values())[0]
            g = group_pins(s, p)
            if g and g <= set(KELVIN["CELL_1N"]):
                spans.append((y["a"], y["b"]))
                left = abs(y["at"][2] - 270) < 1   # rotated to point left: keep the label on that side
                add += label_text("CELL_1N", p, 180 if left else 0)
                moved |= g
            else:
                assert not g & set(KELVIN["CELL_1N"]), ("CELL_N symbol mixes Kelvin and power pins", sorted(g))
    for x in anchors(s, "label"):
        if x["name"] == KELVIN_FROM["CELL_4P"]:
            g = group_pins(s, x["p"])
            if g and g <= set(KELVIN["CELL_4P"]):
                spans.append((x["a"], x["b"]))
                add += "\n\t" + s[x["a"]:x["b"]].replace('(label "CELL_P_RAW"', '(label "CELL_4P"', 1)
                moved |= g
            else:
                assert not g & set(KELVIN["CELL_4P"]), ("CELL_P_RAW label mixes Kelvin and power pins", sorted(g))
    missing = (set(KELVIN["CELL_1N"]) | set(KELVIN["CELL_4P"])) - moved
    assert not missing, ("Kelvin pins not found on their power net", sorted(missing))
    s = insert_top(cut(s, spans), add)
    syms = {y["ref"]: y for y in symbols(s)}
    tmpl = s[syms["TP106"]["a"]:syms["TP106"]["b"]]
    add = ""
    for ref, (net, at) in KELVIN_AT.items():
        slot = "1N" if net == "CELL_1N" else "4P"
        add += "\n\t" + clone(tmpl, ref, "%s Kelvin wire" % slot, SLOTS[slot], at, "TP106")
        add += label_text(net, at)
    # CELL_1N feeds the gauge's VSS pins: a PWR_FLAG on a stub to the left of J115, as #FLG101 sits beside J108
    flg = syms["#FLG101"]
    x0, y0 = flg["at"][:2]
    at = KELVIN_AT["J115"][1]
    q = (round(at[0] - 5.08, 2), at[1])
    b = new_uuids(s[flg["a"]:flg["b"]]).replace('"#FLG101"', '"#FLG107"')
    b = re.sub(r"\(at ([-\d.]+) ([-\d.]+)", lambda m: "(at %g %g" % (
        round(float(m.group(1)) - x0 + q[0], 2), round(float(m.group(2)) - y0 + q[1], 2)), b)
    add += "\n\t" + b + wire_text(q, at)
    return insert_top(s, add)


SHARED_BULK_AT = (63.5, 133.35)  # power sheet, under the 3V3 rail
SHARED_BULK = ["C208", "C209", "C210", "C211", "C212", "C213"]
GMK = GMK_PROPS


def add_shared_bulk(s):
    """Shared PACK_P bulk for both chargers' battery sides and both TPS62933 inputs: six 22 uF 35 V 1210 MLCCs
    (2.7 mm max), low_profile_sims.py option N1. Was one 100 uF hybrid can (7.7 mm tall); polymer chips that fit
    under the inductors' 3.1 mm are rated for hundreds of uA leakage, too much for this always-live bus.
    Cloned from C206 (Device:C on this sheet)."""
    host = next(y for y in symbols(s) if y["ref"] == "C206")
    tmpl = s[host["a"]:host["b"]]
    add = ""
    for i, ref in enumerate(SHARED_BULK):
        at = (SHARED_BULK_AT[0] + 10.16 * i, SHARED_BULK_AT[1])
        blk = clone(tmpl, ref, GMK["Value"], GMK["Footprint"], at, "C206")
        blk = set_prop(set_prop(blk, "LCSC", GMK["LCSC"]), "MPN", GMK["MPN"])
        add += "\n\t" + blk
    s = insert_top(s, add)
    pins = {y["ref"]: y["pins"] for y in symbols(s) if y["ref"] in SHARED_BULK}
    first = pins[SHARED_BULK[0]]
    add = clone_power(power_template(s, "PACK_P"), first["1"]) + clone_power(power_template(s, "GND"), first["2"])
    for r, q in zip(SHARED_BULK, SHARED_BULK[1:]):  # top and bottom rails across the row
        add += wire_text(pins[r]["1"], pins[q]["1"]) + wire_text(pins[r]["2"], pins[q]["2"])
    head = next((a, b) for a, b in top_blocks(s, "text") if "3.3 V ALWAYS-ON RAIL" in s[a:b])
    t = new_uuids(s[head[0]:head[1]])
    t = re.sub(r'\(text "[^"]*"', '(text "PACK_P SHARED BULK  (both chargers + both 5 V buck inputs): 6x 22u 35V 1210, '
               'between the two power stages beside the RBAT pads"', t, count=1)
    t = re.sub(r"\(at [-\d.]+ [-\d.]+", "(at 40.64 116.84", t, count=1)
    add += "\n\t" + t
    return insert_top(s, add)


PEGS = ["H101", "H102", "H103", "H104"]  # carrier peg holes, in MS.CUP_PEGS order; make_board.py --mech places them
PEG_AT = (63.5, 154.94)                   # power sheet, under the shared bulk (outside layout_production's moves)
MECH_SYM = r"C:\Program Files\KiCad\10.0\share\kicad\symbols\Mechanical.kicad_sym"
PEG_FP = "Peg_NPTH_Slot%gx%gmm" % MS.CUP_PEG_SLOT
PEG_PROPS = {"Value": "Peg slot %gx%g NPTH" % MS.CUP_PEG_SLOT, "Footprint": "MonolithDev:" + PEG_FP,
             "Datasheet": "", "Description": "NPTH for a %g mm PA12 carrier peg (mechanical/monolith_shell.py CUP_PEGS)"
             % MS.CUP_PEG_D, "LCSC": "", "MPN": ""}


def add_pegs(s):
    """Four NPTH holes for the cup carrier's board pegs (mechanical/monolith_cup.py, 2026-10-21): the pegs locate the
    board on the carrier and stand CUP_PEG_PROUD above F.Cu. They replace the aluminium cover's SMT standoffs (same
    references H101-H104, so Update PCB swaps the footprints). Mechanical:MountingHole symbol: no pins, no net, not in
    the BOM. Cloned from C206."""
    from schlib import block_end
    lib = open(MECH_SYM, encoding="utf-8").read()
    a = lib.index('\n\t(symbol "MountingHole"\n') + 1
    sym = lib[a:block_end(lib, a + 1)].replace('(symbol "MountingHole"', '(symbol "Mechanical:MountingHole"', 1)
    sym = "\n".join("\t" + ln for ln in sym.split("\n"))
    i = s.index("\n\t(lib_symbols") + len("\n\t(lib_symbols")
    s = s[:i] + "\n" + sym + s[i:]
    host = next(y for y in symbols(s) if y["ref"] == "C206")
    tmpl = s[host["a"]:host["b"]]
    add = ""
    for k, ref in enumerate(PEGS):
        blk = clone(tmpl, ref, PEG_PROPS["Value"], PEG_PROPS["Footprint"], (PEG_AT[0] + 15.24 * k, PEG_AT[1]), "C206")
        blk = re.sub(r'\(lib_id "[^"]+"\)', '(lib_id "Mechanical:MountingHole")', blk, count=1)
        blk = blk.replace("(in_bom yes)", "(in_bom no)", 1)
        for prop in ("Datasheet", "Description", "LCSC", "MPN"):
            blk = set_prop(blk, prop, PEG_PROPS[prop])
        if '(property "Notes" ' in blk:
            blk = set_prop(blk, "Notes", "")
        blk = blk[:blk.index('\n\t\t(pin "')] + blk[blk.index("\n\t\t(instances"):]
        add += "\n\t" + blk
    head = next((a, b) for a, b in top_blocks(s, "text") if "3.3 V ALWAYS-ON RAIL" in s[a:b])
    t = new_uuids(s[head[0]:head[1]])
    t = re.sub(r'\(text "[^"]*"', '(text "CARRIER PEG SLOTS  (4x %g x %g mm NPTH for the cup carrier\'s %g mm pegs; positions '
               'from mechanical/monolith_shell.py CUP_PEGS, placed by make_board.py --mech)"'
               % (MS.CUP_PEG_SLOT + (MS.CUP_PEG_D,)), t, count=1)
    t = re.sub(r"\(at [-\d.]+ [-\d.]+", "(at 40.64 142.24", t, count=1)
    add += "\n\t" + t
    return insert_top(s, add)


LOW_PROFILE_AT = {"C456": (378.46, 121.92)}  # usb sheet, right of C430 on AC_SNS_N


def add_usb_bulk(s, templates):
    """Per port: a second 35V polymer tantalum (C456; CA55 47u until 2026-10-31, now T593V 68u) on AC_SNS_N, with C421 -> CA55:
    low_profile_sims.py option C2. Clone of C421 (both ports' instance paths)."""
    syms = {y["ref"]: y for y in symbols(s)}
    add = ""
    for ref, src in (("C456", "C421"),):
        tmpl = s[syms[src]["a"]:syms[src]["b"]]
        val = re.search(r'\(property "Value" "([^"]*)"', tmpl).group(1)
        fp = re.search(r'\(property "Footprint" "([^"]*)"', tmpl).group(1)
        blk = clone(tmpl, ref, val, fp, LOW_PROFILE_AT[ref], src)
        blk = blk.replace('(reference "%s")' % (src[0] + "5" + src[2:]), '(reference "%s")' % (ref[0] + "5" + ref[2:]))
        if '(property "Notes" ' in blk:
            blk = set_prop(blk, "Notes", "Second T593V 68u on AC_SNS_N, see C421")
        add += "\n\t" + blk
    s = insert_top(s, add)
    pins = {y["ref"]: y["pins"] for y in symbols(s) if y["ref"] in LOW_PROFILE_AT}
    add = wire_text((368.3, 118.11), pins["C456"]["1"])
    add += "".join(clone_power(templates["GND"], pins[r]["2"]) for r in LOW_PROFILE_AT)
    return insert_top(s, add)


# 9 V gate drive per port (loss cut 2, adopted 2026-10-23; drawn 2026-10-28). Port 1 refs, port 2 = 5xx.
# U406 TPS7A4101 runs from PACK_P and sets ~9.6 V (40.2k / 5.6k on FB); D411 ORs it onto DRV_SUP. D410 replaces R420
# (10 R REGN -> DRV_SUP): with the LDO off, DRV_SUP is REGN - VF, the TI-standard drive, so a dead pack still charges.
# EN = REGN through R454, pulled low by Q409 unless GPIO6 is low: GPIO6 Hi-Z (reset, no configuration) or high keeps
# the 9 V off; 'GPsl' turns it on, 'GPsh' off. With REGN down EN is low, so DRV_SUP is never driven while the BQ25756
# is off (bq25756.pdf 6.3.3.2). R455 holds Q409 on from the TPS25751's own LDO_3V3.
GATE_DRIVE_AT = (495.3, 190.5)   # usb sheet: U406, in the free area right of the BQ25756 controller block
LDO_SYM = "MonolithDev:TPS7A4101"
GD_PARTS = {  # ref: (template ref, lib_id, (x, y), rotation, props, pin numbers)
    "U406": ("C411", LDO_SYM, GATE_DRIVE_AT, 0, {
        "Value": tps7a4101.VALUE, "Footprint": tps7a4101.FOOTPRINT, "LCSC": tps7a4101.LCSC, "MPN": tps7a4101.MPN,
        "Datasheet": tps7a4101.DATASHEET, "Description": tps7a4101.DESCRIPTION,
        "Notes": "9 V DRV_SUP (loss cut 2): ~9.6 V out (VREF 1.173 x (1 + 40.2k/5.6k)), DRV_SUP ~9.3 V through D411. "
                 "<= 34 mA, <= 0.25 W at 16.8 V: PowerPAD to the GND pour. EN must not exceed IN + 0.3 V: firmware enables "
                 "it only with PACK_P >= 10 V"}, ("1", "2", "3", "4", "5", "6", "7", "8", "9")),
    "C457": ("C411", "Device:C", (477.52, 189.23), 0, {
        "Value": "1u 50V", "Footprint": "Capacitor_SMD:C_0603_1608Metric", "LCSC": "C15849", "MPN": "CL10A105KB8NNNC",
        "Notes": "U406 input (>= 1 uF), at the IN pin"}, ("1", "2")),
    "C458": ("C411", "Device:C", (520.7, 189.23), 0, {
        "Value": "22u 25V", "Footprint": "Capacitor_SMD:C_0805_2012Metric", "LCSC": "C45783", "MPN": "CL21A226MAQNNNE",
        "Notes": "U406 output: >= 4.7 uF needed, about 8 uF left at 9.6 V"}, ("1", "2")),
    "R452": ("R412", "Device:R", (510.54, 189.23), 0, {
        "Value": "40.2k 1%", "Footprint": R0402, "LCSC": "C25893", "MPN": "0402WGF4022TCE", "Notes": "U406 FB top"},
        ("1", "2")),
    "R453": ("R412", "Device:R", (510.54, 196.85), 0, {
        "Value": "5.6k 1%", "Footprint": R0402, "LCSC": "C25908", "MPN": "0402WGF5601TCE", "Notes": "U406 FB bottom"},
        ("1", "2")),
    "D411": ("D404", "Device:D_Schottky", (529.59, 185.42), 180, {
        "Notes": "U406 OUT -> DRV_SUP: keeps REGN off the LDO output (OUT-to-IN abs max 0.3 V)"}, ("1", "2")),
    "R454": ("R412", "Device:R", (486.41, 208.28), 90, {
        "Value": "100k", "Footprint": R0201, "LCSC": "C270364", "MPN": "0201WMF1003TEE",
        "Notes": "U406 EN from REGN: the 9 V can only be on while REGN is"}, ("1", "2")),
    "Q409": ("C411", "Transistor_FET:Q_NMOS_GSD", (480.06, 215.9), 0, {
        "Value": "AO3400A", "Footprint": "Package_TO_SOT_SMD:SOT-23", "LCSC": "C20917", "MPN": "AO3400A (AOS)",
        "Datasheet": "", "Description": "N-MOSFET, logic level",
        "Notes": "Holds U406 EN low unless TPS25751 GPIO6 drives DRV9_OFF low ('GPsl')"}, ("1", "2", "3")),
    "R455": ("R412", "Device:R", (469.9, 212.09), 0, {
        "Value": "100k", "Footprint": R0201, "LCSC": "C270364", "MPN": "0201WMF1003TEE",
        "Notes": "Q409 gate to LDO_3V3: 9 V off while GPIO6 is Hi-Z (reset, no configuration)"}, ("1", "2")),
}
REGN_DIODE = ("R420", "D410")   # 10 R REGN -> DRV_SUP becomes a Schottky (anode REGN, cathode DRV_SUP)
DIODE_PROPS = {"Value": "LRB520S-40T1G", "Footprint": "Diode_SMD:D_SOD-523", "LCSC": "C132124",
               "MPN": "LRB520S-40T1G", "Datasheet": "", "Description": "Schottky diode"}
GD_HEADING = "9 V GATE DRIVE (DRV_SUP): fitted, off by default (loss cut 2)"
BS_N = chr(92) + "n"
GD_NOTE = BS_N.join([
    "U406 TPS7A4101 from PACK_P sets ~9.6 V (R452/R453); D411 ORs it onto DRV_SUP (~9.3 V).",
    "D410 (was R420 10R) feeds REGN - VF while U406 is off: TI's standard drive, so a dead pack",
    "still charges. EN = REGN via R454, held low by Q409 unless TPS25751 GPIO6 (DRV9_OFF) is low:",
    "GPIO6 Hi-Z or high = off. Configure GPIO6 as an output, initial high; 'GPsl' on, 'GPsh' off.",
    "Firmware: on only while this converter switches, for contracts >= 45 W and PACK_P >= 10 V",
    "(EN <= IN + 0.3 V); off first on any fault or INT (bq25756.pdf 6.3.3.2: DRV_SUP off whenever",
    "the converter is). SiZ240DT: ~30 % lower RDS(on) at 9 V. If SW1/SW2 ring, fit 2.2-4.7R in R444-R447."])


# check_netlist: the gate-drive parts' nets, port 1 refs (a dev-board pin on that net, or "new NAME"), and the part
# they replace
_GND, _PACK, _REGN, _DRV = ("TP109", "1"), ("R418", "1"), ("U403", "24"), ("U403", "23")
GD_NETS = {"U406": {"8": _PACK, "5": "new DRV9_EN", "1": "new DRV9_OUT", "2": "new DRV9_FB", "4": _GND, "9": _GND,
                    "3": None, "6": None, "7": None},
           "C457": {"1": _PACK, "2": _GND}, "C458": {"1": "new DRV9_OUT", "2": _GND},
           "R452": {"1": "new DRV9_OUT", "2": "new DRV9_FB"}, "R453": {"1": "new DRV9_FB", "2": _GND},
           "D411": {"2": "new DRV9_OUT", "1": _DRV}, "D410": {"2": _REGN, "1": _DRV},
           "R454": {"1": "new DRV9_EN", "2": _REGN}, "Q409": {"3": "new DRV9_EN", "2": _GND, "1": "new DRV9_OFF"},
           "R455": {"1": ("U401", "1"), "2": "new DRV9_OFF"}}
GD_GONE = ["R420"]


def _place(s, tmpl_ref, ref, lib_id, at, rot, props, pins):
    """A new symbol block from a placed 4xx part (so it carries both ports' instance paths)."""
    y = next(y for y in symbols(s) if y["ref"] == tmpl_ref)
    blk = new_uuids(s[y["a"]:y["b"]])
    x0, y0 = map(float, re.search(r"\n\t\t\(at ([-\d.]+) ([-\d.]+)", blk).groups())
    blk = re.sub(r"\(at ([-\d.]+) ([-\d.]+)", lambda m: "(at %g %g" % (
        round(float(m.group(1)) - x0 + at[0], 2), round(float(m.group(2)) - y0 + at[1], 2)), blk)
    blk = re.sub(r"\n\t\t\(at ([-\d.]+) ([-\d.]+) [-\d.]+\)", lambda m: "\n\t\t(at %s %s %d)" % (m.group(1), m.group(2), rot),
                 blk, count=1)
    blk = re.sub(r"\n\t\t\(mirror \w\)", "", blk)
    blk = re.sub(r'\(lib_id "[^"]+"\)', '(lib_id "%s")' % lib_id, blk, count=1)
    blk = set_prop(blk, "Reference", ref)
    for k, v in props.items():
        assert '(property "%s" ' % k in blk, (tmpl_ref, k)
        blk = set_prop(blk, k, v)
    a = blk.index('\n\t\t(pin "')
    b = blk.index("\n\t\t(instances")
    blk = blk[:a] + "".join('\n\t\t(pin "%s"\n\t\t\t(uuid "%s")\n\t\t)' % (p, uid()) for p in pins) + blk[b:]
    port2 = tmpl_ref[:-3] + "5" + tmpl_ref[-2:]
    blk = blk.replace('(reference "%s")' % tmpl_ref, '(reference "%s")' % ref)
    return blk.replace('(reference "%s")' % port2, '(reference "%s")' % (ref[:-3] + "5" + ref[-2:]))


def _junction(p):
    return '\n\t(junction\n\t\t(at %g %g)\n\t\t(diameter 0)\n\t\t(color 0 0 0 0)\n\t\t(uuid "%s")\n\t)' % (p[0], p[1], uid())


def add_gate_drive(s, templates):
    """Loss cut 2: per-port 9 V DRV_SUP (GD_PARTS), R420 -> D410, and TPS25751 GPIO6 freed from the GND rail as the
    active-low enable DRV9_OFF."""
    for name, sym in ((LDO_SYM, tps7a4101.lib_symbol()), ("Transistor_FET:Q_NMOS_GSD", q_nmos_symbol())):
        if '(symbol "%s"' % name not in s:
            i = s.index("\n\t(lib_symbols") + len("\n\t(lib_symbols")
            s = s[:i] + "\n" + sym + s[i:]
    # R420 -> D410 in place (same pins: rotated 180, pin 2 = anode on REGN, pin 1 = cathode on DRV_SUP)
    old, new = REGN_DIODE
    y = next(y for y in symbols(s) if y["ref"] == old)
    blk = s[y["a"]:y["b"]]
    blk = re.sub(r'\(lib_id "[^"]+"\)', '(lib_id "Device:D_Schottky")', blk, count=1)
    blk = re.sub(r"\n\t\t\(at ([-\d.]+) ([-\d.]+) [-\d.]+\)", lambda m: "\n\t\t(at %s %s 180)" % m.groups(), blk, count=1)
    blk = set_prop(blk, "Reference", new)
    for k, v in DIODE_PROPS.items():
        blk = set_prop(blk, k, v)
    blk = set_prop(blk, "Notes", "REGN -> DRV_SUP (was R420 10 R): the gate drive whenever U406 is off, incl. dead-pack charging")
    blk = blk.replace('(reference "%s")' % old, '(reference "%s")' % new)
    blk = blk.replace('(reference "%s")' % (old[:-3] + "5" + old[-2:]), '(reference "%s")' % (new[:-3] + "5" + new[-2:]))
    s = s[:y["a"]] + blk + s[y["b"]:]
    add = ""
    for ref, (tmpl, lib, at, rot, props, pins) in GD_PARTS.items():
        if lib == "Device:D_Schottky":
            props = {**DIODE_PROPS, **props}
        add += "\n\t" + _place(s, tmpl, ref, lib, at, rot, props, pins)
    s = insert_top(s, add)
    P = {y["ref"]: y["pins"] for y in symbols(s) if y["ref"] in GD_PARTS}
    u, q = P["U406"], P["Q409"]
    assert u["8"] == (485.14, 185.42) and u["5"] == (485.14, 193.04) and u["4"] == u["9"] == (495.3, 200.66), u
    assert q["3"] == (482.6, 210.82) and q["2"] == (482.6, 220.98) and q["1"] == (474.98, 215.9), q
    gnd, pack = templates["GND"], power_template(s, "PACK_P")
    en = (482.6, 208.28)          # EN node: R454, Q409 drain
    gate = P["R455"]["2"]         # (469.9, 215.9) on the gate line
    add = clone_power(pack, P["C457"]["1"]) + wire_text(P["C457"]["1"], u["8"])
    add += "".join(clone_power(gnd, p) for p in (P["C457"]["2"], u["4"], P["R453"]["2"], P["C458"]["2"], q["2"]))
    add += wire_text(u["1"], P["R452"]["1"]) + wire_text(P["R452"]["1"], P["C458"]["1"])
    add += wire_text(P["C458"]["1"], P["D411"]["2"]) + _junction(P["R452"]["1"]) + _junction(P["C458"]["1"])
    add += wire_text(u["2"], P["R452"]["2"]) + _junction(P["R452"]["2"])
    add += label_text("DRV_SUP", P["D411"]["1"])
    add += wire_text(u["5"], (en[0], u["5"][1])) + wire_text((en[0], u["5"][1]), en) + wire_text(en, q["3"])
    assert P["R454"]["1"] == en, P["R454"]
    add += _junction(en) + label_text("REGN", P["R454"]["2"])
    add += wire_text(q["1"], gate) + wire_text(gate, (gate[0] - 5.08, gate[1])) + _junction(gate)
    add += label_text("DRV9_OFF", (gate[0] - 5.08, gate[1]), 180) + label_text("LDO_3V3", P["R455"]["1"], 180)
    t = next((a, b) for a, b in top_blocks(s, "text") if "BQ25756 CONTROLLER" in s[a:b])
    t = new_uuids(s[t[0]:t[1]])
    t = re.sub(r'\(text "[^"]*"', '(text "%s"' % GD_HEADING, t, count=1)
    t = re.sub(r"\(at [-\d.]+ [-\d.]+", "(at 459.74 172.72", t, count=1)
    add += "\n\t" + t
    n = next((a, b) for a, b in top_blocks(s, "text") if "Charger battery side joins PACK_P" in s[a:b])  # a plain note
    n = new_uuids(s[n[0]:n[1]])
    n = re.sub(r'\(text "[^"]*"', '(text "%s"' % GD_NOTE, n, count=1)
    n = re.sub(r"\(at [-\d.]+ [-\d.]+", "(at 459.74 246.38", n, count=1)
    add += "\n\t" + n
    s = insert_top(s, add)
    return free_gpio6(s)


def free_gpio6(s):
    """U401 GPIO6 (pin 37) leaves the unused-GPIO GND rail (pin_actions) for DRV9_OFF. The rail's two segments meeting
    at GPIO6's row become one, so the new wire to the label crosses it without a connection."""
    g6 = {y["ref"]: y for y in symbols(s)}["U401"]["pins"]["37"]
    ws = wires(s)
    stub = next(w for w in ws if g6 in w["p"])
    corner = next(q for q in stub["p"] if q != g6)
    rail = [w for w in ws if corner in w["p"] and w is not stub]
    assert len(rail) == 2 and all(p[0] == corner[0] for w in rail for p in w["p"]), rail
    ends = sorted({p for w in rail for p in w["p"] if p != corner}, key=lambda p: p[1])
    spans = [(w["a"], w["b"]) for w in [stub] + rail]
    spans += [(x["a"], x["b"]) for x in anchors(s, "junction") if x["p"] == corner]
    label_at = (round(corner[0] - 5.08, 2), g6[1])
    add = wire_text(ends[0], ends[1]) + wire_text(g6, label_at) + label_text("DRV9_OFF", label_at, 180)
    return insert_top(cut(s, spans), add)


def q_nmos_symbol():
    """Transistor_FET:Q_NMOS_GSD as embedded on the dev gauge sheet (Q103)."""
    from schlib import block_end
    g = open(os.path.join(DEV, "gauge.kicad_sch"), encoding="utf-8").read()
    a = g.index('\n\t\t(symbol "Transistor_FET:Q_NMOS_GSD"') + 1
    return g[a:block_end(g, a + 2)]


TITLE = {
    ROOT: "Monolith production board - top level",
    "gauge.kicad_sch": "Monolith production board - cells and gauge",
    "power.kicad_sch": "Monolith production board - 3V3 rail",
    "mcu.kicad_sch": "Monolith production board - MCU",
    "usb_port.kicad_sch": "Monolith production board - USB-C port",
}


def title_block(s, sheet):
    s = re.sub(r'\(title "[^"]*"\)', '(title "%s")' % TITLE[sheet], s, count=1)
    s = re.sub(r'\(date "[^"]*"\)', '(date "2026-10-17")', s, count=1)
    s = re.sub(r'\(rev "[^"]*"\)', '(rev "P0")', s, count=1)
    s = re.sub(r'\(company "[^"]*"\)', '(company "Monolith 100 W battery bank - production")', s, count=1)
    s = re.sub(r'\(comment 3 "[^"]*"\)', '(comment 3 "P0: dev board rev A8 stripped by Production/tools/make_production.py; not reviewed")', s, count=1)
    return s


SYM_UUID = re.compile(r'\n\t\t\(uuid "([^"]+)"\)')


def keep_symbol_uuids(s, old_path):
    """Give each part the symbol uuid it had in the existing production sheet. Cloned parts get fresh uuids on every
    run, and Update PCB links footprints by uuid: without this, placed parts would come back as new footprints."""
    if not os.path.exists(old_path):
        return s
    o = open(old_path, encoding="utf-8").read()
    old = {y["ref"]: SYM_UUID.search(o[y["a"]:y["b"]]).group(1) for y in symbols(o) if not y["power"]}
    reps = []
    for y in symbols(s):
        if y["power"] or y["ref"] not in old:
            continue
        m = SYM_UUID.search(s, y["a"], y["b"])
        if m.group(1) != old[y["ref"]]:
            reps.append((m.start(1), m.end(1), old[y["ref"]]))
    for a, b, u in sorted(reps, reverse=True):
        s = s[:a] + u + s[b:]
    return s


def process(sheet, src):
    s = open(src, encoding="utf-8").read()
    s = s.replace('(project "MonolithDev"', '(project "Monolith"')
    s, _ = split_wires(s)
    before = attached(s)
    old = {y["ref"]: y for y in symbols(s)}
    drop = set(REMOVE.get(sheet, [])) | set(LINKS.get(sheet, []))
    missing = drop - set(old)
    assert not missing, (sheet, missing)
    templates = {}
    for y in old.values():
        if y["power"]:
            v = re.search(r'\(property "Value" "([^"]*)"', s[y["a"]:y["b"]]).group(1)
            templates.setdefault(v, s[y["a"]:y["b"]])
    spans, add = [], ""
    for ref in drop:
        spans.append((old[ref]["a"], old[ref]["b"]))
    if sheet != ROOT:  # root straps are joined by renaming their sheet-pin labels instead
        for ref in LINKS.get(sheet, []):
            p = old[ref]["pins"]
            assert len(p) == 2, ref
            add += wire_text(p["1"], p["2"])
    if sheet == "usb_port.kicad_sch":  # name U405's VBIAS cap net before U405 goes (tpd6s300.py)
        add += label_text("VBIAS", old["C451"]["pins"]["1"])
    s = cut(s, spans)
    s = insert_top(s, add)
    if sheet == "gauge.kicad_sch":
        s = add_gauge_pads(s, old)
        s = add_training_gauge(s)
    s, n = prune(s)
    if sheet == "gauge.kicad_sch":
        s = add_kelvin(s)
    if sheet == "power.kicad_sch":
        s = add_shared_bulk(s)
        s = add_pegs(s)
    if sheet == "mcu.kicad_sch":  # after pruning, so its pins can't catch J301's old wires
        s = add_tc2030(s, old)
        s = add_gauge_tc2030(s)
        s, n2 = prune(s)
        n += n2
    s = rename_labels(s, sheet, templates)
    s = pin_actions(s, sheet, templates)
    s, n2 = prune(s)
    n += n2
    s = insert_top(s, "".join(nc_text(p) for p in EXTRA_NC.get(sheet, [])))
    for a, b in TEXT_EDITS.get(sheet, []):
        assert s.count(a) == 1, (sheet, a)
        s = s.replace(a, b)
    s = edit_symbols(s, sheet)
    if sheet == "usb_port.kicad_sch":
        s = swap_fets(s)
        s = add_tpd6s300(s, old, templates)
        s = add_usb_bulk(s, templates)
        s = add_gate_drive(s, templates)
    s = title_block(s, sheet)
    # pins that were connected before and are now open get a no-connect flag
    now = attached(s)
    cur = {y["ref"]: y for y in symbols(s)}
    opened = sorted(rp for rp in before - now if rp[0] in cur and rp[0] not in drop and not cur[rp[0]]["power"])
    s = insert_top(s, "".join(nc_text(cur[r]["pins"][p]) for r, p in opened))
    s = keep_symbol_uuids(s, os.path.join(PROD, sheet))
    open(os.path.join(PROD, sheet), "w", encoding="utf-8", newline="\n").write(s)
    print("%-20s removed %3d parts, %d links, pruned %3d items, new no-connects: %s"
          % (sheet, len(REMOVE.get(sheet, [])), len(LINKS.get(sheet, [])), n, ", ".join("%s.%s" % rp for rp in opened) or "-"))


APS0730 = """(footprint "L_Coilank_APS0730"
\t(version 20241229)
\t(generator "make_production.py")
\t(layer "F.Cu")
\t(descr "Inductor, Coilank APS0730 (APS-F series), 7.8x7.6x3.1mm, datasheet land pattern a 2.8 / b 7.4 / c 7.2 (datasheets/aps0730.pdf)")
\t(tags "inductor molded APS0730")
\t(property "Reference" "REF**" (at 0 -5 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))
\t(property "Value" "L_Coilank_APS0730" (at 0 5 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))
\t(attr smd)
\t(pad "1" smd rect (at -2.55 0) (size 2.3 7.2) (layers "F.Cu" "F.Paste" "F.Mask"))
\t(pad "2" smd rect (at 2.55 0) (size 2.3 7.2) (layers "F.Cu" "F.Paste" "F.Mask"))
\t(fp_rect (start -3.8 -3.9) (end 3.8 3.9) (stroke (width 0.1) (type solid)) (fill no) (layer "F.Fab"))
\t(fp_line (start -1.2 -4.02) (end 1.2 -4.02) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))
\t(fp_line (start -1.2 4.02) (end 1.2 4.02) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))
\t(fp_rect (start -4.05 -4.15) (end 4.05 4.15) (stroke (width 0.05) (type solid)) (fill no) (layer "F.CrtYd"))
\t(fp_text user "${REFERENCE}" (at 0 0 0) (layer "F.Fab") (effects (font (size 0.8 0.8) (thickness 0.12))))
)
"""


def tdson_footprint(src=None):
    """TDSON_FP from KiCad's Infineon_PG-TDSON-8_6.15x5.15mm: drain leads renumbered 5-8 (bottom to top, SO-8 order);
    the drain pad stays 5."""
    t = open(src or KICAD_TDSON, encoding="utf-8").read()
    old = "Infineon_PG-TDSON-8_6.15x5.15mm"
    t = t.replace('(footprint "%s"' % old, '(footprint "%s"' % TDSON_FP, 1).replace('"%s"' % old, '"%s"' % TDSON_FP)
    t = re.sub(r'\(descr "', '(descr "Q101/Q102 BSC007N04LS6 (TDSON-8 FL): drain leads numbered 5-8 (make_production.py). ', t,
               count=1)
    leads = sorted(((float(m.group(2)), m.start(1), m.end(1)) for m in
                    re.finditer(r'\(pad "(5)" smd roundrect\s*\(at [-\d.]+ ([-\d.]+)\)', t)), reverse=True)
    assert len(leads) == 4, leads
    for (y, a, b), num in sorted(zip(leads, "5678"), key=lambda v: -v[0][1]):
        t = t[:a] + num + t[b:]
    return t


def slot_footprint(length):
    """Sense-wire pad (2026-10-24; was a plated slot for a nickel tail): a round SENSE_D hole for a 28 AWG PTFE wire in
    an oval pad (length + 2 x SLOT_RING by SLOT_W + 2 x SLOT_RING along x; 1.5 x 1.4 since sb_slots() gives every pad
    SB_SWIRE_PAD_L), on both faces, no paste (soldered by hand on F.Cu). Courtyard 0.1 mm outside the pad."""
    L = round(length, 2)
    px, py = L + 2 * SLOT_RING, SLOT_W + 2 * SLOT_RING
    cx, cy = px / 2 + 0.1, py / 2 + 0.1
    return "\n".join([
        '(footprint "%s"' % slot_name(L), "\t(version 20241229)", '\t(generator "make_production.py")', '\t(layer "F.Cu")',
        '\t(descr "Plated hole %g mm in a %g x %g mm pad, for a 28 AWG PTFE sense wire soldered on F.Cu '
        '(mechanical/monolith_shell.py sb_slots)")' % (SENSE_D, px, py),
        '\t(tags "connector wire 28AWG PTFE battery sense")',
        '\t(property "Reference" "REF**" (at 0 -%g 0) (layer "F.SilkS") (hide yes) (effects (font (size 0.6 0.6) '
        '(thickness 0.1))))' % (cy + 0.6),
        '\t(property "Value" "%s" (at 0 %g 0) (layer "F.Fab") (effects (font (size 0.6 0.6) (thickness 0.1))))'
        % (slot_name(L), cy + 0.6),
        "\t(attr through_hole exclude_from_pos_files)",
        '\t(pad "1" thru_hole oval (at 0 0) (size %g %g) (drill %g) (layers "*.Cu" "*.Mask") '
        '(remove_unused_layers no))' % (px, py, SENSE_D),
        '\t(fp_rect (start -%g -%g) (end %g %g) (stroke (width 0.05) (type solid)) (fill no) (layer "F.CrtYd"))'
        % (cx, cy, cx, cy),
        '\t(fp_circle (center 0 0) (end %g 0) (stroke (width 0.1) (type solid)) (fill no) (layer "F.Fab"))' % (MS.SB_KWIRE_OD / 2),
        '\t(fp_text user "${REFERENCE}" (at 0 0 0) (layer "F.Fab") (effects (font (size 0.4 0.4) (thickness 0.06))))',
        ")", ""])


def wire_footprint():
    """Plated hole for a PACK power wire: WIRE_D finished, WIRE_RING all round, on both faces, no paste (the wire comes
    from the cell side and is soldered by hand on F.Cu). Fab circle = the wire's insulation."""
    pad = WIRE_D + 2 * WIRE_RING
    c = pad / 2 + 0.25
    return "\n".join([
        '(footprint "%s"' % WIRE_FP, "\t(version 20241229)", '\t(generator "make_production.py")', '\t(layer "F.Cu")',
        '\t(descr "Plated hole %g mm, %g mm ring, for an 18 AWG thin-wall PTFE PACK wire (M22759/11-18, %g mm OD at most) '
        'soldered on F.Cu (mechanical/monolith_shell.py sb_pack_holes)")' % (WIRE_D, WIRE_RING, WIRE_OD),
        '\t(tags "connector wire 18AWG PTFE battery")',
        '\t(property "Reference" "REF**" (at 0 -%g 0) (layer "F.SilkS") (hide yes) (effects (font (size 0.6 0.6) '
        '(thickness 0.1))))' % (c + 0.6),
        '\t(property "Value" "%s" (at 0 %g 0) (layer "F.Fab") (effects (font (size 0.6 0.6) (thickness 0.1))))'
        % (WIRE_FP, c + 0.6),
        "\t(attr through_hole exclude_from_pos_files)",
        '\t(pad "1" thru_hole circle (at 0 0) (size %g %g) (drill %g) (layers "*.Cu" "*.Mask") (remove_unused_layers no))'
        % (pad, pad, WIRE_D),
        '\t(fp_rect (start -%g -%g) (end %g %g) (stroke (width 0.05) (type solid)) (fill no) (layer "F.CrtYd"))'
        % (c, c, c, c),
        '\t(fp_circle (center 0 0) (end %g 0) (stroke (width 0.1) (type solid)) (fill no) (layer "F.Fab"))' % (WIRE_OD / 2),
        '\t(fp_text user "${REFERENCE}" (at 0 0 0) (layer "F.Fab") (effects (font (size 0.4 0.4) (thickness 0.06))))',
        ")", ""])


def peg_footprint():
    """NPTH slot for a carrier peg, long along KiCad x (shell y) so the board floats across the USB-C seal bores' width
    and stays located in z; courtyard on both faces 0.5 mm outside the slot (the peg stands proud of F.Cu and the
    carrier rail bears on B.Cu around it)."""
    w, h = MS.CUP_PEG_SLOT
    cx, cy = w / 2 + 0.5, h / 2 + 0.5
    crt = "".join('\n\t(fp_rect (start -%g -%g) (end %g %g) (stroke (width 0.05) (type solid)) (fill no) (layer "%s"))'
                  % (cx, cy, cx, cy, lay) for lay in ("F.CrtYd", "B.CrtYd"))
    return "\n".join([
        '(footprint "%s"' % PEG_FP, "\t(version 20241229)", '\t(generator "make_production.py")', '\t(layer "F.Cu")',
        '\t(descr "NPTH %g x %g mm slot for a %g mm PA12 carrier peg (mechanical/monolith_cup.py)")' % (w, h, MS.CUP_PEG_D),
        '\t(tags "peg slot npth")',
        '\t(property "Reference" "REF**" (at 0 -%g 0) (layer "F.SilkS") (hide yes) (effects (font (size 0.6 0.6) '
        '(thickness 0.1))))' % (cy + 0.6),
        '\t(property "Value" "%s" (at 0 %g 0) (layer "F.Fab") (effects (font (size 0.6 0.6) (thickness 0.1))))'
        % (PEG_FP, cy + 0.6),
        "\t(attr exclude_from_pos_files exclude_from_bom)",
        '\t(pad "" np_thru_hole oval (at 0 0) (size %g %g) (drill oval %g %g) (layers "*.Cu" "*.Mask"))' % (w, h, w, h)]
        + [crt.lstrip("\n"),
           '\t(fp_rect (start -%g -%g) (end %g %g) (stroke (width 0.12) (type solid)) (fill no) (layer "F.SilkS"))'
           % (cx, cy, cx, cy),
           ")", ""])


def main():
    for f in ("MonolithDev.kicad_sym", "sym-lib-table", "fp-lib-table"):
        shutil.copy2(os.path.join(DEV, f), os.path.join(PROD, f))
    if os.path.isdir(os.path.join(PROD, "MonolithDev.pretty")):
        shutil.rmtree(os.path.join(PROD, "MonolithDev.pretty"))
    shutil.copytree(os.path.join(DEV, "MonolithDev.pretty"), os.path.join(PROD, "MonolithDev.pretty"))
    with open(os.path.join(PROD, "MonolithDev.pretty", "L_Coilank_APS0730.kicad_mod"), "w", encoding="utf-8",
              newline="\n") as f:
        f.write(APS0730)
    with open(os.path.join(PROD, "MonolithDev.pretty", "Vishay_PowerPAIR_3x3S.kicad_mod"), "w", encoding="utf-8",
              newline="\n") as f:
        f.write(siz240dt.footprint())
    with open(os.path.join(PROD, "MonolithDev.pretty", tpd6s300.FP_NAME + ".kicad_mod"), "w", encoding="utf-8",
              newline="\n") as f:
        f.write(tpd6s300.footprint())
    with open(os.path.join(PROD, "MonolithDev.pretty", TDSON_FP + ".kicad_mod"), "w", encoding="utf-8", newline="\n") as f:
        f.write(tdson_footprint())
    for length in sorted({v[2] for v in MS.sb_slots().values()}):
        with open(os.path.join(PROD, "MonolithDev.pretty", slot_name(length) + ".kicad_mod"), "w", encoding="utf-8",
                  newline="\n") as f:
            f.write(slot_footprint(length))
    with open(os.path.join(PROD, "MonolithDev.pretty", WIRE_FP + ".kicad_mod"), "w", encoding="utf-8", newline="\n") as f:
        f.write(wire_footprint())
    with open(os.path.join(PROD, "MonolithDev.pretty", PEG_FP + ".kicad_mod"), "w", encoding="utf-8", newline="\n") as f:
        f.write(peg_footprint())
    import make_3d_models  # 3D models the DevBoard footprints lack (Production/3dmodels, make_3d_models.py)
    make_3d_models.attach_library(os.path.join(PROD, "MonolithDev.pretty"))
    lib = os.path.join(PROD, "MonolithDev.kicad_sym")
    t = open(lib, encoding="utf-8").read()
    if '(symbol "SiZ240DT"' not in t:
        t = t.rstrip()[:-1].rstrip() + "\n" + siz240dt.library_entry() + "\n)\n"
    if '(symbol "TPD6S300"' not in t:
        t = t.rstrip()[:-1].rstrip() + "\n" + tpd6s300.library_entry() + "\n)\n"
    if '(symbol "TPS7A4101"' not in t:
        t = t.rstrip()[:-1].rstrip() + "\n" + tps7a4101.library_entry() + "\n)\n"
    open(lib, "w", encoding="utf-8", newline="\n").write(t)
    pro = open(os.path.join(DEV, "MonolithDev.kicad_pro"), encoding="utf-8").read()
    pro = pro.replace('"MonolithDev.kicad_pro"', '"Monolith.kicad_pro"').replace('"MonolithDev.kicad_sch"', '"Monolith.kicad_sch"')
    pro = pro.replace('"name": "MonolithDev"', '"name": "Monolith"')
    if not os.path.exists(os.path.join(PROD, "Monolith.kicad_pro")):  # it holds the board's rules from here on
        open(os.path.join(PROD, "Monolith.kicad_pro"), "w", encoding="utf-8", newline="\n").write(pro)

    process(ROOT, os.path.join(DEV, ROOT_DEV))
    for sh in SHEETS:
        process(sh, os.path.join(DEV, sh))
    # the J302 symbol exists only embedded in the MCU sheet: copy it into the project library as well
    from schlib import block_end
    m = open(os.path.join(PROD, "mcu.kicad_sch"), encoding="utf-8").read()
    a = m.index('\n\t\t(symbol "MonolithDev:TC2030_GAUGE"') + 1
    sym = m[a:block_end(m, a + 2)].replace('"MonolithDev:TC2030_GAUGE"', '"TC2030_GAUGE"', 1)
    sym = "\n".join(ln[1:] if ln.startswith("\t") else ln for ln in sym.split("\n"))
    t = open(lib, encoding="utf-8").read()
    if '(symbol "TC2030_GAUGE"' not in t:
        t = t.rstrip()[:-1].rstrip() + "\n" + sym + "\n)\n"
        open(lib, "w", encoding="utf-8", newline="\n").write(t)


if __name__ == "__main__":
    main()
