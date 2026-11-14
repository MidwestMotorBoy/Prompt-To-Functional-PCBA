"""3V3 always-on rail: TPS62177 28 V, 0.5 A step-down with sleep mode, fed straight from the pack."""
from kernel import *

def rail_3v3(pack_p, v3v3, gnd, sleep_n):
    """pack_p: 12 to 16.8 V pack rail. v3v3: 3.3 V out, 0.5 A. sleep_n: low = sleep mode (from the MCU)."""
    with block("3V3 Rail"):
        section("TPS62177 3.3 V always-on buck")
        note('PACK_P (12 to 16.8 V) -> 3V3, 0.5 A. Fixed-output part: VOS senses the output, FB to ground. EN tied to VIN: always on.')
        note('3V3_SLEEP low = sleep mode (driven by the MCU). C206 closes the hot loop; C208 to C213 are the shared pack-rail bulk capacitors.')
        u = part("Regulator_Switching", "TPS62177DQC", "U204", "TPS62177DQCR",
                 "Package_SON:WSON-10-1EP_2x3mm_P0.5mm_EP0.84x2.4mm", LCSC="C91241", MPN="TPS62177DQCR")
        sw = declare(Net("SW_3V3"), kind="switching", swing_v=16.8, edge_ns=5)
        u["VIN"] += pack_p
        u["EN"] += pack_p                 # always on
        u["SW"] += sw
        u["VOS"] += v3v3                  # output sense, fixed 3.3 V version
        u["FB"] += gnd                    # fixed-output part: FB to ground per datasheet
        u["~{SLEEP}"] += sleep_n
        u["PGND", "AGND", "PAD"] += gnd
        u["NC"] += gnd                    # datasheet: connect NC to ground
        u["PG"] += NC

        l = part("Device", "L", "L201", "10u", "Inductor_SMD:L_Changjiang_FNR4030S",
                 LCSC="C167879", MPN="FNR4030S100MT (Changjiang)")
        l[1] += sw; l[2] += v3v3

        C("C206", "2.2u 50V", "0805", pack_p, gnd, serves="U204.VIN", LCSC="C377773", MPN="CL21A225KBQNNNE")
        C("C207", "22u 25V", "0805", v3v3, gnd, serves="L201.2", LCSC="C45783", MPN="CL21A226MAQNNNE")
        hot_loop("HL_3V3", pack_p, gnd, ["U204.VIN", "U204.PGND"], ["C206"])
        declare(v3v3, kind="power", current_a=0.5)
        volts(16.8, sw); volts(3.6, sleep_n)
        draw_as("buck", "U204", vin="VIN", sw="SW", sense="VOS", inductor="L201",
                cin=["C206"] + [f"C{208 + i}" for i in range(6)], cout=["C207"])

        section("Pack-rail bulk capacitance")
        for i in range(6):
            C(f"C{208 + i}", "22u 35V", "1210", pack_p, gnd, LCSC="C778721", MPN="GMK325BJ226MM-P")
