"""run_seeds.py <clusters.json> <board dump.json> <intent.json> <out dir> <first seed> <count> [parallel, default = cores - 2] [extra place_pack args...]
Runs place_pack.py for a range of seeds side by side (each run is one core for about half an hour on Monolith), then
prints one line per seed: half-perimeter, crossings, intent statements that hold, and every overlap or off-board part
that the hand placement in the dump does not already have. A seed with nothing in that last column is legal."""
import sys, os, subprocess, json, time
here = os.path.dirname(os.path.abspath(__file__)); cl, dump, intent, out, s0, n = sys.argv[1:7]; s0, n = int(s0), int(n)
par = int(sys.argv[7]) if len(sys.argv) > 7 else max(1, (os.cpu_count() or 4) - 2); extra = sys.argv[8:]
os.makedirs(out, exist_ok=True); todo = list(range(s0, s0 + n)); run = {}
py = lambda *a: subprocess.run([sys.executable, *a], capture_output=True, text=True, cwd=here).stdout
while todo or run:
    while todo and len(run) < par:
        s = todo.pop(0); log = open(os.path.join(out, f"seed{s}.log"), "w")
        run[s] = subprocess.Popen([sys.executable, os.path.join(here, "place_pack.py"), cl, dump, os.path.join(out, f"seed{s}.json"), "100000", str(s), "2500000", intent, *extra], stdout=log, stderr=subprocess.STDOUT, cwd=here)
    time.sleep(5)
    for s in [s for s, p in run.items() if p.poll() is not None]: del run[s]; print(f"seed {s} finished", flush=True)
base = set(py("overlaps.py", dump).splitlines()); rows = []
for s in range(s0, s0 + n):
    f = os.path.join(out, f"seed{s}.json")
    if not os.path.exists(f): rows.append(dict(seed=s, failed=True)); continue
    bad = [l for l in py("overlaps.py", dump, f).splitlines() if l not in base and not l.startswith("total")]
    x = json.loads(py("crossings.py", dump, f)); st = py("intent.py", "check", intent, dump, f).strip().splitlines()[-1]
    last = json.loads(open(os.path.join(out, f"seed{s}.log")).read().strip().splitlines()[-1])
    rows.append(dict(seed=s, half_perimeter_mm=last.get("signal_half_perimeter_mm"), crossings=x["crossings"], statements=st.split(" statements")[0], problems=bad))
json.dump(rows, open(os.path.join(out, "summary.json"), "w"), indent=1)
for r in rows: print(json.dumps(r))
