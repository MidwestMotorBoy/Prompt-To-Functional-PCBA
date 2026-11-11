"""Shared PACK_P bus: both chargers' battery-side banks, both TPS62933 input banks and the pack, as one network.

Extends DevBoard/tools/cap_sims.py (same part models, waveforms and pack model). Nodes: P1 and P2 are each port's
local bank at its FETs / buck input; H is the shared bulk position between the two power stages, where the pack bus
also lands. P1-H and P2-H are copper links (R + jwL). Each converter injects its switched current at its own port
node; currents from different converters are not synchronised, so per-capacitor RMS adds in quadrature and rail
ripple adds peak-to-peak (worst phase).

Checks per bank option:
  * C_eff on the bus (worst case at 16.8 V) >= 80 uF: BQ25756 sec. 5.3 C_OUT minimum after derating, per converter;
    each converter sees the whole bus through the links.
  * per-capacitor ripple current against its rating, worst over the operating cases;
  * ripple at P1 and P2;
  * input-filter damping (Middlebrook) at P1: bus + pack |Zout| against V^2/P of 100 W total from the pack.
Run: "C:/Program Files/KiCad/10.0/bin/python.exe" -I hardware/Production/tools/pack_bus_sims.py
"""
import importlib.util
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("cap_sims", os.path.join(HERE, "..", "..", "DevBoard", "tools", "cap_sims.py"))
cs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cs)

S, I10, HYB = "CL31A226 22u 25V 1206", "CL31A106 10u 50V 1206", "EEH-ZA1E101 100u 25V hybrid"
cs.PARTS[HYB]["area"] = 66.7  # CP_Elec_6.3x7.7 courtyard in the production footprint
HF = cs.HF                    # C438/C538 0.1 uF at the battery-side FETs; C446/C546 0.1 uF at the buck VIN

# option: (per-port local bank, shared bank at H)
OPTIONS = {
    "A0 now: per port 2x22u + hybrid + 2x10u50V": ([(S, 2), (HYB, 1), (I10, 2)], []),
    "A1: per port 2x22u + 2x10u50V, one shared hybrid": ([(S, 2), (I10, 2)], [(HYB, 1)]),
    "A2: per port 2x22u + 1x10u50V, one shared hybrid": ([(S, 2), (I10, 1)], [(HYB, 1)]),
    "A3: per port 1x22u + 1x10u50V, one shared hybrid": ([(S, 1), (I10, 1)], [(HYB, 1)]),
    "A4: per port 2x22u + 2x10u50V, no hybrid": ([(S, 2), (I10, 2)], []),
    "A5: per port 3x22u + 1x10u50V, no hybrid": ([(S, 3), (I10, 1)], []),
}
LINK = (0.007, 8e-9)          # P-H: RBAT 5 mOhm + 2 mOhm copper, 8 nH (power stages back to back, bulk between them)
VBATS = (10.0, 12.0, 16.8)


def zpart(part, v, w):
    p = cs.PARTS[part]
    return p["esr"] + 1j * w * p["esl"] + 1 / (1j * w * cs.c_eff(part, v))


def zhf(w):
    return HF["esr"] + 1j * w * HF["esl"] + 1 / (1j * w * HF["c"])


def network(opt, v, w, zpack):
    """3x3 nodal admittance (P1, P2, H) at angular frequency w, plus each element's (node, part, n, z)."""
    local, shared = OPTIONS[opt]
    Y = np.zeros((3, 3), complex)
    elems = []
    for node in (0, 1):
        y = 2 / zhf(w)  # the charger HF cap + the buck VIN 0.1 uF
        for part, n in local:
            z = zpart(part, v, w)
            y += n / z
            elems.append((node, part, n, z))
        Y[node, node] += y
    for part, n in shared:
        z = zpart(part, v, w)
        Y[2, 2] += n / z
        elems.append((2, part, n, z))
    Y[2, 2] += 1 / zpack(w)
    yl = 1 / (LINK[0] + 1j * w * LINK[1])
    for node in (0, 1):
        Y[node, node] += yl
        Y[2, 2] += yl
        Y[node, 2] -= yl
        Y[2, node] -= yl
    return Y, elems


def respond(opt, v, i_sw, fsw, node, zpack):
    """One converter's switched current at `node`: per-part RMS (dict) and p-p ripple at P1, P2."""
    X = np.fft.rfft(i_sw - i_sw.mean()) / cs.N * 2
    k = np.arange(len(X))
    keep = (k >= 1) & (k <= cs.KMAX)
    V = np.zeros((3, len(X)), complex)
    rms2 = {}
    for kk in np.nonzero(keep)[0]:
        w = 2 * np.pi * fsw * kk
        Y, elems = network(opt, v, w, zpack)
        inj = np.zeros(3, complex)
        inj[node] = X[kk]
        Vn = np.linalg.solve(Y, inj)
        V[:, kk] = Vn
        for nd, part, n, z in elems:
            key = (nd, part)
            rms2[key] = rms2.get(key, 0.0) + abs(Vn[nd] / z) ** 2 / 2
    ripple = []
    for nd in (0, 1):
        vt = np.fft.irfft(V[nd] / 2 * cs.N, n=cs.N)
        ripple.append(float(vt.max() - vt.min()))
    return rms2, ripple


def charger(direction, usb_v, usb_i, vbat):
    """Battery-side switched current of one BQ25756."""
    if direction == "fwd":
        p_out = min(usb_v * usb_i * cs.ETA, vbat * cs.ICHG)
        vin, vout = usb_v, vbat
    else:
        p_out = usb_v * usb_i
        vin, vout = vbat, usb_v
    mode = "buck" if vin >= vout else "boost"
    i_in, i_out, *_ = cs.waveform(mode, vin, vout, p_out, cs.L1, cs.FSW)
    return (i_out if direction == "fwd" else i_in), p_out / cs.ETA if direction == "rev" else -p_out


def buck5(vbat):
    i_in, *_ = cs.waveform("buck", vbat, cs.V5, cs.V5 * 3, cs.L5, cs.FSW5)
    return i_in, cs.V5 * 3 / 0.9


# operating cases: list of (node, source) with source = ("chg", dir, usb_v, usb_i) or ("buck",)
CASES = {
    "port 1 reverse 20 V 5 A": [(0, ("chg", "rev", 20, 5))],
    "port 1 forward 9 V 3 A (boost)": [(0, ("chg", "fwd", 9, 3))],
    "port 1 forward 20 V 3 A": [(0, ("chg", "fwd", 20, 3))],
    "both reverse: 20 V 4 A + 9 V 2.22 A": [(0, ("chg", "rev", 20, 4)), (1, ("chg", "rev", 9, 2.22))],
    "pass-through: 1 fwd 20 V 3 A, 2 rev 20 V 2 A": [(0, ("chg", "fwd", 20, 3)), (1, ("chg", "rev", 20, 2))],
    "port 1 reverse 20 V 4 A + port 2 5 V 3 A (buck)": [(0, ("chg", "rev", 20, 4)), (1, ("buck",))],
    "both 5 V 3 A (bucks)": [(0, ("buck",)), (1, ("buck",))],
}


def run_case(opt, case, vbat, zpack):
    rms2, rip = {}, [0.0, 0.0]
    for node, src in CASES[case]:
        if src[0] == "chg":
            i_sw, _ = charger(src[1], src[2], src[3], vbat)
            if src[1] == "fwd" and src[2] < vbat:
                pass
            r, rp = respond(opt, vbat, i_sw, cs.FSW, node, zpack)
        else:
            i_sw, _ = buck5(vbat)
            r, rp = respond(opt, vbat, i_sw, cs.FSW5, node, zpack)
        for kk, vv in r.items():
            rms2[kk] = rms2.get(kk, 0.0) + vv
        rip = [a + b for a, b in zip(rip, rp)]
    return {k: float(np.sqrt(v)) for k, v in rms2.items()}, rip


def damping(opt, zpacks):
    f = np.logspace(3, 6.3, 500)
    worst = (99.0, 0, 0, None)
    for vbat in VBATS:
        for zp in zpacks:
            zo = []
            for fr in f:
                Y, _ = network(opt, vbat, 2 * np.pi * fr, zp)
                zo.append(abs(np.linalg.inv(Y)[0, 0]))
            zo = np.array(zo)
            zin = vbat * vbat / (100 / cs.ETA)
            k = int(np.argmax(zo))
            m = 20 * np.log10(zin / zo[k])
            if m < worst[0]:
                worst = (m, f[k], zo[k], vbat)
    return worst


def main():
    zpacks = [cs.ext_pack(0.1e-6, 0.05), cs.ext_pack(0.3e-6, 0.05), cs.ext_pack(0.5e-6, 0.085)]
    for opt, (local, shared) in OPTIONS.items():
        ceff = 2 * cs.bank_c(local, 16.8) + cs.bank_c(shared, 16.8)
        area = 2 * sum(n * cs.PARTS[p]["area"] for p, n in local) + sum(n * cs.PARTS[p]["area"] for p, n in shared)
        worst_part, worst_rip = (0, "", ""), (0, "")
        for case in CASES:
            for vbat in VBATS:
                for zp in zpacks[:2]:
                    rms, rip = run_case(opt, case, vbat, zp)
                    for (nd, part), i in rms.items():
                        ratio = i / cs.PARTS[part]["irms"]
                        if ratio > worst_part[0]:
                            worst_part = (ratio, "%s at %s (%.2f A)" % (part.split()[0] + (" P%d" % (nd + 1) if nd < 2 else " H"), case, i), vbat)
                    if max(rip) > worst_rip[0]:
                        worst_rip = (max(rip), "%s, pack %.1f V" % (case, vbat))
        m, fpk, zpk, vb = damping(opt, zpacks)
        print("%-52s Ceff %5.1f uF %s  area %5.1f mm2  worst part %4.0f%% %s pack %.1f V" % (
            opt, ceff * 1e6, "OK " if ceff >= 80e-6 else "LOW", area, worst_part[0] * 100, worst_part[1], worst_part[2]))
        print("%52s ripple %4.0f mV (%s)   damping %4.1f dB at %.0f kHz (pack %.1f V)" % (
            "", worst_rip[0] * 1e3, worst_rip[1], m, fpk / 1e3, vb))


if __name__ == "__main__":
    main()
