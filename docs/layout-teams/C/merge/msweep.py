#!/usr/bin/env python3
"""msweep.py: team C merged-placer sweep driver (place -> legality gate -> planner opens -> scorecard screen, 2 lanes).

  msweep.py OUT GRID.json [--seeds m=1-10,ms=1-6,...] [--screen N|all] [--lanes 2] [--jobs 2] [--skip-plan]

GRID.json is {config name: {env knobs}} as for sweep.py (HOOKS per config). Steps, all cached in OUT (re-run skips
what is done; built on ../sweep/sweep.py, which does the per-run bookkeeping):
  1. place   every (config, seed) with cplace/run.sh, 2 placer processes at a time (sweep.py place)
  2. legal   discard placements with new courtyard / keep-out / off-board overlaps against the base placement
             (sweep.py proxies: new_overlap_mm2 > 0.05, side-aware) and byte-identical duplicates -> OUT/legal.txt
  3. plan    host copper planner (no KiCad, about 75 s each) on every legal placement, in `lanes` parallel lanes:
             predicted non-GND power opens (matched the scorecard on 8 of 8 boards, sweep/README.md)
  4. screen  scorecard --route=0 --no-hot (cplace/cscore.sh) on the legal placements, best predicted first, in
             `lanes` lanes (each lane its own lock file; never more than `lanes` scorecards at once)
  5. table   OUT/table.md / table.csv / contact.png (sweep.py table), and OUT/msweep.md (this driver's ranking:
             extra power opens, DRC errors, then blocked edges, then loss)
"""
import argparse, json, os, subprocess, sys, time, re
H = os.path.dirname(os.path.abspath(__file__)); SW = os.path.normpath(os.path.join(H, "..", "sweep"))
SWP = [sys.executable, os.path.join(SW, "sweep.py")]


def run(args, env=None, log=None):
    print("[msweep]", " ".join(args[2:]), flush=True)
    return subprocess.run(SWP + args, env=env, stdout=open(log, "a") if log else None, stderr=subprocess.STDOUT if log else None).returncode


def lanes(O, kind, tags, n, extra):
    """run sweep.py <kind> --tags ... in n parallel lanes, each with its own scorecard lock"""
    groups = [tags[i::n] for i in range(n)]; ps = []
    for i, g in enumerate(groups):
        if not g: continue
        env = dict(os.environ, SWEEP_LOCK=f"{O}/.lock{i}", SWEEP_LOAD_MAX=os.environ.get("SWEEP_LOAD_MAX", "6"))
        lg = f"{O}/{kind}_lane{i}.log"
        ps.append(subprocess.Popen(SWP + [kind, O, "--tags", ",".join(g)] + extra, env=env, stdout=open(lg, "a"), stderr=subprocess.STDOUT))
        print(f"[msweep] {kind} lane {i}: {len(g)} placements, log {lg}", flush=True)
        time.sleep(20)                                    # stagger the docker starts
    for p in ps: p.wait()


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("out"); ap.add_argument("grid")
    ap.add_argument("--seeds", default="", help="per config, e.g. m=1-10,ms=1-6 (default 1-4 for each)")
    ap.add_argument("--screen", default="all"); ap.add_argument("--lanes", type=int, default=2); ap.add_argument("--skip-plan", action="store_true")
    ap.add_argument("--jobs", default="2", help="placer processes at once")
    a = ap.parse_args(); O = os.path.abspath(a.out); os.makedirs(O, exist_ok=True)
    G = json.load(open(a.grid)); S = dict(x.split("=") for x in a.seeds.split(",") if x)
    # 1. place, one config at a time (each its own seed list)
    for name, kn in G.items():
        gf = f"{O}/grid_{name}.json"; json.dump({name: kn}, open(gf, "w"))
        run(["place", O, "--grid", gf, "--seeds", S.get(name, "1-4"), "--jobs", a.jobs, "--load-max", "6"], log=f"{O}/place.log")
    # 2. legality gate
    legal, bad = [], []
    seen = {}
    import hashlib
    for t in sorted(os.listdir(f"{O}/runs")):
        px = json.load(open(f"{O}/runs/{t}/proxies.json")) if os.path.exists(f"{O}/runs/{t}/proxies.json") else None
        if px is None: bad.append((t, "no placement")); continue
        h = hashlib.md5(open(f"{O}/runs/{t}/p.json", "rb").read()).hexdigest()
        if h in seen: bad.append((t, f"duplicate of {seen[h]}")); continue
        seen[h] = t
        if px.get("new_overlap_mm2", 0) > 0.05: bad.append((t, f"overlap {px['new_overlap_mm2']} mm2 {px.get('new_overlaps', '')}")); continue
        legal.append(t)
    open(f"{O}/legal.txt", "w").write("\n".join(legal) + "\n")
    open(f"{O}/discarded.txt", "w").write("\n".join(f"{t}\t{w}" for t, w in bad) + "\n")
    print(f"[msweep] legal {len(legal)}, discarded {len(bad)}: {bad}", flush=True)
    # 3. plan
    if not a.skip_plan:
        todo = [t for t in legal if not os.path.exists(f"{O}/runs/{t}/plan/plan.json")]
        lanes(O, "plan", todo, a.lanes, [])
    # 4. screen: best predicted first
    def key(t):
        px = json.load(open(f"{O}/runs/{t}/proxies.json"))
        return (px.get("plan_n_open", 99), px.get("power_IxL", 0))
    order = sorted(legal, key=key)
    pick = order if a.screen == "all" else order[:int(a.screen)]
    todo = [t for t in pick if not os.path.exists(f"{O}/runs/{t}/screen/score.json")]
    lanes(O, "screen", todo, a.lanes, [])
    # 5. tables
    run(["table", O]); write_rank(O)
    print("DONE-MSWEEP", flush=True)


def write_rank(O):
    """the ranking asked for: hard limits (extra power opens empty, DRC 0), then blocked edges, then loss"""
    sys.path.insert(0, SW); import sweep
    rows = []
    for t in sorted(os.listdir(f"{O}/runs")):
        s = sweep.jload(f"{O}/runs/{t}/screen/score.json")
        if not s: continue
        rj = sweep.jload(f"{O}/runs/{t}/run.json", {}); px = sweep.jload(f"{O}/runs/{t}/proxies.json", {})
        ex = sweep.extra_open(s); bl, bt = sweep.bcount(s)
        rows.append(dict(tag=t, ex=ex, drc=s.get("drc_errors"), bl=bl, bt=bt, loss=s.get("loss_W"), plan=px.get("plan_open"),
                         nB=px.get("n_flipped", 0), env={k: v for k, v in rj.get("env", {}).items() if k not in ("HOOKS",)}, hooks=rj.get("env", {}).get("HOOKS")))
    rows.sort(key=lambda r: (len(r["ex"]) > 0, r["drc"] != 0, len(r["ex"]), r["bl"] if r["bl"] is not None else 9999, r["loss"] or 99))
    L = ["| # | tag | hooks | extra power_open | DRC | blocked | loss W | parts on B |", "|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(rows):
        L.append(f"| {i+1} | {r['tag']} | {r['hooks']} | {' '.join(r['ex']) or '-'} | {r['drc']} | {r['bl']} of {r['bt']} | {r['loss']} | {r['nB']} |")
    open(f"{O}/msweep.md", "w").write("\n".join(L) + "\n"); print("\n".join(L))


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "rank": write_rank(os.path.abspath(sys.argv[2]))
    else: main()
