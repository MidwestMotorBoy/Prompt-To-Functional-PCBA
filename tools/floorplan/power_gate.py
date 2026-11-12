"""power_gate.py <constraints.json> <netlist.json> <limits dir> <limitsmap.json> <hot_score result.json> [reference hot_score result.json]
Tier 1 (pass or fail) and tier 2 (a number to push down) for every hot loop of a placement, from the loop
inductances hot_score.py computed on its rule-made copper. Exit code 1 when a tier-1 limit fails.

Tier 1, the board would not work or the part is over its rating:
  closed     the first capacitor of the loop (the first one the circuit code lists) closes its loop on the stage's
             own copper (thousands of nH = no path). A bulk capacitor the rule copper does not reach is reported
             as a note, not a failure: routing will connect it, and what it then adds is a tier-2 matter.
  overshoot  supply voltage plus the turn-off spike stays under the absolute maximum of the switch.
             Spike, two estimates, the limit is taken from the first that has its data:
               ring   I * sqrt(L / Coss)   all loop energy rings into the switch's output capacitance, no damping.
                                           Upper bound. Used when the limits file has COSS_PF (discrete FETs).
               edge   L * I / t            current commutates in half the edge time the circuit code declares
                                           for the switch node. Used for converters with built-in switches,
                                           whose datasheets give no Coss.
             I is the part's own current limit (IHS_LIMIT_MAX) when the limits file has it, else 1.3 times the
             current the circuit code declares for the supply net. L is the board loop with all capacitors and
             their package inductance in parallel, plus PKG_NH for the switch package.
Tier 2, lower is better, no threshold: total loop inductance, the first capacitor's loop, the ring frequency,
and each against the reference placement when one is given.
Numbers come from the circuit code (voltages, currents, edge times) and the limits files (page and quote there)."""
import sys, json, math, os
cons, netl, ldir, lmap, hotf = sys.argv[1:6]; reff = sys.argv[6] if len(sys.argv) > 6 else None
C = json.load(open(cons)); comps = json.load(open(netl))["comps"]; M = json.load(open(lmap)); H = json.load(open(hotf)); R = json.load(open(reff)) if reff else {}
PKG_NH = 0.2          # assumed: switch package, source and drain bond or clip (not in the datasheets used here)
OPEN_NH = 100.0       # a per-capacitor loop above this has no path on the stage copper
EDGE_FACTOR = 0.5     # the edge estimate uses half the declared edge time
nets = {k.lstrip("/"): v for k, v in C["nets"].items()}
def limits(ref):
    f = os.path.join(ldir, M.get(comps[ref]["lib"], "") + ".json"); return json.load(open(f)) if os.path.isfile(f) else {}
def fact(L, k, scale=1.0):
    f = L.get("facts", {}).get(k)
    if not f: return None
    return f["value"] * (1e-3 if f.get("unit", "").startswith("mA") else 1.0) * scale
rows = []; fail = 0
for name, hl in sorted(C["hot_loops"].items()):
    if name not in H: continue
    h = H[name]; dev, pin = hl["switch_pins"][0].split("."); L = limits(dev); why = []
    opened = [c for c, v in h["per_cap_nH"].items() if v > OPEN_NH]
    note = ""
    if hl["caps"][0] in opened: why.append("no closed loop through the first capacitor " + hl["caps"][0])
    elif opened: note = "bulk not reached by the rule copper: " + ", ".join(opened)
    vin = nets.get(hl["supply"], {}).get("max_v"); spins = [t.split(".")[1] for t in hl["switch_pins"]]
    vabs = fact(L, "SW_TRANSIENT_MAX") or next((a["max_v"] for a in L.get("abs_max", []) if set(a["pins"]) & set(spins)), None)
    i_pk = fact(L, "IHS_LIMIT_MAX") or 1.3 * nets.get(hl["supply"], {}).get("current_a", 0)
    coss = fact(L, "COSS_PF", 1e-12); swn = [n for n, v in nets.items() if v.get("kind") == "switching" and n.startswith(name.rsplit("/", 1)[0] if "/" in name else "") and v.get("edge_ns")]
    row = dict(loop=name, switch=dev, first_cap_nH=round(h["per_cap_nH"][hl["caps"][0]], 2) if hl["caps"][0] in h["per_cap_nH"] and hl["caps"][0] not in opened else None, tier1="pass")
    if len(opened) < len(h["per_cap_nH"]) and h["all_parallel_with_esl_nH"] < OPEN_NH:
        Lt = (h["all_parallel_with_esl_nH"] + PKG_NH) * 1e-9; row["loop_total_nH"] = round(Lt * 1e9, 2)
        if vin is None or vabs is None or not i_pk: why.append("no rating, supply voltage or current to check the spike against")
        else:
            if coss: spike = i_pk * math.sqrt(Lt / coss); lmax = coss * ((vabs - vin) / i_pk) ** 2; row["method"] = "ring"; row["ring_MHz"] = round(1e-6 / (2 * math.pi * math.sqrt(Lt * coss)))
            else:
                t = EDGE_FACTOR * 1e-9 * min([nets[n]["edge_ns"] for n in swn] or [5]); spike = Lt * i_pk / t; lmax = (vabs - vin) * t / i_pk; row["method"] = "edge"
            row.update(supply_V=vin, abs_max_V=vabs, peak_A=round(i_pk, 2), spike_V=round(spike, 1), peak_V=round(vin + spike, 1), limit_total_nH=round(lmax * 1e9, 2))
            if vin + spike > vabs: why.append(f"spike reaches {vin + spike:.1f} V, rating {vabs:g} V")
    if R.get(name) and "loop_total_nH" in row: row["reference_total_nH"] = round(R[name]["all_parallel_with_esl_nH"] + PKG_NH, 2)
    if why: row["tier1"] = "FAIL: " + "; ".join(why); fail += 1
    elif note: row["tier1"] = "pass (" + note + ")"
    rows.append(row)
print("| Hot loop | Switch | Tier 1 | Loop total, nH | Tier-1 limit, nH | Peak at switch / rating, V | First capacitor, nH | Reference total, nH |\n|---|---|---|---|---|---|---|---|")
g = lambda r, k: "" if r.get(k) is None else r[k]
for r in rows: print(f"| {r['loop']} | {r['switch']} | {r['tier1']} | {g(r, 'loop_total_nH')} | {g(r, 'limit_total_nH')} ({g(r, 'method')}) | {g(r, 'peak_V')} / {g(r, 'abs_max_V')} | {g(r, 'first_cap_nH')} | {g(r, 'reference_total_nH')} |")
tot = sum(r.get("loop_total_nH", 0) for r in rows)
print(f"\n{len(rows) - fail} of {len(rows)} hot loops pass tier 1; tier-2 score (sum of loop totals that close): {tot:.2f} nH")
json.dump(rows, open(os.path.splitext(hotf)[0] + "_gate.json", "w"), indent=1)
sys.exit(1 if fail else 0)
