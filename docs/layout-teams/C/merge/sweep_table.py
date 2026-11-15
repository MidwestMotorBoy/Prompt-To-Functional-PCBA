#!/usr/bin/env python3
"""sweep_table.py OUT1 [OUT2 ...] > table.md: one markdown table over msweep folders: every placement made, legality,
planner prediction, screen (and full scorecard where run). Numbers come from score.json only."""
import json, os, sys
sys.path.insert(0, "/home/claude/repo/docs/layout-teams/C/sweep"); import sweep
KN = ("PDW_B", "PD_RIN_W2", "PD_BOX2", "PD_BUCK1", "NOISE", "SIDE_POST")
L = ["| tag | folder | knobs (besides HOOKS, SEED) | legal | planner-predicted opens | screen extra power_open | DRC | blocked | loss W | B parts | hot loops | full route |",
     "|---|---|---|---|---|---|---|---|---|---|---|---|"]
for O in sys.argv[1:]:
    disc = dict(l.rstrip("\n").split("\t", 1) for l in open(f"{O}/discarded.txt") if "\t" in l)
    for t in sweep.runs(O):
        rj = sweep.jload(f"{O}/runs/{t}/run.json", {}); px = sweep.jload(f"{O}/runs/{t}/proxies.json", {}) or {}
        env = rj.get("env", {}); kn = " ".join(f"{k}={env[k]}" for k in KN if k in env)
        if "cside" in env.get("HOOKS", ""): kn += " +cside"
        po = px.get("plan_open"); pred = "-" if po == {} else (" ".join(f"{n}@{'+'.join(r)}" for n, r in po.items()) if po else "not run")
        s = sweep.jload(f"{O}/runs/{t}/screen/score.json"); f = sweep.jload(f"{O}/runs/{t}/full/score.json")
        h = sweep.jload(f"{O}/runs/{t}/hot/score.json")
        hot = (f or {}).get("hot_loops") or (h or {}).get("hot_loops") or "not run"
        if s:
            bl, bt = sweep.bcount(s)
            row = [" ".join(sweep.extra_open(s)) or "-", str(s.get("drc_errors")), f"{bl} of {bt}", str(s.get("loss_W"))]
        else: row = ["not screened", "", "", ""]
        L.append(f"| {t} | {os.path.basename(O)} | {kn} | {disc.get(t, 'yes')} | {pred} | " + " | ".join(row) + f" | {px.get('n_flipped', 0)} | {hot} | {(f or {}).get('route', 'not run')} |")
print("\n".join(L))
