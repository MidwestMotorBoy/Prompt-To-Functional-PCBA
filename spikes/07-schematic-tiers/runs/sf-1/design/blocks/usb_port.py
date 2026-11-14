"""One USB-C PD port of the pack: connector and protection, TPS25751D PD controller, BQ25756 four-switch
buck-boost charger between VBUS and the pack, a 5 V buck for the PD controller, and a 9 V gate-drive LDO.

Used twice. `n` is the reference base (400 for port 1, 500 for port 2).
"""
from kernel import *

C100N = dict(LCSC="C307331", MPN="CL05B104KB54PNC")          # 0.1u 50V 0402
C22U35 = dict(LCSC="C778721", MPN="GMK325BJ226MM-P")         # 22u 35V 1210
R0 = dict(LCSC="C17168", MPN="0402WGF0000TCE")
R10 = dict(LCSC="C25077", MPN="0402WGF100JTCE")
R100K = dict(LCSC="C270364", MPN="0201WMF1003TEE")
R0201 = "Resistor_SMD:R_0201_0603Metric"
SCHOTTKY = dict(LCSC="C132124", MPN="LRB520S-40T1G")

def usb_port(name, n, pack_p, gnd, v3v3, sda, scl, irq_n, chg_inh, en_5v, ldo_3v3, adcin1_high=True):
    """pack_p: pack rail (12 to 16.8 V, 5 A). v3v3: always-on 3.3 V. sda/scl/irq_n: I2C target side to the MCU.
    chg_inh: high stops charging. en_5v: enables the 5 V buck. ldo_3v3: the PD controller's own 3.3 V LDO (out).
    adcin1_high: ADCIN1 strap of the PD controller. It sets the I2C target address, so the two ports must differ."""
    r = lambda k: f"{n + k}"
    net = lambda s: Net(f"{name}/{s}")
    with block(name):
        vbus = declare(net("VBUS"), kind="power", current_a=5, max_v=22, normal_v=20)
        pphv = declare(net("PPHV"), kind="power", current_a=5)
        pp5v = declare(net("PP5V"), kind="power", current_a=1.5)
        i2cc_sda, i2cc_scl, chg_int = net("I2CC_SDA"), net("I2CC_SCL"), net("CHG_INT")

        section("USB-C connector and port protection", "VBUS and CC from the receptacle, ESD and CC/SBU protection to the PD controller")
        j = part("Connector", "USB_C_Receptacle_USB2.0_16P", "J" + r(1), "TYPE-C 16PCB1.6 IP68",
                 "MonolithDev:USB_C_Receptacle_ShouHan_TYPE-C_16PCB1.6_IP68",
                 LCSC="C55629729", MPN="TYPE-C 16PCB1.6 IP68 (Shou Han)")
        c_cc1, c_cc2, cc1, cc2 = net("C_CC1"), net("C_CC2"), net("CC1"), net("CC2")
        j["VBUS"] += vbus
        j["GND", "SHIELD"] += gnd
        j["CC1"] += c_cc1; j["CC2"] += c_cc2
        j["D+", "D-"] += net("DPDN_DCP")        # D+ shorted to D-: dedicated charging port, no data
        j["SBU1", "SBU2"] += NC

        tvs = part("Power_Protection", "TVS2200DRV", "D" + r(1), "TVS2200DRVR",
                   "Package_SON:WSON-6-1EP_2x2mm_P0.65mm_EP1x1.6mm", LCSC="C55616459", MPN="TVS2200DRVR")
        tvs["IN"] += vbus; tvs["GND"] += gnd
        C("C" + r(6), "4.7u 50V", "1206", vbus, gnd, serves=f"J{r(1)}.VBUS", MPN="1206B475K500NT", LCSC="C29823")
        C("C" + r(50), "10n 50V", "0402", vbus, gnd, serves=f"U{r(1)}.VBUS", LCSC="C15195", MPN="CL05B103KB5NNNC")

        esd = part("MonolithDev", "TPD6S300", "U" + r(5), "TPD6S300RUKR",
                   "MonolithDev:TI_RUK0020B_WQFN-20-1EP_3x3mm_P0.4mm_EP1.7x1.7mm_Via0.3",
                   LCSC="C2649810", MPN="TPD6S300RUKR (TI)")
        sbu_flt = net("SBU_FLT")
        esd["C_CC1", "RPD_G1"] += c_cc1         # RPD_Gx to its CC pin: dead-battery Rd
        esd["C_CC2", "RPD_G2"] += c_cc2
        esd["CC1"] += cc1; esd["CC2"] += cc2
        esd["VPWR"] += ldo_3v3
        esd["VBIAS"] += net("VBIAS")
        esd["~{FLT}"] += sbu_flt
        esd["GND", "N.C."] += gnd               # datasheet: tie N.C. pins to ground
        esd["C_SBU1", "C_SBU2", "SBU1", "SBU2", "D1", "D2"] += NC
        C("C" + r(51), "0.1u 50V", "0402", CIRCUIT["nets"][f"{name}/VBIAS"], gnd, serves=f"U{r(5)}.VBIAS", **C100N)
        C("C" + r(52), "1u 25V", "0402", ldo_3v3, gnd, serves=f"U{r(5)}.VPWR", LCSC="C52923", MPN="CL05A105KA5NQNC")
        C("C" + r(1), "220p 50V", "0402", cc1, gnd, LCSC="C1530", MPN="0402B221K500NT")
        C("C" + r(2), "220p 50V", "0402", cc2, gnd, LCSC="C1530", MPN="0402B221K500NT")

        section("USB PD controller TPS25751D, EEPROM and I2C pull-ups")
        pd = part("MonolithDev", "TPS25751D", "U" + r(1), "TPS25751DREFR",
                  "MonolithDev:TI_WQFN-38-2EP_REF0038A_6x4mm_P0.4mm_2oz", LCSC="C30169739", MPN="TPS25751DREFR")
        pd["VBUS", "VBUS_IN"] += vbus
        pd["PPHV"] += pphv                      # internal 5 A switch: VBUS <-> PPHV
        pd["PP5V"] += pp5v
        pd["VIN_3V3"] += v3v3
        pd["LDO_3V3"] += ldo_3v3
        pd["ADCIN1"] += ldo_3v3 if adcin1_high else gnd
        pd["ADCIN2"] += gnd
        pd["LDO_1V5"] += net("LDO_1V5")
        pd["CC1"] += cc1; pd["CC2"] += cc2
        pd["DRAIN", "DRAIN_EP"] += net("PD_DRAIN")
        pd["I2Cc_SDA"] += i2cc_sda; pd["I2Cc_SCL"] += i2cc_scl; pd["~{I2Cc_IRQ}"] += chg_int
        pd["I2Ct_SDA"] += sda; pd["I2Ct_SCL"] += scl; pd["~{I2Ct_IRQ}"] += irq_n
        pd["GPIO3"] += sbu_flt
        drv9_off = net("DRV9_OFF")
        pd["GPIO6"] += drv9_off
        pd["GPIO0", "GPIO1", "GPIO2", "GPIO4", "GPIO5", "GPIO7", "GPIO11"] += gnd     # unused GPIO grounded
        pd["GND"] += gnd
        C("C" + r(3), "10u 25V", "0603", v3v3, gnd, serves=f"U{r(1)}.VIN_3V3", LCSC="C96446", MPN="CL10A106MA8NRNC")
        C("C" + r(4), "10u 25V", "0603", ldo_3v3, gnd, serves=f"U{r(1)}.LDO_3V3", LCSC="C96446", MPN="CL10A106MA8NRNC")
        C("C" + r(8), "0.1u 16V", "Capacitor_SMD:C_0201_0603Metric", ldo_3v3, gnd, serves=f"U{r(2)}.VCC",
          LCSC="C307380", MPN="CL03A104KO3NNNC")
        C("C" + r(5), "10u 6.3V", "0402", CIRCUIT["nets"][f"{name}/LDO_1V5"], gnd, serves=f"U{r(1)}.LDO_1V5",
          LCSC="C15525", MPN="CL05A106MQ5NUNC")
        C("C" + r(7), "10u 25V", "0603", pp5v, gnd, serves=f"U{r(1)}.PP5V", LCSC="C96446", MPN="CL10A106MA8NRNC")
        C("C" + r(9), "1u 50V (VAC)", "0603", pphv, gnd, serves=f"U{r(3)}.VAC", LCSC="C15849", MPN="CL10A105KB8NNNC")
        C("C" + r(49), "0.1u 50V", "0402", pphv, gnd, serves=f"U{r(1)}.PPHV", **C100N)
        R("R" + r(2), "3.3k", R0201, ldo_3v3, i2cc_sda, LCSC="C270350", MPN="0201WMF3301TEE")
        R("R" + r(3), "3.3k", R0201, ldo_3v3, i2cc_scl, LCSC="C270350", MPN="0201WMF3301TEE")
        R("R" + r(4), "10k", R0201, ldo_3v3, chg_int, LCSC="C473048", MPN="0201WMF1002TEE")
        R("R" + r(41), "100k", R0201, ldo_3v3, sbu_flt, **R100K)

        ee = part("Memory_EEPROM", "24LC512", "U" + r(2), "M24512-DFMC6TG",
                  "MonolithDev:ST_UFDFPN-8-1EP_2x3mm_P0.5mm_EP1.2x1.4mm", LCSC="C222237", MPN="M24512-DFMC6TG")
        ee["VCC"] += ldo_3v3
        ee["SDA"] += i2cc_sda; ee["SCL"] += i2cc_scl
        ee["A0", "A1", "A2", "WP", "GND"] += gnd

        section("BQ25756 buck-boost charger: controller and current sense", "Input window dividers and sense filters on the left, gate drivers and feedback on the right")
        chg = part("MonolithDev", "BQ25756", "U" + r(3), "BQ25756RRVR",
                   "MonolithDev:TI_VQFN-36-1EP_RRV0036A_5x6mm_P0.5mm", LCSC="C19272232", MPN="BQ25756RRVR")
        ac_n = declare(net("AC_SNS_N"), kind="power", current_a=5)       # input side of the bridge, after RAC
        bat_p = declare(net("BAT_SNS_P"), kind="power", current_a=5)     # output side, before RBAT
        sw1 = declare(net("SW1"), kind="switching", swing_v=22, edge_ns=5, current_a=6)
        sw2 = declare(net("SW2"), kind="switching", swing_v=17, edge_ns=5, current_a=6)
        regn, drv_sup = net("REGN"), net("DRV_SUP")
        chg["SCL"] += i2cc_scl; chg["SDA"] += i2cc_sda; chg["~{INT}"] += chg_int
        chg["VAC"] += pphv
        chg["PGND"] += gnd
        chg["REGN"] += regn; chg["DRV_SUP"] += drv_sup
        chg["SW1"] += sw1; chg["SW2"] += sw2
        chg["NC", "~{PG}", "~{STAT1}", "~{STAT2}"] += NC

        # input and output current sense, each a Kelvin pair with an RC filter
        acp_f, acn_f, srp_f, srn_f = net("ACP_F"), net("ACN_F"), net("SRP_F"), net("SRN_F")
        R("R" + r(24), "5m 0.5W", "0805", pphv, ac_n, LCSC="C728267", MPN="PA0805FRE470R005L")
        R("R" + r(25), "10R", "0402", pphv, acp_f, **R10)
        R("R" + r(26), "10R", "0402", ac_n, acn_f, **R10)
        C("C" + r(14), "0.47u 25V", "0402", acp_f, acn_f, serves=f"U{r(3)}.ACP", LCSC="C92361", MPN="CL05A474KA5NNNC")
        C("C" + r(15), "0.1u 50V", "0402", acp_f, gnd, serves=f"U{r(3)}.ACP", **C100N)
        C("C" + r(16), "0.1u 50V", "0402", acn_f, gnd, serves=f"U{r(3)}.ACN", **C100N)
        chg["ACP"] += acp_f; chg["ACN"] += acn_f
        kelvin(f"{name}/RAC", "R" + r(24), acp_f, acn_f)
        R("R" + r(27), "5m 1W (RBAT)", "1206", bat_p, pack_p, LCSC="C252653", MPN="MA120610FR005MZ (50 ppm)")
        R("R" + r(28), "10R", "0402", bat_p, srp_f, **R10)
        R("R" + r(29), "10R", "0402", pack_p, srn_f, **R10)
        C("C" + r(17), "0.47u 25V", "0402", srp_f, srn_f, serves=f"U{r(3)}.SRP", LCSC="C92361", MPN="CL05A474KA5NNNC")
        C("C" + r(18), "0.1u 50V", "0402", srp_f, gnd, serves=f"U{r(3)}.SRP", **C100N)
        C("C" + r(19), "0.1u 50V", "0402", srn_f, gnd, serves=f"U{r(3)}.SRN", **C100N)
        chg["SRP"] += srp_f; chg["SRN"] += srn_f
        kelvin(f"{name}/RBAT", "R" + r(27), srp_f, srn_f)

        section("Four-switch power stage. 0R gate resistors are tuning positions", "Power path left to right: input shunt and caps, input half bridge, L, output half bridge, output caps, battery shunt")
        fp_q = "MonolithDev:Vishay_PowerPAIR_3x3S"
        qf = dict(LCSC="C3289403", MPN="SiZ240DT-T1-GE3 (Vishay)")
        q1 = part("MonolithDev", "SiZ240DT", "Q" + r(1), "SiZ240DT", fp_q, **qf)     # VBUS-side half bridge
        q2 = part("MonolithDev", "SiZ240DT", "Q" + r(2), "SiZ240DT", fp_q, **qf)     # pack-side half bridge
        for q, top, sw, hi, lo, k in ((q1, ac_n, sw1, "HIDRV1", "LODRV1", 44), (q2, bat_p, sw2, "HIDRV2", "LODRV2", 46)):
            i = "1" if q is q1 else "2"
            hg, lg, hdrv, ldrv = net("HG" + i), net("LG" + i), net(hi), net(lo)
            q["D1"] += top; q["SW"] += sw; q["S2"] += gnd
            q["G1"] += hg; q["G2"] += lg
            chg[hi] += hdrv; chg[lo] += ldrv
            R("R" + r(k), "0R", "0402", hdrv, hg, **R0)
            R("R" + r(k + 1), "0R", "0402", ldrv, lg, **R0)
        ind = part("Device", "L", "L" + r(1), "3.3u", "MonolithDev:L_Coilank_APS0730", MPN="XGL7030-332MEC (Coilcraft)")
        ind[1] += sw1; ind[2] += sw2
        btst1, btst2 = net("BTST1"), net("BTST2")
        chg["BTST1"] += btst1; chg["BTST2"] += btst2
        C("C" + r(12), "0.1u 50V", "0402", btst1, sw1, serves=f"U{r(3)}.BTST1", **C100N)
        C("C" + r(13), "0.1u 50V", "0402", btst2, sw2, serves=f"U{r(3)}.BTST2", **C100N)
        for ref, k_net in (("D" + r(4), btst1), ("D" + r(5), btst2)):       # external bootstrap diodes from DRV_SUP
            d = part("Device", "D_Schottky", ref, "LRB520S-40T1G", "Diode_SMD:D_SOD-523", **SCHOTTKY)
            d["A"] += drv_sup; d["K"] += k_net

        # bridge decoupling. The first ceramic on each side closes the hot loop.
        for k in (20, 23, 24, 27):
            C("C" + r(k), "22u 35V", "1210", ac_n, gnd, serves=f"Q{r(1)}.D1", **C22U35)
        C("C" + r(30), "0.1u 50V", "0402", ac_n, gnd, serves=f"Q{r(1)}.D1", **C100N)
        for k in (21, 56):
            C("C" + r(k), "68u 35V", "Capacitor_Tantalum_SMD:CP_EIA-7343-31_Kemet-D", ac_n, gnd, lib=("Device", "C_Polarized"),
              MPN="KEMET T593V686M035APE070 (polymer tantalum)")
        for k in (31, 34):
            C("C" + r(k), "22u 35V", "1210", bat_p, gnd, serves=f"Q{r(2)}.D1", **C22U35)
        C("C" + r(38), "0.1u 50V", "0402", bat_p, gnd, serves=f"Q{r(2)}.D1", **C100N)
        draw_as("bridge4", "Q" + r(1), q_out="Q" + r(2), inductor="L" + r(1), rin="R" + r(24), rout="R" + r(27),
                cin=["C" + r(k) for k in (30, 20, 23, 24, 27, 21, 56)], cout=["C" + r(k) for k in (38, 31, 34)])
        hot_loop(f"{name}/HL_IN", ac_n, gnd, [f"Q{r(1)}.D1", f"Q{r(1)}.S2"], ["C" + r(30), "C" + r(20), "C" + r(23)])
        hot_loop(f"{name}/HL_OUT", bat_p, gnd, [f"Q{r(2)}.D1", f"Q{r(2)}.S2"], ["C" + r(38), "C" + r(31), "C" + r(34)])
        C("C" + r(44), "22u 35V", "1210", pack_p, gnd, **C22U35)
        C("C" + r(46), "0.1u 50V", "0402", pack_p, gnd, **C100N)

        section("Charger programming: input window, frequency, current limits, battery feedback, thermistor")
        acuv, acov = net("ACUV"), net("ACOV")
        R("R" + r(9), "137k 1%", "0402", pphv, acuv, LCSC="C32298", MPN="0402WGF1373TCE")
        R("R" + r(10), "40.2k 1%", "0402", acuv, acov, LCSC="C25893", MPN="0402WGF4022TCE")
        R("R" + r(11), "10k 1%", "0402", acov, gnd, LCSC="C25744", MPN="0402WGF1002TCE")
        chg["ACUV"] += acuv; chg["ACOV"] += acov
        fsw, ilim, ichg = net("FSW"), net("ILIM"), net("ICHG")
        R("R" + r(12), "49.9k 1%", R0201, fsw, gnd, MPN="0201WMF4992TEE")
        R("R" + r(13), "11.8k 1%", "0402", ichg, gnd, LCSC="C93752", MPN="0402WGF1182TCE")
        R("R" + r(14), "3.6k 1%", "0402", ilim, gnd, LCSC="C25891", MPN="0402WGF3601TCE")
        chg["FSW_SYNC"] += fsw; chg["ICHG"] += ichg; chg["ILIM_HIZ"] += ilim
        fb, fbg = net("FB"), net("FBG")
        R("R" + r(18), "100k 0.1%", "0402", pack_p, fb, LCSC="C445619", MPN="ERA2AEB104X")
        R("R" + r(19), "10.0k 0.1%", "0402", fb, fbg, LCSC="C191915", MPN="ERA2AEB103X")
        chg["FB"] += fb; chg["FBG"] += fbg
        declare(fb, kind="sensitive")
        ts = declare(net("TS"), kind="sensitive")
        R("R" + r(15), "1.8k 1%", "0402", regn, ts, LCSC="C25871", MPN="0402WGF1801TCE")
        R("R" + r(16), "5.6k 1%", "0402", ts, gnd, LCSC="C25908", MPN="0402WGF5601TCE")
        th = part("Device", "Thermistor_NTC", "TH" + r(1), "10k B3435", "Resistor_SMD:R_0402_1005Metric",
                  LCSC="C77131", MPN="NCP15XH103F03RC")
        th[1] += ts; th[2] += gnd
        chg["TS"] += ts
        ce_n = net("CE_N")                      # charge enable, active low: pulled up, MCU can force it high
        R("R" + r(17), "47k", R0201, ce_n, v3v3, LCSC="C270345", MPN="0201WMF4702TEE")
        R("R" + r(35), "1k", R0201, chg_inh, ce_n, LCSC="C270365", MPN="0201WMF1001TEE")
        chg["~{CE}"] += ce_n
        C("C" + r(10), "4.7u 10V", "0402", regn, gnd, serves=f"U{r(3)}.REGN", LCSC="C23733", MPN="CL05A475MP5NRNC")
        C("C" + r(11), "4.7u 25V", "0805", drv_sup, gnd, serves=f"U{r(3)}.DRV_SUP", LCSC="C1779", MPN="CL21A475KAQNNNE")

        section("9 V gate-drive supply, diode-ORed with REGN", "TPS7A41 makes the 9 V driver rail from PACK_P; D diode-ORs it with REGN")
        ldo = part("MonolithDev", "TPS7A4101", "U" + r(6), "TPS7A4101DGNR",
                   "Package_SO:HVSSOP-8-1EP_3x3mm_P0.65mm_EP1.57x1.89mm", LCSC="C111739", MPN="TPS7A4101DGNR (TI)")
        v9, v9_fb, v9_en = net("V9_DRV"), net("V9_FB"), net("V9_EN")
        ldo["IN"] += pack_p; ldo["OUT"] += v9; ldo["FB"] += v9_fb; ldo["EN"] += v9_en
        ldo["GND"] += gnd; ldo["NC"] += NC
        C("C" + r(57), "1u 50V", "0603", pack_p, gnd, serves=f"U{r(6)}.IN", LCSC="C15849", MPN="CL10A105KB8NNNC")
        C("C" + r(58), "22u 25V", "0805", v9, gnd, serves=f"U{r(6)}.OUT", LCSC="C45783", MPN="CL21A226MAQNNNE")
        R("R" + r(52), "40.2k 1%", "0402", v9, v9_fb, LCSC="C25893", MPN="0402WGF4022TCE")
        R("R" + r(53), "5.6k 1%", "0402", v9_fb, gnd, LCSC="C25908", MPN="0402WGF5601TCE")
        for ref, a in (("D" + r(10), regn), ("D" + r(11), v9)):
            d = part("Device", "D_Schottky", ref, "LRB520S-40T1G", "Diode_SMD:D_SOD-523", **SCHOTTKY)
            d["A"] += a; d["K"] += drv_sup
        q9 = part("Transistor_FET", "Q_NMOS_GSD", "Q" + r(9), "AO3400A", "Package_TO_SOT_SMD:SOT-23",
                  LCSC="C20917", MPN="AO3400A (AOS)")              # PD controller GPIO6 high turns the 9 V LDO off
        q9["G"] += drv9_off; q9["S"] += gnd; q9["D"] += v9_en
        R("R" + r(54), "100k", R0201, v9_en, regn, serves=f"U{r(6)}.EN", **R100K)
        R("R" + r(55), "100k", R0201, ldo_3v3, drv9_off, **R100K)

        section("5 V buck for PP5V (TPS62933)", "PACK_P in on the left, PP5V out on the right; R433/R434 set the output voltage")
        buck = part("Regulator_Switching", "TPS62933", "U" + r(4), "TPS62933DRLR", "Package_TO_SOT_SMD:SOT-583-8",
                    LCSC="C3200405", MPN="TPS62933DRLR")
        sw5 = declare(net("SW_5V"), kind="switching", swing_v=17, edge_ns=5)
        bst5, ss5, fb5 = net("BST_5V"), net("SS_5V"), net("FB_5V")
        buck["VIN"] += pack_p; buck["EN"] += en_5v; buck["GND", "RT"] += gnd
        buck["SW"] += sw5; buck["BST"] += bst5; buck["SS"] += ss5; buck["FB"] += fb5
        l5 = part("Device", "L", "L" + r(2), "3.3u", "MonolithDev:L_COILMX_MS0520", LCSC="C49248023", MPN="EHE05023R3MFB (ABC)")
        l5[1] += sw5; l5[2] += pp5v
        C("C" + r(40), "0.1u 50V", "0402", bst5, sw5, serves=f"U{r(4)}.BST", **C100N)
        C("C" + r(39), "33n 50V", "0402", ss5, gnd, serves=f"U{r(4)}.SS", LCSC="C7419416", MPN="FCC0402B333K500AT")
        for k in (41, 42, 43):
            C("C" + r(k), "22u 25V", "1206", pp5v, gnd, serves=f"L{r(2)}.2", LCSC="C12891", MPN="CL31A226KAHNNNE")
        R("R" + r(33), "120k", "0402", pp5v, fb5, LCSC="C25750", MPN="0402WGF1203TCE")
        R("R" + r(34), "22k", "0402", fb5, gnd, LCSC="C25768", MPN="0402WGF2202TCE")
        R("R" + r(32), "100k", R0201, en_5v, gnd, **R100K)
        hot_loop(f"{name}/HL_5V", pack_p, gnd, [f"U{r(4)}.VIN", f"U{r(4)}.GND"], ["C" + r(46), "C" + r(44)])
        draw_as("buck", "U" + r(4), vin="VIN", sw="SW", fb="FB", div=["R" + r(33), "R" + r(34)], bst="BST", boot="C" + r(40),
                inductor="L" + r(2), cin=["C" + r(46), "C" + r(44), "C" + r(57)], cout=["C" + r(k) for k in (41, 42, 43, 7)])

        # ---- intent: the highest voltage each net can reach, and what the programming parts are meant to set ----
        N = lambda *names: [CIRCUIT["nets"][f"{name}/{s}"] for s in names]
        volts(22, pphv, *N("C_CC1", "C_CC2", "VBIAS", "AC_SNS_N", "ACP_F", "ACN_F", "SW1"))
        across(0.1, "C" + r(14))             # filter cap across the input sense resistor: sees the sense voltage only
        volts(16.8, *N("BAT_SNS_P", "SRP_F", "SRN_F", "SW2", "SW_5V"))
        volts(32, *N("BTST1", "HG1", "HIDRV1")); volts(26.8, *N("BTST2", "HG2", "HIDRV2")); volts(22.3, *N("BST_5V"))
        volts(10, *N("DRV_SUP", "V9_DRV", "LG1", "LG2", "LODRV1", "LODRV2"))
        volts(5.5, pp5v, *N("CC1", "CC2", "DPDN_DCP", "REGN", "TS", "V9_EN", "SS_5V"))
        volts(3.6, ldo_3v3, en_5v, *N("I2CC_SDA", "I2CC_SCL", "CHG_INT", "SBU_FLT", "DRV9_OFF", "CE_N"))
        volts(6, *N("ACUV")); volts(2.5, *N("FSW", "ILIM", "ICHG")); volts(1.65, *N("LDO_1V5", "FB"))
        volts(1.3, *N("ACOV", "V9_FB")); volts(0.9, *N("FB_5V")); volts(0.1, *N("FBG"))
        chgk, chg_, d3 = "BQ25756.", "U" + r(3), dict(R1="R" + r(9), R2="R" + r(10), R3="R" + r(11))
        expect("PP5V", "VREF * (1 + Rtop / Rbot)", 5.15, 0.03, "V", at="U" + r(4) + ".FB", VREF="TPS62933.VREF", Rtop="R" + r(33), Rbot="R" + r(34))
        expect("battery regulation", "VFB * (1 + Rtop / (Rbot + RFBG))", 16.8, 0.01, "V", at=chg_ + ".FB", VFB=chgk + "VFB_NOM", RFBG=chgk + "RFBG", Rtop="R" + r(18), Rbot="R" + r(19))
        expect("input undervoltage", "VREF * (R1 + R2 + R3) / (R2 + R3)", 4.1, 0.05, "V", at=chg_ + ".ACUV", VREF=chgk + "VREF_ACUV", **d3)
        expect("input overvoltage", "VREF * (R1 + R2 + R3) / R3", 22.5, 0.05, "V", at=chg_ + ".ACOV", VREF=chgk + "VREF_ACOV", **d3)
        expect("charge current limit", "K * 0.005 / Rsns / (Rset / 1e3)", 4.2, 0.05, "A", at=chg_ + ".ICHG", K=chgk + "KICHG", Rsns="R" + r(27), Rset="R" + r(13))
        expect("input current limit", "K * 0.002 / Rsns / (Rset / 1e3)", 5.5, 0.05, "A", at=chg_ + ".ILIM_HIZ", K=chgk + "KILIM", Rsns="R" + r(24), Rset="R" + r(14))
        expect("gate-drive supply", "VREF * (1 + Rtop / Rbot)", 9.6, 0.03, "V", at="U" + r(6) + ".FB", VREF="TPS7A4101.VREF", Rtop="R" + r(52), Rbot="R" + r(53))
        expect("switching frequency", "(1 / Rset + 5e-6) / 5e-11 / 1e3", 500, 0.05, "kHz", at=chg_ + ".FSW_SYNC", Rset="R" + r(12))

        tp = part("Connector", "TestPoint", "TP" + r(12), "GND", "TestPoint:TestPoint_Pad_D1.0mm",
                  MPN="RH-S2761-46R (ronghe; Harwin S2761-46R equivalent)")
        tp[1] += gnd
