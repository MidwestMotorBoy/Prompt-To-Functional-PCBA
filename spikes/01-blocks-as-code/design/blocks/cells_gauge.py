"""Cells and gauge: 4S pack connections, BQ40Z50 gauge with back-to-back protection FETs, BQ2947 second-level
protector with a chemical fuse. Parts and wiring were imported from the KiCad sheet (tools/import/sheet_to_block.py);
the intent at the end of the block is written by hand."""
from kernel import *

def cells_gauge(gnd, irq_n, pack_p, scl, sda):
    with block("Cells and Gauge"):
        btp_int = Net("BTP_INT")
        cell1 = Net("CELL1")
        cell2 = Net("CELL2")
        cell3 = Net("CELL3")
        cell_1n = Net("CELL_1N")
        cell_4p = Net("CELL_4P")
        cell_p = Net("CELL_P")
        cell_p_raw = Net("CELL_P_RAW")
        chg = Net("CHG")
        chg_g = Net("CHG_G")
        dsg = Net("DSG")
        dsg_g = Net("DSG_G")
        fet_mid = Net("FET_MID")
        gauge_fuse = Net("GAUGE_FUSE")
        pack_cmid = Net("PACK_CMID")
        srn = Net("SRN")
        srp = Net("SRP")
        ts1 = Net("TS1")
        ts2 = Net("TS2")
        ts3 = Net("TS3")
        ts4 = Net("TS4")
        wake = Net("WAKE")
        cell_n = Net("CELL_N")
        net_c110_pad2 = Net("Net-(C110-Pad2)")
        net_d101_k = Net("Net-(D101-K)")
        net_f102_htr = Net("Net-(F102-HTR)")
        net_q104_g = Net("Net-(Q104-G)")
        net_u101_bat = Net("Net-(U101-BAT)")
        net_u101_pack = Net("Net-(U101-PACK)")
        net_u101_pbi = Net("Net-(U101-PBI)")
        net_u101_smbc = Net("Net-(U101-SMBC)")
        net_u101_smbd = Net("Net-(U101-SMBD)")
        net_u101_vc1 = Net("Net-(U101-VC1)")
        net_u101_vc2 = Net("Net-(U101-VC2)")
        net_u101_vc3 = Net("Net-(U101-VC3)")
        net_u101_vc4 = Net("Net-(U101-VC4)")
        net_u101_vcc = Net("Net-(U101-VCC)")
        net_u102_cd = Net("Net-(U102-CD)")
        net_u102_out = Net("Net-(U102-OUT)")
        net_u102_v1 = Net("Net-(U102-V1)")
        net_u102_v2 = Net("Net-(U102-V2)")
        net_u102_v3 = Net("Net-(U102-V3)")
        net_u102_v4 = Net("Net-(U102-V4)")
        net_u102_vdd = Net("Net-(U102-VDD)")

        section("Cell and load wires")
        j108 = part("Connector", "TestPoint", "J108", "PACK- power wire",
          "MonolithDev:SolderWire-18AWG_PTFE_1x01_D1.5mm_OD2.3mm")
        j108[1] += cell_n
        j109 = part("Connector", "TestPoint", "J109", "CELL1 sense wire",
          "MonolithDev:SolderWire-28AWG_PTFE_1x01_D0.8mm_Pad1.5x1.4mm")
        j109[1] += cell1
        j110 = part("Connector", "TestPoint", "J110", "CELL2 sense wire",
          "MonolithDev:SolderWire-28AWG_PTFE_1x01_D0.8mm_Pad1.5x1.4mm")
        j110[1] += cell2
        j111 = part("Connector", "TestPoint", "J111", "CELL3 sense wire",
          "MonolithDev:SolderWire-28AWG_PTFE_1x01_D0.8mm_Pad1.5x1.4mm")
        j111[1] += cell3
        j112 = part("Connector", "TestPoint", "J112", "PACK+ power wire",
          "MonolithDev:SolderWire-18AWG_PTFE_1x01_D1.5mm_OD2.3mm")
        j112[1] += cell_p_raw
        j113 = part("Connector", "TestPoint", "J113", "LOAD PACK_P",
          "Connector_Wire:SolderWire-0.5sqmm_1x01_D0.9mm_OD2.1mm")
        j113[1] += pack_p
        j114 = part("Connector", "TestPoint", "J114", "LOAD GND",
          "Connector_Wire:SolderWire-0.5sqmm_1x01_D0.9mm_OD2.1mm")
        j114[1] += gnd
        j115 = part("Connector", "TestPoint", "J115", "1N Kelvin wire",
          "MonolithDev:SolderWire-28AWG_PTFE_1x01_D0.8mm_Pad1.5x1.4mm")
        j115[1] += cell_1n
        j116 = part("Connector", "TestPoint", "J116", "4P Kelvin wire",
          "MonolithDev:SolderWire-28AWG_PTFE_1x01_D0.8mm_Pad1.5x1.4mm")
        j116[1] += cell_4p
        j117 = part("Connector_Generic", "Conn_01x01", "J117", "TS2 NTC wire",
          "MonolithDev:SolderWire-28AWG_PTFE_1x01_D0.8mm_Pad1.5x1.4mm")
        j117[1] += ts2
        j118 = part("Connector_Generic", "Conn_01x01", "J118", "TS2 NTC return wire",
          "MonolithDev:SolderWire-28AWG_PTFE_1x01_D0.8mm_Pad1.5x1.4mm")
        j118[1] += cell_1n
        j119 = part("Connector_Generic", "Conn_01x01", "J119", "TS3 NTC wire",
          "MonolithDev:SolderWire-28AWG_PTFE_1x01_D0.8mm_Pad1.5x1.4mm")
        j119[1] += ts3
        j120 = part("Connector_Generic", "Conn_01x01", "J120", "TS3 NTC return wire",
          "MonolithDev:SolderWire-28AWG_PTFE_1x01_D0.8mm_Pad1.5x1.4mm")
        j120[1] += cell_1n

        section("BQ40Z50 gauge: supply, cell inputs, SMBus")
        u101 = part("MonolithDev", "BQ40Z50-R2", "U101", "BQ40Z50RSMR-R2",
          "MonolithDev:TI_RSM0032A_VQFN-32_4x4mm_P0.4mm_EP1.4x1.4mm", LCSC="C2845123", MPN="BQ40Z50RSMR-R2")
        u101[1] += net_u101_pbi
        u101[2] += net_u101_vc4
        u101[3] += net_u101_vc3
        u101[4] += net_u101_vc2
        u101[5] += net_u101_vc1
        u101[6] += srn
        u101[7, 14, 20, 21, 22, 29, 30] += NC
        u101[8] += srp
        u101[9, 16, 17, 23, 24, 33] += cell_1n
        u101[10] += ts1
        u101[11] += ts2
        u101[12] += ts3
        u101[13] += ts4
        u101[15] += btp_int
        u101[18] += net_u101_smbd
        u101[19] += net_u101_smbc
        u101[25] += gauge_fuse
        u101[26] += net_u101_vcc
        u101[27] += net_u101_pack
        u101[28] += dsg
        u101[31] += chg
        u101[32] += net_u101_bat
        d101 = part("Device", "D_Schottky", "D101", "BAT54WS", "Diode_SMD:D_SOD-882", LCSC="C549279",
          MPN="BAT54L,315 (Nexperia)",
          Notes="BAT feed from the cell top before F102, as TI fig. 9-12 (D1 on 4P): isolates BAT from a short-"
                "circuit dip, and keeps the gauge powered and logging if F102 opens")
        d101[1] += net_d101_k
        d101[2] += cell_4p
        R("R105", "100", "0402", net_d101_k, net_u101_bat, LCSC="C25076", MPN="0402WGF1000TCE")
        C("C105", "2.2u 50V", "0805", net_u101_pbi, cell_1n, LCSC="C377773", MPN="CL21A225KBQNNNE",
          Notes="PBI sits near VBAT (16.8 V): 50 V X7R 1206 keeps more of its 2.2 uF than the old 0805 (review "
                "m2; JLC basic since the 2026-10-14 cost-down)")
        R("R106", "100", "0402", fet_mid, net_u101_vcc, LCSC="C25076", MPN="0402WGF1000TCE")
        R("R113", "10k", "0402", pack_p, net_u101_pack, LCSC="C25744", MPN="0402WGF1002TCE")
        R("R101", "100", "0402", cell1, net_u101_vc1, LCSC="C25076", MPN="0402WGF1000TCE",
          Notes="1206 (0.25 W): survives the open-cell fault current until CUV opens DSG (review #7)")
        R("R102", "100", "0402", cell2, net_u101_vc2, LCSC="C25076", MPN="0402WGF1000TCE",
          Notes="1206 (0.25 W): survives the open-cell fault current until CUV opens DSG (review #7)")
        R("R103", "100", "0402", cell3, net_u101_vc3, LCSC="C25076", MPN="0402WGF1000TCE",
          Notes="1206 (0.25 W): survives the open-cell fault current until CUV opens DSG (review #7)")
        R("R104", "100", "0402", cell_4p, net_u101_vc4, LCSC="C25076", MPN="0402WGF1000TCE",
          Notes="1206 (0.25 W): survives the open-cell fault current until CUV opens DSG (review #7)")
        C("C101", "0.1u 50V", "0402", net_u101_vc4, net_u101_vc3, LCSC="C307331", MPN="CL05B104KB54PNC")
        C("C102", "0.1u 50V", "0402", net_u101_vc3, net_u101_vc2, LCSC="C307331", MPN="CL05B104KB54PNC")
        C("C103", "0.1u 50V", "0402", net_u101_vc2, net_u101_vc1, LCSC="C307331", MPN="CL05B104KB54PNC")
        C("C104", "0.1u 50V", "0402", net_u101_vc1, cell_1n, LCSC="C307331", MPN="CL05B104KB54PNC")
        R("R115", "100", "Resistor_SMD:R_0201_0603Metric", net_u101_smbc, scl, LCSC="C270366", MPN="0201WMF1000TEE")
        R("R116", "100", "Resistor_SMD:R_0201_0603Metric", net_u101_smbd, sda, LCSC="C270366", MPN="0201WMF1000TEE")

        section("Current sense")
        R("RS101", "1m 1% 1W", "1206", cell_n, gnd, Notes="1 mOhm 1 % 2 W sense resistor (YAGEO)", LCSC="C154629",
          MPN="LR1206-21R001F4 (Ralec, 75 ppm)")
        R("R107", "100", "0402", cell_n, srp, LCSC="C25076", MPN="0402WGF1000TCE")
        R("R108", "100", "0402", gnd, srn, LCSC="C25076", MPN="0402WGF1000TCE")
        C("C106", "0.1u 50V", "0402", srp, srn, LCSC="C307331", MPN="CL05B104KB54PNC")

        section("Protection FETs (charge and discharge, back to back)")
        q101 = part("MonolithDev", "AGM404AP1", "Q101", "BSC007N04LS6",
          "MonolithDev:Infineon_PG-TDSON-8_6.15x5.15mm_D5-8", Notes="CHG", LCSC="C534274",
          MPN="BSC007N04LS6ATMA1 (Infineon)")
        q101[1, 2, 3] += cell_p
        q101[4] += chg_g
        q101[5, 6, 7, 8] += fet_mid
        q102 = part("MonolithDev", "AGM404AP1", "Q102", "BSC007N04LS6",
          "MonolithDev:Infineon_PG-TDSON-8_6.15x5.15mm_D5-8", Notes="DSG", LCSC="C534274",
          MPN="BSC007N04LS6ATMA1 (Infineon)")
        q102[1, 2, 3] += pack_p
        q102[4] += dsg_g
        q102[5, 6, 7, 8] += fet_mid
        R("R109", "5.1k", "0402", chg, chg_g, LCSC="C25905", MPN="0402WGF5101TCE")
        R("R110", "10M 5%", "0402", chg_g, cell_p, LCSC="C26086", MPN="0402WGJ0106TCE")
        R("R111", "5.1k", "0402", dsg, dsg_g, LCSC="C25905", MPN="0402WGF5101TCE")
        R("R112", "10M 5%", "0402", dsg_g, pack_p, LCSC="C26086", MPN="0402WGJ0106TCE")
        d103 = part("Device", "D_Zener", "D103", "BZT52C15", "Diode_SMD:D_SOD-123", LCSC="C19077412",
          MPN="BZT52C15 (JLC preferred C19077412)",
          Notes="Fitted (2026-10-13, dev board and production): clamps Q102 VGS (AGM404AP1 +/-20 V) in a hard "
                "PACK_P short until SCD opens the FETs (DSG = VBAT + 10.5-12 V, source near 0 V). Vz 13.8-15.6 V "
                "sits above the 10.5-12 V on-state gate drive; leakage at 12 V is tens of nA, which the DSG pump "
                "supplies. Required whenever C109 is fitted. Not in TI fig. 9-2")
        d103[1] += dsg_g
        d103[2] += pack_p
        C("C110", "0.1u 50V", "0402", cell_p, net_c110_pad2, LCSC="C307331", MPN="CL05B104KB54PNC",
          Notes="ESD protection across the back-to-back protection FETs, CELL_P to PACK_P (TI BQ40Z50-R2 sec. "
                "9.2.2.1.1 / fig. 9-2 C1, C2). Two in series so one shorted cap does not bypass the FETs; each is"
                " rated for the full pack voltage. Short, wide traces")
        C("C111", "0.1u 50V", "0402", net_c110_pad2, pack_p, LCSC="C307331", MPN="CL05B104KB54PNC",
          Notes="ESD protection across the back-to-back protection FETs, CELL_P to PACK_P (TI BQ40Z50-R2 sec. "
                "9.2.2.1.1 / fig. 9-2 C1, C2). Two in series so one shorted cap does not bypass the FETs; each is"
                " rated for the full pack voltage. Short, wide traces")
        C("C107", "0.1u 50V", "0402", pack_p, pack_cmid, LCSC="C307331", MPN="CL05B104KB54PNC")
        C("C108", "0.1u 50V", "0402", pack_cmid, gnd, LCSC="C307331", MPN="CL05B104KB54PNC")
        R("R118", "4.7k", "0402", cell_p, wake, LCSC="C25900", MPN="0402WGF4701TCE")
        tp113 = part("Connector", "TestPoint", "TP113", "WAKE", "TestPoint:TestPoint_Pad_D1.0mm")
        tp113[1] += wake

        section("Cell thermistors on the board")
        th101 = part("Device", "Thermistor_NTC", "TH101", "10k B3435", "Resistor_SMD:R_0402_1005Metric",
          LCSC="C77131", MPN="NCP15XH103F03RC",
          Notes="Front-cell NTC, SMD on B.Cu in the outer bottom corner of the gap-filler zone over C1 (BT101), "
                "outboard of the BQ25756 (under the gel; research_notes/Pack thermal BAK 65E/smd-ntc.md). Reads "
                "the board there, 0.6-3.8 K above the hottest point of the C1 (BT101) can in the model. Keep the "
                "inner planes under it; low side to CELL_1N by its own trace. Gauge internal 18k pull-up; enable "
                "TS1 in data flash. Murata NCP15XH103F03RB/RC: B25/50 = 3380 K, B25/85 = 3435 K")
        th101[1] += ts1
        th101[2] += cell_1n
        th104 = part("Device", "Thermistor_NTC", "TH104", "10k B3435", "Resistor_SMD:R_0402_1005Metric",
          LCSC="C77131", MPN="NCP15XH103F03RC",
          Notes="Front-cell NTC, SMD on B.Cu in the outer bottom corner of the gap-filler zone over C4 (BT104), "
                "outboard of the BQ25756 (under the gel; research_notes/Pack thermal BAK 65E/smd-ntc.md). Reads "
                "the board there, 0.6-3.8 K above the hottest point of the C4 (BT104) can in the model. Keep the "
                "inner planes under it; low side to CELL_1N by its own trace. Gauge internal 18k pull-up; enable "
                "TS4 in data flash. Murata NCP15XH103F03RB/RC: B25/50 = 3380 K, B25/85 = 3435 K")
        th104[1] += ts4
        th104[2] += cell_1n

        section("Second-level protector and fuse")
        u102 = part("MonolithDev", "BQ294700", "U102", "BQ294700DSGR",
          "Package_SON:Texas_DSG0008A_WSON-8-1EP_2x2mm_P0.5mm_EP0.9x1.6mm", LCSC="C414622", MPN="BQ294700DSGR",
          Notes="Independent of the gauge: 4.35 V/cell OVP (hysteresis 0.30 V), active-high OUT (~7 V) after the "
                "CD delay. RIN must be 1k (device calibrated with it). Exposed pad to VSS (CELL_1N, the Kelvin "
                "ground at the 1N tab).")
        u102[1] += net_u102_vdd
        u102[2] += net_u102_v4
        u102[3] += net_u102_v3
        u102[4] += net_u102_v2
        u102[5] += net_u102_v1
        u102[6, 9] += cell_1n
        u102[7] += net_u102_cd
        u102[8] += net_u102_out
        R("R119", "1k", "0402", cell_4p, net_u102_v4, LCSC="C11702", MPN="0402WGF1001TCE")
        R("R120", "1k", "0402", cell3, net_u102_v3, LCSC="C11702", MPN="0402WGF1001TCE")
        R("R121", "1k", "0402", cell2, net_u102_v2, LCSC="C11702", MPN="0402WGF1001TCE")
        R("R122", "1k", "0402", cell1, net_u102_v1, LCSC="C11702", MPN="0402WGF1001TCE")
        R("R123", "100", "0402", net_u102_vdd, cell_4p, LCSC="C25076", MPN="0402WGF1000TCE")
        C("C112", "0.1u 50V", "0402", net_u102_v4, net_u102_v3, LCSC="C307331", MPN="CL05B104KB54PNC")
        C("C113", "0.1u 50V", "0402", net_u102_v3, net_u102_v2, LCSC="C307331", MPN="CL05B104KB54PNC")
        C("C114", "0.1u 50V", "0402", net_u102_v2, net_u102_v1, LCSC="C307331", MPN="CL05B104KB54PNC")
        C("C115", "0.1u 50V", "0402", net_u102_v1, cell_1n, LCSC="C307331", MPN="CL05B104KB54PNC")
        C("C116", "0.1u 50V", "0402", net_u102_vdd, cell_1n, LCSC="C307331", MPN="CL05B104KB54PNC")
        C("C117", "0.1u 50V", "0402", cell_1n, net_u102_cd, LCSC="C307331", MPN="CL05B104KB54PNC",
          Notes="CD delay: tCD = 10-20 s/uF x 0.1 uF = 1-2 s. An open or shorted CD also trips OUT during an OV.")
        f102 = part("MonolithDev", "WSFB1514", "F102", "WSFB1514", "MonolithDev:TLC_WSFB_4x3mm", LCSC="C42463217",
          MPN="TLC Electronic WSFB1514",
          Notes="4-cell SCP (UL E467707): 15 A rated at 40 C, cut < 1 min at 2x rated, 50 A break, 36 V max, "
                "heater operating range 10.5-19.6 V (heater resistance not given; same range as Littelfuse "
                "ITV4030L1415, 11.2-20 ohm). Fuse path 1-3 mOhm: about 0.2 W at 10 A. Pin 1 to the cells. Only "
                "fuse in the pack path (F101 deleted): 50 A break, below a cell-top dead short (~200 A); faults "
                "after Q101/Q102 are cleared by the gauge SCD first Same land pattern as the Littelfuse ITV4030 "
                "(pins numbered differently: there fuse 1-3, heater 2)")
        f102[1] += cell_p_raw
        f102[2] += cell_p
        f102[3] += net_f102_htr
        q104 = part("Transistor_FET", "Q_NMOS_GSD", "Q104", "AO3400A", "Package_TO_SOT_SMD:SOT-23", LCSC="C20917",
          MPN="AO3400A (AOS)",
          Notes="Fuse ignition FET (TI Q5): 30 V, Vgs max +-12 V (gate sees <= 8 V through the 5.1k/51k divider),"
                " heater 11.2-20 ohm at 10.5-16.8 V = 0.5-1.5 A for < 1 min")
        q104[1] += net_q104_g
        q104[2] += gnd
        q104[3] += net_f102_htr
        R("R124", "5.1k", "0402", net_u102_out, net_q104_g, LCSC="C25905", MPN="0402WGF5101TCE")
        R("R125", "51k", "0402", net_q104_g, gnd, LCSC="C25794", MPN="0402WGF5102TCE")
        R("R126", "5.1k", "0402", net_q104_g, gauge_fuse, LCSC="C25905", MPN="0402WGF5101TCE")
        C("C118", "0.1u 50V", "0402", net_q104_g, cell_1n, LCSC="C307331", MPN="CL05B104KB54PNC")

        section("Gauge interrupt onto the shared IRQ line")
        q103 = part("Transistor_FET", "Q_NMOS_GSD", "Q103", "AO3400A", "Package_TO_SOT_SMD:SOT-23", LCSC="C20917",
          MPN="AO3400A (AOS)",
          Notes="BTP_INT level shift onto the shared open-drain IRQ_N (inverts: IRQ_N low while BTP_INT is high)."
                " AO3400A Vgs(th) 0.65-1.45 V against BTP_INT VOH >= 1.8 V at 10 uA (DS 7.12); JLC basic, same "
                "part as Q104. Firmware: BTP_POL = 1 whenever BTP_EN = 1 (review 4 D-2)")
        q103[1] += btp_int
        q103[2] += gnd
        q103[3] += irq_n
        R("R117", "470k", "0402", btp_int, cell_1n, LCSC="C25790", MPN="0402WGF4703TCE",
          Notes="Holds Q103 off when BTP_INT floats (BTP_INT VOH is at most about 3.5 V)")

        section("Test points")
        tp106 = part("Connector", "TestPoint", "TP106", "PACK_P", "TestPoint:TestPoint_Pad_D1.0mm")
        tp106[1] += pack_p
        tp109 = part("Connector", "TestPoint", "TP109", "GND", "TestPoint:TestPoint_Pad_D1.0mm", LCSC="",
          MPN="RH-S2761-46R (ronghe; Harwin S2761-46R equivalent)",
          Sourcing="Hand-solder, not JLC assembled (test loop, dev only; saves a JLC extended-part fee; LCSC "
                   "C55121754 RH-S2761-46R (ronghe; Harwin S2761-46R equivalent))")
        tp109[1] += gnd

        section("Intent")
        # The gauge and protector take the cell-1 negative tab (Kelvin wire) as their ground. It differs from GND only
        # by the drop across RS101 and the pack wire.
        volts(0, cell_1n, cell_n)
        volts(16.8, cell_4p, cell_p, cell_p_raw, fet_mid, wake, net_d101_k, net_u101_bat, net_u101_pack, net_u101_vcc,
              net_u101_pbi, net_u101_vc4, net_u102_v4, net_u102_vdd, net_f102_htr, net_c110_pad2, pack_cmid)
        volts(12.6, cell3, net_u101_vc3, net_u102_v3); volts(8.4, cell2, net_u101_vc2, net_u102_v2)
        volts(4.2, cell1, net_u101_vc1, net_u102_v1)
        volts(28.8, chg, chg_g, dsg, dsg_g)          # gauge drives the gates 10.5 to 12 V above the pack
        volts(0.1, srp, srn)                         # 1 mohm sense resistor
        volts(3.6, btp_int, ts1, ts2, ts3, ts4, net_u101_smbc, net_u101_smbd, net_u102_cd)
        volts(16.8, gauge_fuse); volts(8, net_u102_out, net_q104_g)   # OUT about 7 V; gate sees 8 V at most via 5.1k/51k
        across(16.8, "C101", "C102", "C103", "C104", "C112", "C113", "C114", "C110", "C111", "C107", "C108")
        waive("recmax: U101.CHG", "the gauge's own charge pump sets this level (pack + 10.5 to 12 V); the 26 V row in "
              "the recommended table is lower than what the part itself produces on a 16.8 V pack. Logan to confirm")
        waive("recmax: U101.DSG", "same as U101.CHG")

