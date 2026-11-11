"""Low-profile bulk study (2026-10-18): replace the 6.3x7.7 mm cans (C421/C521 polymer, C208 hybrid) with parts no
taller than the inductors (APS0730M2R2F, 3.1 mm max).

USB side (AC_SNS_N, per port): unpowered in sleep, so leakage does not matter; 35 V polymer tantalum CCTC
CA55-D035M476T (47 uF, 150 mOhm, 1.225 A rms, 7343-28, 2.8 mm) next to GMK325 22u 35V 1210s; from 2026-10-31 KEMET
T593V686M035APE070 (68 uF, 70 mOhm, 7343-20, 2.0 mm), option C4. Not MnO2 tantalum
(CA45-D035K336T: 900 mOhm, fails short and can ignite, wants >= 50 % voltage derating on a low-impedance input).
PACK_P (shared bus): always live, so only MLCCs. Polymer aluminium chips (SP-Cap, CDE MPD) and polymer tantalum
are rated 0.1-0.3 CV of leakage (hundreds of uA), against a ~150 uA sleep budget. GMK325BJ226MM 22u 35V 1210
(2.7 mm max) keeps ~10 uF at 16.8 V, more than a TMK325 47u 25V (~8 uF). Applied: C4 (USB, was C2) and N1 (PACK_P).

Reuses DevBoard/tools/cap_sims.py (USB side: ripple, RMS, cable damping) and pack_bus_sims.py (shared bus).
Run: "C:/Program Files/KiCad/10.0/bin/python.exe" -I hardware/Production/tools/low_profile_sims.py
"""
import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("pack_bus_sims", os.path.join(HERE, "pack_bus_sims.py"))
pb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pb)
cs = pb.cs

TA = "T521D336 33u 35V polymer Ta"
cs.PARTS[TA] = dict(c0=33e-6, esr=0.065, esl=2.0e-9, irms=2.2, area=42.3, kind="poly")
C55 = "CA55-D035M476T 47u 35V polymer Ta"
cs.PARTS[C55] = dict(c0=47e-6, esr=0.150, esl=2.0e-9, irms=1.225, area=42.3, kind="poly")
T593 = "T593V686M035APE070 68u 35V polymer Ta"   # 2026-10-31: 7343-20, 2.0 mm max; 1.69 A rms is the 85 C figure (2.42 A at 45 C)
cs.PARTS[T593] = dict(c0=68e-6, esr=0.070, esl=2.0e-9, irms=1.694, area=42.3, kind="poly")
CA45 = "CA45-D035K336T 33u 35V MnO2 Ta"
cs.PARTS[CA45] = dict(c0=33e-6, esr=0.9, esl=2.0e-9, irms=0.342, area=42.3, kind="poly")
G, T, POLY = "GMK325 22u 35V 1210", "TMK325 47u 25V 1210", "HV1V107 100u 35V polymer"
S, I10, HYB = pb.S, pb.I10, pb.HYB
cs.PARTS[POLY]["area"] = 66.7  # production CP_Elec_6.3x7.7 courtyard

cs.BANKS["usb"] = {
    "U0 now: 4x 22u 1210 + 100u can (7.7 mm)": [(G, 4), (POLY, 1)],
    "L1: 4x 22u 1210 + 2x 33u T521D": [(G, 4), (TA, 2)],
    "L2: 5x 22u 1210 + 2x 33u T521D": [(G, 5), (TA, 2)],
    "L3: 4x 22u 1210 + 3x 33u T521D": [(G, 4), (TA, 3)],
    "L4: 6x 22u 1210 + 2x 33u T521D": [(G, 6), (TA, 2)],
    "L3c: 4x 22u 1210 + 3x 33u CA45 (MnO2)": [(G, 4), (CA45, 3)],
    "C2 was applied: 4x 22u 1210 + 2x 47u CA55": [(G, 4), (C55, 2)],
    "C3: 4x 22u 1210 + 3x 47u CA55": [(G, 4), (C55, 3)],
    "C4 applied: 4x 22u 1210 + 2x 68u T593V": [(G, 4), (T593, 2)],
}
cs.BANKS["bat"] = {}

pb.OPTIONS.clear()
pb.OPTIONS.update({
    "A2 now: 2x22u+1x10u per port, hybrid can at H": ([(S, 2), (I10, 1)], [(HYB, 1)]),
    "M1: 2x22u+1x10u per port, 7x 47u 1210 at H": ([(S, 2), (I10, 1)], [(T, 7)]),
    "M2: 2x47u+1x10u per port, 5x 47u 1210 at H": ([(T, 2), (I10, 1)], [(T, 5)]),
    "M3: 3x47u per port, 5x 47u 1210 at H": ([(T, 3)], [(T, 5)]),
    "M4: 2x47u+1x10u per port, 6x 47u 1210 at H": ([(T, 2), (I10, 1)], [(T, 6)]),
})


def main():
    print("== USB side, per port (BQ25756 C_IN >= 80 uF after derating, at 20 V)")
    cs.main()
    print("\n== Shared PACK_P bus (>= 80 uF at 16.8 V)")
    pb.main()


if __name__ == "__main__":
    main()
