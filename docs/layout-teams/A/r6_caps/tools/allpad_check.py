#!/usr/bin/env python3
"""allpad_check.py <board.kicad_pcb> <cu_dump.json> <constraints.json> [out.json] [--nets=regex]
Team A r6_caps: stricter routed-board power check than pad_join_check.py. For every power and return net (roles.py),
the main piece is chosen as in pad_join_check (most terminal parts); then EVERY pad of the net (terminal or not, single
pad parts included) that is not on the main piece is listed, with the piece it sits on (layers, area, vias), plus the
KiCad-independent piece count per net. Allowed findings: r4_vbus/allow.json style file via --allow."""
import sys, json, re
sys.path.insert(0, '/home/claude/repo/tools/copper'); sys.path.insert(0, '/home/claude/repo/docs/layout-teams/A/r4_vbus/tools')
from roles import Design
from dc_score import load_copper
from pad_join_check import net_pieces

def main():
    a = [x for x in sys.argv[1:] if not x.startswith("--")]; opt = dict(x[2:].split("=", 1) for x in sys.argv[1:] if x.startswith("--"))
    D = Design(a[1], a[2]); Z, S, V = load_copper(a[0]); layers = D.D["layers"]
    allow = json.load(open(opt["allow"])) if opt.get("allow") else {}
    rx = re.compile(opt.get("nets", ".*"))
    res = {"off_main": {}, "off_main_not_allowed": {}, "pieces_with_pads": {}}
    for net in sorted(D.power) + sorted(D.ret):
        if not rx.search(net): continue
        T = D.terminals(net)
        if not T: continue
        pad_comps, pieces, f = net_pieces(D, Z, S, V, net, layers, 0.001)
        comp_of = {p["key"]: pad_comps(p) for p in D.pads if p["net"] == net}
        ser = sorted([g for g in T if g["kind"] == "series"] or T, key=lambda g: (-g["current_a"], -len(g["pads"]), g["ref"]))
        src = ser[0]["ref"]; score = {}
        for g in T:
            for p in g["pads"]:
                for c in comp_of[p["key"]]: score.setdefault(c, set()).add(g["ref"])
        if not score: continue
        main = max(score, key=lambda c: (len(score[c]), src in score[c]))
        off = sorted(k for k, cs in comp_of.items() if main not in cs)
        groups = {}
        for k, cs in comp_of.items():
            for c in cs or {None}: groups.setdefault(str(c), []).append(k)
        res["pieces_with_pads"][net] = len(groups)
        if off:
            res["off_main"][net] = off
            al = [x for kk, v in allow.items() if kk in net for x in v]
            bad = [k for k in off if k not in al and k.split(".")[0] not in al]
            if bad: res["off_main_not_allowed"][net] = bad
    n = sum(len(v) for v in res["off_main_not_allowed"].values())
    res["summary"] = f"{n} pads off main (not allowed): " + "; ".join(f"{k}: {','.join(v)}" for k, v in res["off_main_not_allowed"].items())
    if len(a) > 3: json.dump(res, open(a[3], "w"), indent=1)
    print("SUMMARY", res["summary"])

main()
