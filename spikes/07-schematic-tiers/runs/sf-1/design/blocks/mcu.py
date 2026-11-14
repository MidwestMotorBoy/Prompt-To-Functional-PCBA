"""MCU: CC2340R5 Bluetooth LE module with its debug and gauge-training connectors and the shared I2C pull-ups."""
from kernel import *

R0201, C0201 = "Resistor_SMD:R_0201_0603Metric", "Capacitor_SMD:C_0201_0603Metric"

def mcu(v3v3, gnd, sda, scl, irq_n, chg_inh, sleep_n, en_5v1, en_5v2):
    """v3v3: 3.3 V always-on rail. sda/scl/irq_n: system I2C and its shared interrupt (all open drain).
    chg_inh: high stops both chargers. sleep_n: low puts the 3V3 buck in sleep mode. en_5v1/2: 5 V buck enables."""
    with block("MCU"):
        section("CC2340R5MODA module", "Supply, reset and I2C/IRQ pull-ups hang from the 3V3 bus; pins connect by name")
        u = part("MonolithDev", "CC2340R5MODA", "U301", "CC2340R5MODA", "MonolithDev:TI_MHA0024A_CC2340R5MODA_7x10mm",
                 LCSC="", MPN="CC2340R5MODAN0MHAR")
        nrst, swclk, swdio, uart_tx = Net("NRST"), Net("SWCLK"), Net("SWDIO"), Net("UART_TX")
        u["VDDS"] += v3v3; u["GND"] += gnd; u["RSTN"] += nrst
        u["DIO17/SWDCK"] += swclk; u["DIO16/SWDIO"] += swdio; u["DIO18"] += uart_tx
        u["DIO6_A1"] += scl; u["DIO8"] += sda; u["DIO11"] += irq_n
        u["DIO24_A7"] += chg_inh; u["DIO21_A10"] += sleep_n; u["DIO3_X32P"] += en_5v1; u["DIO4_X32N"] += en_5v2
        u["DIO12", "DIO20_A11"] += NC
        C("C301", "4.7u 10V", "0402", v3v3, gnd, serves="U301.VDDS", LCSC="C23733", MPN="CL05A475MP5NRNC")
        C("C302", "0.1u 16V", C0201, v3v3, gnd, serves="U301.VDDS", LCSC="C307380", MPN="CL03A104KO3NNNC")
        C("C303", "0.1u 16V", C0201, v3v3, gnd, serves="U301.VDDS", LCSC="C307380", MPN="CL03A104KO3NNNC")
        R("R302", "100k", R0201, v3v3, nrst, serves="U301.RSTN", LCSC="C270364", MPN="0201WMF1003TEE",
          Notes="RSTN pull-up: SWRS349A fig. 9-1 R1 (100k), with C304 = C92 as the power-on reset")
        C("C304", "0.1u 16V", C0201, nrst, gnd, serves="U301.RSTN", LCSC="C307380", MPN="CL03A104KO3NNNC")
        tp = part("Connector", "TestPoint", "TP301", "3V3", "TestPoint:TestPoint_Pad_D1.0mm"); tp[1] += v3v3

        section("Antenna match (pi network between RFIO and ANT_IN)", "Series C313 and R321 between RFIO and ANT_IN, shunt caps to ground")
        rfio, ant, mid = Net("RFIO"), Net("ANT_IN"), Net("RF_MID")
        u["RFIO"] += rfio; u["ANT_IN"] += ant
        C("C313", "15p C0G", "0402", rfio, mid, LCSC="C1548", MPN="0402CG150J500NT")
        C("C314", "1p C0G", "0402", mid, gnd, LCSC="C1550", MPN="0402CG1R0C500NT",
          Notes="Z60 shunt, DNP as on TI's LaunchPad. Placeholder value: TI characterised the match on 0201 parts, "
                "so retune Z60/Z61/Z62 on this board (review 4 A-10)")
        R("R321", "0R", "0402", mid, ant, LCSC="C17168", MPN="0402WGF0000TCE",
          Notes="Z61 series element of the antenna pi match (TI LaunchPad: 0R). Retune on this board")
        C("C315", "1p C0G", "0402", ant, gnd, LCSC="C1550", MPN="0402CG1R0C500NT")

        section("Pull-ups owned by this block")
        R("R304", "3.3k", R0201, v3v3, scl, serves="U301.DIO6_A1", LCSC="C270350", MPN="0201WMF3301TEE")
        R("R305", "3.3k", R0201, v3v3, sda, serves="U301.DIO8", LCSC="C270350", MPN="0201WMF3301TEE")
        R("R313", "220k", R0201, v3v3, sleep_n, serves="U301.DIO21_A10", LCSC="C473458", MPN="0201WMF2203TEE",
          Notes="3V3_SLEEP pull-up: holds the TPS62177 in normal mode while U301 is in reset or unprogrammed "
                "(pins float; SLEEP pull-down 1.4 uA typ, no max). 220k gives about 0.92 x VDDS typ against VIH "
                "0.8 x VDDS (review 4 A-1b); 15 uA while firmware drives SLEEP low in S2")
        R("R314", "47k", R0201, v3v3, irq_n, serves="U301.DIO11", LCSC="C270345", MPN="0201WMF4702TEE",
          Notes="The one IRQ_N pull-up (TPS25751 I2Ct_IRQ x2, gauge BTP via Q103; all open drain). 47k for leakage "
                "and noise margin on a long net (review 4 A-5); 70 uA only while asserted")

        section("Debug and gauge-training connectors (Tag-Connect, no part fitted)")
        j = part("Connector", "Conn_ARM_SWD_TagConnect_TC2030", "J301", "TC2030-NL",
                 "Connector:Tag-Connect_TC2030-IDC-NL_2x03_P1.27mm_Vertical")
        j["VCC"] += v3v3; j["SWDIO"] += swdio; j["~{RESET}"] += nrst; j["SWCLK"] += swclk; j["GND"] += gnd; j["SWO"] += uart_tx
        g = part("MonolithDev", "TC2030_GAUGE", "J302", "TC2030-NL GAUGE",
                 "Connector:Tag-Connect_TC2030-IDC-NL_2x03_P1.27mm_Vertical")
        g["SDA"] += sda; g["CHG_INH"] += chg_inh; g["NRST"] += nrst; g["NC"] += NC; g["GND"] += gnd; g["SCL"] += scl
        volts(3.6, nrst, swclk, swdio, uart_tx, rfio, ant, mid, sleep_n, en_5v1, en_5v2)
