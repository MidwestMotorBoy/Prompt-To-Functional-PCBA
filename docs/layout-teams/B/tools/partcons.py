"""partcons.py <constraints.json> <placement.json> <out constraints_part.json> [refs_out.json]
Constraints filtered to the parts present on a partial board (fixed parts + the placement's refs):
hot loops whose switch or any capacitor is missing are dropped; draw entries whose chip is missing are dropped and
their lists cut to the parts present (a missing single ref field is dropped); kelvin, serves, heat, pin_pads,
across and near_mm entries that name a missing part are dropped. Writes the present refs to refs_out.json."""
import sys, json, re, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from blib import Board

def main(cf, pf, of, rf=None):
    B = Board(); C = json.load(open(cf)); P = {r for r in json.load(open(pf)) if not r.startswith("_")}
    have = P | B.fixed; isref = lambda s: isinstance(s, str) and re.fullmatch(r"[A-Z]+\d+", s)
    dropped = []
    hl = {}
    for k, v in C.get("hot_loops", {}).items():
        refs = {t.split(".")[0] for t in v["switch_pins"]} | set(v["caps"])
        if refs <= have: hl[k] = v
        else: dropped.append(f"hot loop {k}")
    C["hot_loops"] = hl
    dr = {}
    for k, v in C.get("draw", {}).items():
        if k not in have: dropped.append(f"draw {k}"); continue
        o = {}
        for f, x in v.items():
            if isinstance(x, list): o[f] = [y for y in x if not isref(y) or y in have]
            elif isref(x) and x not in have: continue
            else: o[f] = x
        dr[k] = o
    C["draw"] = dr
    C["kelvin"] = {k: v for k, v in C.get("kelvin", {}).items() if v.get("resistor") in have}
    C["serves"] = {k: v for k, v in C.get("serves", {}).items() if k in have and v.split(".")[0] in have}
    C["heat"] = {k: v for k, v in C.get("heat", {}).items() if k in have}
    C["pin_pads"] = {k: v for k, v in C.get("pin_pads", {}).items() if k.split(".")[0] in have}
    for key in ("across", "near_mm"):
        if isinstance(C.get(key), dict): C[key] = {k: v for k, v in C[key].items() if not isref(k) or k in have}
    if "copper" in C and "terminals" in C["copper"]:
        C["copper"]["terminals"] = {n: [t for t in ts if t.split(".")[0] in have] for n, ts in C["copper"]["terminals"].items()}
    json.dump(C, open(of, "w"), indent=1)
    if rf: json.dump(sorted(P), open(rf, "w"))
    print(f"{of}: {len(have)} parts present ({len(P)} placed), hot loops kept {sorted(hl)}, dropped: {dropped}")

if __name__ == "__main__":
    main(*sys.argv[1:])
