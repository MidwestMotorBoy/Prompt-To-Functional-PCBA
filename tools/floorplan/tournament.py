"""tournament.py <build dir> <limits dir> <limitsmap.json> <clusters.json> <board dump.json> <intent.json> <board.kicad_pcb> <work dir> <first seed> <count> [parallel]
Placement tournament, power first:
  1. run_seeds.py places every seed and keeps the buildable ones (no overlap, on the board, off the keep-outs);
  2. each buildable seed gets the rule-made power copper (stage_copper.py) and its hot loops are solved
     (hot_score.py) and gated (power_gate.py): tier 1 pass or fail, tier 2 the sum of loop inductances;
  3. seeds are ranked: tier 1 pass first, then lowest tier-2 sum, then fewest signal crossings. Sums within
     5 % of the best passing seed count as equal (the loop solver does not resolve less), so crossings decide there.
<build dir> holds the circuit build's constraints.json and netlist.json; <board.kicad_pcb> is any board with the
design's footprints (its copper is stripped). Results: <work dir>/tournament.json and a table.

KiCad's python is needed for two steps. Set KICAD_PYTHON to the command that runs it with the work dir as the
current directory, for example
  KICAD_PYTHON="docker run --rm -u 0 -v <work dir>:/w -w /w kicad/kicad:10.0 python3"      (Linux, Docker)
  KICAD_PYTHON="C:/Program Files/KiCad/10.0/bin/python.exe"                                 (Windows)
The winner still has to pass the trial route (apply_placement.py --strip, open_connections.py, the router)."""
import sys, os, json, shutil, shlex, subprocess, time
a = sys.argv[1:]; build, ldir, lmap, cl, dump, intent, board, work = a[:8]; s0, n = int(a[8]), int(a[9]); par = int(a[10]) if len(a) > 10 else max(1, (os.cpu_count() or 4) - 1)
here = os.path.dirname(os.path.abspath(__file__)); kpy = shlex.split(os.environ.get("KICAD_PYTHON", "")) or sys.exit("set KICAD_PYTHON (see the top of this file)")
work = os.path.abspath(work); os.makedirs(work, exist_ok=True); cons = os.path.join(build, "constraints.json"); netl = os.path.join(build, "netlist.json")
subprocess.run([sys.executable, os.path.join(here, "run_seeds.py"), cl, dump, intent, os.path.join(work, "seeds"), str(s0), str(n), str(par)], check=True, stdout=subprocess.DEVNULL)
rows = json.load(open(os.path.join(work, "seeds", "summary.json"))); ok = [r for r in rows if not r.get("failed") and not r["problems"]]
print(f"{len(ok)} of {len(rows)} seeds buildable", flush=True)
for f in ("apply_placement.py", "stage_copper.py"): shutil.copy(os.path.join(here, f), work)
shutil.copy(board, os.path.join(work, "in.kicad_pcb")); shutil.copy(cons, os.path.join(work, "constraints.json")); pro = os.path.splitext(board)[0] + ".kicad_pro"
def copper(r):      # KiCad steps, one seed at a time (they are quick)
    s = r["seed"]; shutil.copy(os.path.join(work, "seeds", f"seed{s}.json"), os.path.join(work, f"seed{s}.json"))
    for t in (f"seed{s}_bare.kicad_pro", f"seed{s}_cu.kicad_pro"):
        if os.path.exists(pro): shutil.copy(pro, os.path.join(work, t))
    for cmd in (["apply_placement.py", "in.kicad_pcb", f"seed{s}_bare.kicad_pcb", f"seed{s}.json", "--strip"], ["stage_copper.py", f"seed{s}_bare.kicad_pcb", "constraints.json", f"seed{s}_cu.kicad_pcb"]):
        p = subprocess.run(kpy + cmd, cwd=work, capture_output=True, text=True)
        if p.returncode: r["copper_error"] = (p.stdout + p.stderr).strip().splitlines()[-1:]; return False
    return True
todo = [r for r in ok if copper(r)]; run = {}
while todo or run:      # loop solves side by side; each uses a core or two and up to a few GB
    while todo and len(run) < max(1, par // 2):
        r = todo.pop(0); s = r["seed"]
        run[s] = (r, subprocess.Popen([sys.executable, os.path.join(here, "hot_score.py"), cons, os.path.join(work, f"seed{s}_hot.json")], env=dict(os.environ, PCB=os.path.join(work, f"seed{s}_cu.kicad_pcb")), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    time.sleep(5)
    for s in [s for s, (_, p) in run.items() if p.poll() is not None]:
        r, p = run.pop(s); hot = os.path.join(work, f"seed{s}_hot.json")
        if p.returncode or not os.path.exists(hot): r["loop_error"] = f"hot_score.py ended with code {p.returncode}"; continue
        g = subprocess.run([sys.executable, os.path.join(here, "power_gate.py"), cons, netl, ldir, lmap, hot], capture_output=True, text=True)
        gate = json.load(open(os.path.join(work, f"seed{s}_hot_gate.json")))
        r["tier1_pass"] = sum(1 for q in gate if q["tier1"].startswith("pass")); r["tier1_of"] = len(gate); r["tier1_fail"] = [f"{q['loop']}: {q['tier1']}" for q in gate if not q["tier1"].startswith("pass")]
        r["tier2_sum_nH"] = round(sum(q.get("loop_total_nH", 0) for q in gate), 2); r["notes"] = [f"{q['loop']}: {q['tier1']}" for q in gate if q["tier1"].startswith("pass (")]
        print(f"seed {s}: {r['tier1_pass']} of {r['tier1_of']} hot loops pass, tier-2 sum {r['tier2_sum_nH']} nH", flush=True)
full = lambda r: not r.get("problems") and not r.get("failed") and "tier1_of" in r and r["tier1_pass"] == r["tier1_of"]
tie = 1.05 * min([r["tier2_sum_nH"] for r in rows if full(r)] or [0])
key = lambda r: (bool(r["problems"]) or r.get("failed", False), not full(r), 0 if full(r) and r["tier2_sum_nH"] <= tie else r.get("tier2_sum_nH", 1e9), r.get("crossings", 1e9))
rows.sort(key=key); json.dump(rows, open(os.path.join(work, "tournament.json"), "w"), indent=1)
print("\n| Rank | Seed | Buildable | Hot loops passing tier 1 | Tier-2 sum, nH | Crossings | Signal half-perimeter, mm | Why not |\n|---|---|---|---|---|---|---|---|")
for i, r in enumerate(rows):
    why = "; ".join((r.get("problems") or [])[:2] + r.get("tier1_fail", [])[:2] + r.get("copper_error", []) + ([r["loop_error"]] if "loop_error" in r else []))
    print(f"| {i + 1} | {r['seed']} | {'yes' if not r.get('problems') and not r.get('failed') else 'no'} | {r.get('tier1_pass', '')}{' of ' + str(r['tier1_of']) if 'tier1_of' in r else ''} | {r.get('tier2_sum_nH', '')} | {r.get('crossings', '')} | {r.get('half_perimeter_mm', '')} | {why} |")
best = rows[0] if rows and full(rows[0]) else None
print(f"\nwinner: seed {best['seed']} ({os.path.join(work, 'seeds', 'seed' + str(best['seed']) + '.json')})" if best else "\nno seed is buildable and passes tier 1")
