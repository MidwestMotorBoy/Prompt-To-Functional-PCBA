#!/usr/bin/env python3
"""sweep.py: seed/knob sweep and screening harness for team C's constructive placer (cplace).

Subcommands (OUT = sweep folder, e.g. /home/claude/work/C/sweep/base; every result is cached there, a re-run skips
what is done, so any command can be killed and started again):

  place   OUT --seeds 1-12 [--grid grid.json] [--set NAME:K=V,K=V ...] [--hooks cpower,cside,ccorr] [--jobs 2]
          Runs cplace/run.sh once per (config, seed) into OUT/runs/<config>_s<seed>/ (p.json, place.log, run.json
          with the full environment and file hashes), then computes the proxies. A config is a set of env knobs
          (STEP, NOISE, PASSES, BOXW, ...; HOOKS may be set per config too). Default config: "base" = no knobs.
  proxies OUT [--force]           cheap proxies (no KiCad, about 1 s per placement) -> OUT/runs/*/proxies.json
  rank    OUT                     hard gates + weighted rank over all placements -> OUT/rank.csv, OUT/rank.md
  screen  OUT --top K | --spread K | --tags T1,T2 [--opts="--route=0 --no-hot"]
          scorecard runs (cplace/cscore.sh) ONE AT A TIME into OUT/runs/<tag>/screen/, then table + contact sheet.
          --top K = best K passing the gates; --spread K = K placements spread evenly over the rank (calibration).
  full    OUT --tag T [--route=45] [--bg]   full scorecard (hot loops + route) into OUT/runs/<tag>/full/
          --bg detaches (nohup) and writes OUT/runs/<tag>/full.log, ending with a line DONE.
  table   OUT                     OUT/table.csv, OUT/table.md, OUT/contact.png (all screened / full results)
  calib   OUT                     Spearman rank correlation of each proxy with the screen's blocked edges and
                                  extra power opens -> OUT/calib.md

Every heavy step (placer batch, each scorecard run) waits until the 1-minute load average is at or below
--load-max (default 3.0, env SWEEP_LOAD_MAX) and holds a container-wide lock file for scorecard runs
(/home/claude/work/C/sweep/.score.lock), so two sweeps never run two scorecards at once.
"""
import argparse, csv, fcntl, hashlib, json, math, os, re, signal, subprocess, sys, time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
CPLACE = os.path.normpath(os.path.join(HERE, "..", "cplace"))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
IN = os.environ.get("SWEEP_IN", "/home/claude/work/C/in")
LOCK = os.environ.get("SWEEP_LOCK", "/home/claude/work/C/sweep/.score.lock")
HAND_SCREEN = "/home/claude/work/C/hand_screen"
KNOBS = ["SEED", "HOOKS", "STEP", "BOXW", "BOXM", "RING", "ROOM_X", "BIG_PADS", "NEARW", "ROOMW", "CENTW", "SECW", "INTERLEAVE",
         "SWAP", "SWAPD", "PASSES", "PWRW", "NOISE", "KEEP_MM", "KEEP_NETS", "MOVE_BIG"]
ALLOWED_OPEN = {"3V3": {"L201"}, "GND": {"J301", "J302"}}

def log(*a): print("[sweep]", *a, flush=True)
def md5(f):
    try: return hashlib.md5(open(f, "rb").read()).hexdigest()[:10]
    except OSError: return None
def jload(f, default=None):
    try: return json.load(open(f))
    except (OSError, ValueError): return default
def jsave(o, f):
    t = f + ".tmp"; json.dump(o, open(t, "w"), indent=1); os.replace(t, f)

def wait_load(lmax, extra=0.0, what="job"):
    t0 = time.time(); said = False
    while os.getloadavg()[0] > lmax + extra:
        if not said or time.time() - t0 > 300:
            log(f"load {os.getloadavg()[0]:.2f} > {lmax + extra:.1f}; waiting before {what}"); said = True; t0 = time.time()
        time.sleep(20)

# ----------------------------------------------------------------------------------------------- geometry (side-aware)
def rot(x, y, k):
    for _ in range(k % 4): x, y = -y, x
    return x, y

class Board:
    """the dump with a placement applied; handles the 4th element ("F"/"B": mirror local x before the turn)"""
    def __init__(self, d, P):
        self.d = d; fps = {f["ref"]: f for f in d["fps"]}; self.fps = fps
        self.pose = {}
        for r, f in fps.items():
            v = P.get(r)
            if v is None: self.pose[r] = (f["x"], f["y"], 0, False, f["side"]); continue
            s0 = f["side"][0]; s = v[3] if len(v) > 3 else s0
            self.pose[r] = (v[0], v[1], int(v[2]) // 90, s != s0, "F.Cu" if s == "F" else "B.Cu")
        self.pads = []
        for p in d["pads"]:
            r = p["ref"]; f = fps[r]; x, y, k, mir, side = self.pose[r]
            def tf(px, py):
                lx, ly = px - f["x"], py - f["y"]
                if mir: lx = -lx
                dx, dy = rot(lx, ly, k); return x + dx, y + dy
            cx, cy = tf(p["x"], p["y"]); a = tf(p["box"][0], p["box"][1]); b = tf(p["box"][2], p["box"][3])
            lay = p["layers"]
            if mir: lay = [{"F.Cu": "B.Cu", "B.Cu": "F.Cu"}.get(l, l) for l in lay]
            self.pads.append(dict(ref=r, num=p["num"], net=p["net"], x=cx, y=cy, layers=lay,
                                  box=(min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))))
        self.court = {}
        for r, f in fps.items():
            if "court" not in f: continue
            x, y, k, mir, side = self.pose[r]; c = f["court"]
            q = [(c[0] - f["x"], c[1] - f["y"]), (c[2] - f["x"], c[3] - f["y"])]
            if mir: q = [(-u, v) for u, v in q]
            q = [rot(u, v, k) for u, v in q]
            self.court[r] = (x + min(q[0][0], q[1][0]), y + min(q[0][1], q[1][1]), x + max(q[0][0], q[1][0]), y + max(q[0][1], q[1][1]), side)
        self.bynet = defaultdict(list); self.byref = defaultdict(list)
        for p in self.pads:
            if p["net"]: self.bynet[p["net"].lstrip("/")].append(p)
            self.byref[p["ref"]].append(p)

    def overlaps(self):
        """overlaps.py, side-aware: list of (text, mm2)"""
        B = self.court; out = []
        T = defaultdict(list)
        for p in self.pads:
            r = p["ref"]
            if r in B and ("*.Cu" in p["layers"] or ("B.Cu" if B[r][4] == "F.Cu" else "F.Cu") in p["layers"]): T[r].append(p["box"])
        rs = sorted(B)
        for a, boxes in sorted(T.items()):
            for b in rs:
                if b == a or B[b][4] == B[a][4]: continue
                for A in boxes:
                    ox = min(A[2], B[b][2]) - max(A[0], B[b][0]); oy = min(A[3], B[b][3]) - max(A[1], B[b][1])
                    if ox > 0.01 and oy > 0.01: out.append((f"far-side pad of {a} under {b}", ox * oy))
        for i, a in enumerate(rs):
            for b in rs[i + 1:]:
                A, C = B[a], B[b]
                if A[4] != C[4]: continue
                ox = min(A[2], C[2]) - max(A[0], C[0]); oy = min(A[3], C[3]) - max(A[1], C[1])
                if ox > 0.01 and oy > 0.01: out.append((f"overlap {a} / {b}", ox * oy))
        for k in self.d.get("keepouts", []):
            if not k.get("no_footprints"): continue
            for r, A in B.items():
                if A[4] in k["layers"]:
                    ox = min(A[2], k["box"][2]) - max(A[0], k["box"][0]); oy = min(A[3], k["box"][3]) - max(A[1], k["box"][1])
                    if ox > 0.01 and oy > 0.01: out.append((f"keep-out {k['name']}: {r}", ox * oy))
        bx = self.d["box"]
        for r, A in B.items():
            if A[0] < bx[0] or A[1] < bx[1] or A[2] > bx[2] or A[3] > bx[3]: out.append((f"off board: {r}", 1.0))     # counted as 1 mm2 in new_overlap_mm2 only
        return out

def mst(Q):
    """Prim over points Q -> list of (i, j, length)"""
    if len(Q) < 2: return []
    E = []; best = {j: (math.dist(Q[j], Q[0]), 0) for j in range(1, len(Q))}
    while best:
        j = min(best, key=lambda q: best[q][0]); dd, i = best.pop(j); E.append((i, j, dd))
        for q in best:
            dq = math.dist(Q[q], Q[j])
            if dq < best[q][0]: best[q] = (dq, j)
    return E

def crossings(E, box):
    """crossings.py count(), copied: E = [(net index, ax, ay, bx, by)]"""
    import numpy as np
    E = np.array(E); n, ax, ay, bx, by = E.T; o = lambda px, py, qx, qy, rx, ry: (qx - px) * (ry - py) - (qy - py) * (rx - px)
    A = lambda v: v[:, None]; B = lambda v: v[None, :]
    d1 = o(A(ax), A(ay), A(bx), A(by), B(ax), B(ay)); d2 = o(A(ax), A(ay), A(bx), A(by), B(bx), B(by))
    d3 = o(B(ax), B(ay), B(bx), B(by), A(ax), A(ay)); d4 = o(B(ax), B(ay), B(bx), B(by), A(bx), A(by))
    X = (d1 * d2 < 0) & (d3 * d4 < 0) & (A(n) != B(n)); i, j = np.nonzero(np.triu(X, 1))
    if len(i) == 0: return 0, 0
    t = d3[i, j] / (d3[i, j] - d4[i, j]); cx = ax[i] + t * (bx[i] - ax[i]); cy = ay[i] + t * (by[i] - ay[i])
    H, _, _ = np.histogram2d(cx, cy, bins=[np.arange(box[0], box[2] + 5, 5), np.arange(box[1], box[3] + 5, 5)])
    W = H[:-1, :-1] + H[1:, :-1] + H[:-1, 1:] + H[1:, 1:]
    return int(len(i)), int(W.max())

# ----------------------------------------------------------------------------------------------- proxies
ICS = ["U403", "U503", "U401", "U501", "U102", "U301"]
PIN_CLR = float(os.environ.get("SWEEP_PIN_CLR", 0.5))
PAIRS = [("U401", "J401"), ("U501", "J501"), ("U404", "U401"), ("U504", "U501")]   # PD chip-connector, 5 V buck-PD chip

def centroid(b, r):
    ps = b.byref[r]; return (sum(p["x"] for p in ps) / len(ps), sum(p["y"] for p in ps) / len(ps))

def proxies(d, P, cl, it, cons, base_ov=None):
    b = Board(d, P); out = {}
    # 1 legality: overlaps beyond the base placement's (fixed-part) list
    ov = b.overlaps(); out["overlap_mm2"] = round(sum(a for t, a in ov if not t.startswith("off board")), 2)   # = overlaps.py total
    if base_ov is not None:
        new = [(t, a) for t, a in ov if t not in base_ov]
        out["new_overlap_mm2"] = round(sum(a for _, a in new), 2); out["new_overlaps"] = [f"{t} {a:.2f}" for t, a in new][:20]
    out["n_flipped"] = sum(1 for r, v in P.items() if len(v) > 3 and v[3] != b.fps[r]["side"][0])
    # 2 signal half-perimeter and shortest trees (non-power nets: < 12 pads, >= 2 pads; same as metrics.py/crossings.py)
    power = {n for n, ps in b.bynet.items() if len(ps) >= 12}
    hp = 0.0; tree = 0.0; E = []
    for ni, (n, ps) in enumerate(sorted(b.bynet.items())):
        if n in power or len(ps) < 2: continue
        hp += max(p["x"] for p in ps) - min(p["x"] for p in ps) + max(p["y"] for p in ps) - min(p["y"] for p in ps)
        u = {}
        for p in ps: u.setdefault((p["ref"], p["num"]), (p["x"], p["y"]))
        Q = list(u.values())
        for i, j, dd in mst(Q): tree += dd; E.append((ni, *Q[i], *Q[j]))
    out["sig_hp_mm"] = round(hp); out["sig_tree_mm"] = round(tree)
    # 3 tree-edge crossings
    out["crossings"], out["worst_10mm_window"] = crossings(E, d["box"])
    # 4 intent: near statements (hot loop / power path / other), keep-apart
    pt = defaultdict(list); boxes = defaultdict(list)
    for p in b.pads: pt[f"{p['ref']}.{p['num']}"].append((p["x"], p["y"])); pt[p["ref"]].append((p["x"], p["y"])); boxes[p["ref"]].append(p["box"])
    edge = lambda bs, Bq: min(math.hypot(max(x[0] - q[0], 0, q[0] - x[2]), max(x[1] - q[1], 0, q[1] - x[3])) for x in bs for q in Bq)
    dist = lambda A, Bq: min(math.hypot(a[0] - q[0], a[1] - q[1]) for a in A for q in Bq)
    agg = {k: [0, 0.0] for k in ("hl", "pp", "near")}
    for s in it.get("near", []):
        A = pt.get(s["part"]); Bq = [q for t in s["to"] for q in pt.get(t, [])]
        if not A or not Bq: continue
        dd = dist(pt[s["pad"]], Bq) if s.get("pad") in pt else edge(boxes[s["part"]], Bq)
        k = "hl" if s["why"].startswith("hot loop") else "pp" if s["why"].startswith("power path") else "near"
        if dd > s["max_mm"]: agg[k][0] += 1; agg[k][1] += s.get("weight", 1) * (dd - s["max_mm"])
    for k, (n, e) in agg.items(): out[f"{k}_fail"] = n; out[f"{k}_excess"] = round(e, 1)
    ka = 0
    for s in it.get("keepapart", []):
        A = [(p["x"], p["y"], p["ref"]) for a in s["a_nets"] for p in b.bynet.get(a.lstrip("/"), [])]
        Bq = [(p["x"], p["y"], p["ref"]) for x in s["b_nets"] for p in b.bynet.get(x.lstrip("/"), [])]
        pr = [math.hypot(a[0] - q[0], a[1] - q[1]) for a in A for q in Bq if a[2] != q[2]]
        if pr and min(pr) < s["min_mm"]: ka += 1
    out["keepapart_fail"] = ka
    # 5 power compactness: sum over power nets of current x pad tree length
    pw = 0.0; per = {}
    for n, v in cons["nets"].items():
        if v.get("kind") != "power" or not v.get("current_a"): continue
        u = {}
        for p in b.bynet.get(n.lstrip("/"), []): u.setdefault((p["ref"], p["num"]), (p["x"], p["y"]))
        L = sum(dd for _, _, dd in mst(list(u.values()))); per[n] = round(L, 1); pw += v["current_a"] * L
    out["power_IxL"] = round(pw); out["power_tree_mm"] = per
    # 6 hot loops: first cap's supply/return pads to the switch's supply/return pads (centre to centre, mm)
    hl = {}
    for name, h in cons["hot_loops"].items():
        c = h["caps"][0]; sw = []
        for sp in h["switch_pins"]:
            r, _, pin = sp.partition("."); nums = cons["pin_pads"].get(sp, [pin])
            sw.append([(p["x"], p["y"]) for p in b.byref[r] if p["num"] in nums])
        cp = b.byref[c]
        cs = [(p["x"], p["y"]) for p in cp if p["net"].lstrip("/") == h["supply"]]; cr = [(p["x"], p["y"]) for p in cp if p["net"].lstrip("/") == h["ret"]]
        if not cs or not cr or not sw[0] or not sw[1]:          # net names did not match: best assignment of the two pads
            q = [(p["x"], p["y"]) for p in cp][:2]
            a1 = max(dist([q[0]], sw[0]), dist([q[1]], sw[1])); a2 = max(dist([q[1]], sw[0]), dist([q[0]], sw[1])); hl[name] = round(min(a1, a2), 2)
        else: hl[name] = round(max(dist(cs, sw[0]), dist(cr, sw[1])), 2)
    out["hl_mm"] = hl; out["hl_max"] = max(hl.values()); out["hl_sum"] = round(sum(hl.values()), 2)
    # 7 PD chip to connector, 5 V buck to PD chip (pad centroids), section sprawl
    for a, c in PAIRS: out[f"d_{a}_{c}"] = round(math.dist(centroid(b, a), centroid(b, c)), 1)
    spr = {}
    for sec, parts in cl.items():
        rs = [r for r in parts if r in b.court]
        if len(rs) < 3: continue
        bx = [min(b.court[r][0] for r in rs), min(b.court[r][1] for r in rs), max(b.court[r][2] for r in rs), max(b.court[r][3] for r in rs)]
        area = sum((b.court[r][2] - b.court[r][0]) * (b.court[r][3] - b.court[r][1]) for r in rs)
        spr[sec] = round((bx[2] - bx[0]) * (bx[3] - bx[1]) / max(area, 1e-6), 2)
    out["sprawl"] = spr
    # 8 crowding round the big chips (metrics.py: parts with a pad within 2.5 mm of the chip's pad box)
    crowd = {}
    for ic in ICS:
        mine = b.byref.get(ic)
        if not mine: continue
        Bx = [min(p["box"][0] for p in mine), min(p["box"][1] for p in mine), max(p["box"][2] for p in mine), max(p["box"][3] for p in mine)]
        s = set()
        for p in b.pads:
            if p["ref"] == ic: continue
            dx = max(Bx[0] - p["box"][2], p["box"][0] - Bx[2], 0); dy = max(Bx[1] - p["box"][3], p["box"][1] - Bx[3], 0)
            if dx * dx + dy * dy <= 6.25: s.add(p["ref"])
        crowd[ic] = len(s)
    out["crowd"] = crowd; out["crowd_sum"] = sum(crowd.values())
    # 9 power-pin crowding: pads on power nets (constraints kind power, + GND) whose box edge is within PIN_CLR mm of a pad
    #   of ANOTHER part on a different net (the copper planner then cannot get a pour onto the pin; base runs open there)
    pn = {n.lstrip("/") for n, v in cons["nets"].items() if v.get("kind") == "power"} | {"GND"}
    import numpy as np
    A = np.array([p["box"] for p in b.pads]); refs = np.array([p["ref"] for p in b.pads]); nets = np.array([p["net"].lstrip("/") for p in b.pads])
    sideF = np.array(["F.Cu" in p["layers"] or "*.Cu" in p["layers"] for p in b.pads]); sideB = np.array(["B.Cu" in p["layers"] or "*.Cu" in p["layers"] for p in b.pads])
    cr = 0; crn = defaultdict(int)
    for i, p in enumerate(b.pads):
        if p["net"].lstrip("/") not in pn: continue
        bx = p["box"]; dx = np.maximum(np.maximum(A[:, 0] - bx[2], bx[0] - A[:, 2]), 0); dy = np.maximum(np.maximum(A[:, 1] - bx[3], bx[1] - A[:, 3]), 0)
        same = (sideF & sideF[i]) | (sideB & sideB[i])
        m = (np.hypot(dx, dy) < PIN_CLR) & (refs != p["ref"]) & (nets != nets[i]) & same
        if m.any(): cr += 1; crn[f"{p['net'].lstrip('/')}@{p['ref']}"] += 1
    out["pwr_pin_crowd"] = cr; out["pwr_pin_crowd_at"] = dict(sorted(crn.items(), key=lambda kv: -kv[1])[:12])
    return out

def inputs():
    if not os.path.exists(f"{IN}/bodies.json"): subprocess.run([f"{CPLACE}/gen_inputs.sh", IN], check=True, stdout=subprocess.DEVNULL)
    return (jload(f"{IN}/dump.json"), jload(f"{IN}/clusters.json"), jload(f"{IN}/intent.json"), jload(f"{IN}/constraints.json"))

def hand_proxies(OUT, d, cl, it, cons):
    f = f"{OUT}/hand_proxies.json"; h = jload(f)
    if h is None: h = proxies(d, {}, cl, it, cons); h.update(sprawl_flags={}, sprawl_worst=1.0, new_overlap_mm2=0); jsave(h, f)
    return h

def base_overlaps(d):
    return {t for t, _ in Board(d, jload(f"{CPLACE}/base_seed2_placement.json")).overlaps()}

def finish_proxies(px, hand, sprawl_x):
    """sprawl vs hand: sections whose bounding-box/area ratio is over sprawl_x times the hand board's"""
    fl = {s: round(v / hand["sprawl"][s], 2) for s, v in px["sprawl"].items() if s in hand["sprawl"] and v > sprawl_x * hand["sprawl"][s]}
    px["sprawl_flags"] = fl; px["sprawl_worst"] = max([v / hand["sprawl"][s] for s, v in px["sprawl"].items() if s in hand["sprawl"]] or [0])
    px["sprawl_worst"] = round(px["sprawl_worst"], 2)
    return px

def cmd_proxies(a):
    d, cl, it, cons = inputs(); hand = hand_proxies(a.out, d, cl, it, cons); bov = None; n = 0
    for tag in runs(a.out):
        R = f"{a.out}/runs/{tag}"
        if not os.path.exists(f"{R}/p.json") or (os.path.exists(f"{R}/proxies.json") and not a.force): continue
        if bov is None: bov = base_overlaps(d)
        px = finish_proxies(proxies(d, jload(f"{R}/p.json"), cl, it, cons, bov), hand, a.sprawl_x); jsave(px, f"{R}/proxies.json"); n += 1
    log(f"proxies written for {n} placements")

def runs(OUT):
    D = f"{OUT}/runs"
    key = lambda t: [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", t)]
    return sorted(os.listdir(D), key=key) if os.path.isdir(D) else []

# ----------------------------------------------------------------------------------------------- place
def parse_seeds(s):
    out = []
    for part in s.split(","):
        if "-" in part: x, y = part.split("-"); out += list(range(int(x), int(y) + 1))
        elif part: out.append(int(part))
    return out

def configs(a):
    C = {}
    if a.grid:
        g = jload(a.grid)
        if isinstance(g, list): g = {f"c{i}": v for i, v in enumerate(g)}
        C.update(g)
    for s in a.set or []:
        name, _, kv = s.partition(":"); C[name] = dict(x.split("=", 1) for x in kv.split(",") if x)
    if not C: C = {"base": {}}
    for k, v in C.items():
        if not re.fullmatch(r"[A-Za-z0-9.+-]+", k): sys.exit(f"config name {k!r}: use letters, digits, . + - only")
    return C

def cmd_place(a):
    os.makedirs(f"{a.out}/runs", exist_ok=True); C = configs(a); todo = []
    for name, kn in C.items():
        for s in parse_seeds(a.seeds):
            tag = f"{name}_s{s}"; R = f"{a.out}/runs/{tag}"; rj = jload(f"{R}/run.json", {})
            if rj.get("rc") == 0 and os.path.exists(f"{R}/p.json"): continue
            env = {k: str(v) for k, v in kn.items()}; env.setdefault("HOOKS", a.hooks); env["SEED"] = str(s)
            todo.append((tag, name, env))
    log(f"{len(todo)} placements to run ({sum(len(parse_seeds(a.seeds)) for _ in C) - len(todo)} cached), {a.jobs} at a time")
    hashes = {f: md5(f"{CPLACE}/{f}") for f in sorted(os.listdir(CPLACE)) if f.endswith(".py")}
    git = subprocess.run(["git", "-C", REPO, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    running = {}
    while todo or running:
        while todo and len(running) < a.jobs:
            wait_load(a.load_max, extra=len(running), what="placer run")
            tag, name, env = todo.pop(0); R = f"{a.out}/runs/{tag}"; os.makedirs(R, exist_ok=True)
            for f in ("p.json", "proxies.json"):
                if os.path.exists(f"{R}/{f}"): os.remove(f"{R}/{f}")
            full = dict(os.environ); [full.pop(k, None) for k in KNOBS]; full.update(env)
            cmd = [f"{CPLACE}/run.sh", f"{R}/p.json", IN]
            rj = dict(tag=tag, config=name, env=env, cmd=" ".join(f"{k}={v}" for k, v in sorted(env.items())) + " " + " ".join(cmd),
                      cwd=CPLACE, git=git, cplace_files_md5=hashes, start=time.strftime("%Y-%m-%d %H:%M:%S"))
            jsave(rj, f"{R}/run.json")
            running[tag] = (subprocess.Popen(cmd, cwd=CPLACE, env=full, stdout=open(f"{R}/place.log", "w"), stderr=subprocess.STDOUT), time.time(), rj)
        time.sleep(2)
        for tag in [t for t, (p, _, _) in running.items() if p.poll() is not None or time.time() - running[t][1] > a.timeout]:
            p, t0, rj = running.pop(tag)
            if p.poll() is None: p.kill(); p.wait(); rj["timed_out"] = True
            rj["rc"] = p.returncode; rj["secs"] = round(time.time() - t0, 1)
            P = jload(f"{a.out}/runs/{tag}/p.json"); rj["n_parts"] = len(P) if P else 0
            if rj["rc"] != 0 or not P: rj["rc"] = rj["rc"] or 1
            jsave(rj, f"{a.out}/runs/{tag}/run.json"); log(f"{tag}: rc {rj['rc']}, {rj['secs']} s, {rj['n_parts']} parts")
    a.force = False; cmd_proxies(a); cmd_rank(a)

# ----------------------------------------------------------------------------------------------- rank
RANKW = dict(power_IxL=2.0, hl_sum=2.0, sig_tree_mm=1.0, crossings=1.0, near_excess=0.5, pp_excess=1.0)

def gates(px, hand, a):
    g = []
    if px.get("new_overlap_mm2", 0) > 0.05: g.append(f"overlap {px['new_overlap_mm2']} mm2")
    if px["hl_max"] > a.hl_max: g.append(f"hot-loop cap {px['hl_max']} mm > {a.hl_max}")
    for x, y in PAIRS[:2]:
        k = f"d_{x}_{y}"
        if px[k] > hand[k] + a.pd_slack: g.append(f"{x}-{y} {px[k]} mm (hand {hand[k]})")
    for x, y in PAIRS[2:]:
        k = f"d_{x}_{y}"
        if px[k] > hand[k] + a.buck_slack: g.append(f"{x}-{y} {px[k]} mm (hand {hand[k]})")
    return g

def ranked(a):
    d, cl, it, cons = inputs(); hand = hand_proxies(a.out, d, cl, it, cons); rows = []
    W = dict(RANKW); W.update({k: float(v) for k, v in (x.split("=") for x in (a.weights or "").split(",") if x)})
    seen = {}
    for tag in runs(a.out):
        px = jload(f"{a.out}/runs/{tag}/proxies.json")
        if not px: continue
        g = gates(px, hand, a); h = md5(f"{a.out}/runs/{tag}/p.json")       # identical placements (e.g. NOISE that does not change the order)
        if h in seen: g = [f"duplicate of {seen[h]}"] + g
        else: seen[h] = tag
        rows.append(dict(tag=tag, px=px, gates=g))
    for k in W:                                   # weighted sum of value / median over the placements
        vals = sorted(r["px"][k] for r in rows); med = vals[len(vals) // 2] if vals else 1
        for r in rows: r.setdefault("score", 0.0); r["score"] += W[k] * r["px"][k] / (med or 1)
    anyplan = any(r["px"].get("plan_n_open") is not None for r in rows)   # after 'plan': unplanned rows go below planned ones
    rows.sort(key=lambda r: (bool(r["gates"]), r["px"].get("plan_n_open", 99 if anyplan else 0), r["score"]))
    for i, r in enumerate(rows): r["rank"] = i + 1
    return rows, hand

PCOLS = ["new_overlap_mm2", "n_flipped", "sig_hp_mm", "sig_tree_mm", "crossings", "near_fail", "near_excess", "pp_fail", "pp_excess", "hl_fail",
         "keepapart_fail", "power_IxL", "hl_max", "hl_sum", "d_U401_J401", "d_U501_J501", "d_U404_U401", "d_U504_U501", "sprawl_worst", "crowd_sum", "pwr_pin_crowd", "plan_n_open"]

def cmd_rank(a):
    rows, hand = ranked(a)
    with open(f"{a.out}/rank.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["rank", "tag", "score", "gates"] + PCOLS)
        w.writerow(["-", "hand", "", ""] + [hand.get(k, "") for k in PCOLS])
        for r in rows: w.writerow([r["rank"], r["tag"], round(r["score"], 3), "; ".join(r["gates"])] + [r["px"].get(k, "") for k in PCOLS])
    sh = ["rank", "tag", "score", "gates", "sig_tree_mm", "crossings", "power_IxL", "hl_max", "hl_sum", "pp_excess", "d_U401_J401", "d_U501_J501", "d_U404_U401", "d_U504_U501", "sprawl_worst"]
    L = ["| " + " | ".join(sh) + " |", "|" + "---|" * len(sh)]
    L.append("| - | hand | | | " + " | ".join(str(hand[k]) for k in sh[4:]) + " |")
    for r in rows: L.append("| " + " | ".join([str(r["rank"]), r["tag"], f"{r['score']:.3f}", "; ".join(r["gates"]) or "pass"] + [str(r["px"][k]) for k in sh[4:]]) + " |")
    open(f"{a.out}/rank.md", "w").write("\n".join(L) + "\n"); print("\n".join(L[:40]))

# ----------------------------------------------------------------------------------------------- scorecard
def scorecard(a, tag, kind, opts):
    R = f"{a.out}/runs/{tag}"; O = f"{R}/{kind}"
    if os.path.exists(f"{O}/score.json"): log(f"{tag}/{kind}: cached"); return jload(f"{O}/score.json")
    os.makedirs(os.path.dirname(LOCK), exist_ok=True); lk = open(LOCK, "w")
    log(f"{tag}/{kind}: waiting for the scorecard lock"); fcntl.flock(lk, fcntl.LOCK_EX)
    try:
        wait_load(a.load_max, what=f"scorecard {tag}/{kind}")
        log(f"{tag}/{kind}: cscore.sh {' '.join(opts)} (started {time.strftime('%H:%M:%S')})"); t0 = time.time()
        os.makedirs(O, exist_ok=True)
        th = os.environ.get("SWEEP_THREADS", "1")        # hot-loop solve and numpy use every core unless told (measured 183 % CPU)
        env = dict(os.environ, **{k: th for k in ("NUMBA_NUM_THREADS", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")})
        p = subprocess.run([f"{CPLACE}/cscore.sh", O, f"{R}/p.json", *opts], stdout=open(f"{O}/cscore.log", "w"), stderr=subprocess.STDOUT, env=env)
        meta = dict(opts=opts, rc=p.returncode, wall_min=round((time.time() - t0) / 60, 1), finished=time.strftime("%Y-%m-%d %H:%M:%S"))
        jsave(meta, f"{O}/sweep_meta.json"); s = jload(f"{O}/score.json")
        log(f"{tag}/{kind}: {meta['wall_min']} min, {json.dumps(s) if s else 'NO score.json, see ' + O + '/cscore.log'}")
        return s
    finally:
        fcntl.flock(lk, fcntl.LOCK_UN); lk.close()

def cmd_screen(a):
    rows, _ = ranked(a)
    if a.tags: pick = a.tags.split(",")
    elif a.spread:
        n = len(rows); k = min(a.spread, n); pick = [rows[round(i * (n - 1) / max(k - 1, 1))]["tag"] for i in range(k)]
    else: pick = [r["tag"] for r in rows if not r["gates"]][:a.top or 4]
    log(f"screening {len(pick)}: {', '.join(pick)}")
    for t in pick: scorecard(a, t, "screen", a.opts.split())
    cmd_table(a)

def cmd_full(a):
    if a.bg:
        R = f"{a.out}/runs/{a.tag}"; lg = f"{R}/full.log"
        args = [sys.executable, os.path.abspath(__file__), "full", a.out, "--tag", a.tag, f"--route={a.route}", f"--load-max={a.load_max}"] + (["--no-hot"] if a.no_hot else [])
        sh = " ".join(f"'{x}'" for x in args) + "; echo DONE"
        subprocess.Popen(["nohup", "bash", "-c", sh], stdout=open(lg, "w"), stderr=subprocess.STDOUT, start_new_session=True)
        log(f"full scorecard for {a.tag} started in the background; log {lg} (ends with DONE)"); return
    opts = [f"--route={a.route}"] + (["--no-hot"] if a.no_hot else [])
    scorecard(a, a.tag, "full", opts); cmd_table(a)

# ----------------------------------------------------------------------------------------------- plan (power opens without KiCad)
TPL_BARE = os.environ.get("SWEEP_TPL_BARE", f"{HAND_SCREEN}/bare.json")

def parse_plan(txt, cons):
    """plan.log -> {net: [refs left to the router]} for power nets of 1 A or more, and the return pads left over"""
    cur = {n.lstrip("/"): v.get("current_a", 0) for n, v in cons["nets"].items()}; out = {}
    for m in re.finditer(r"^(\S[^:\n]*): ([\d.]+) A, .*?left to router \[(.*?)\]$", txt, re.M):
        n, a, lst = m.group(1).lstrip("/"), float(m.group(2)), m.group(3)
        refs = re.findall(r"'(\S+) \(", lst)
        if refs and a >= 1.0: out[n] = refs
    m = re.search(r'^return pads (\{.*\})$', txt, re.M)
    ret = sorted({x.split(".")[0] for x in json.loads(m.group(1)).get("left_to_router", [])}) if m else []
    return out, ret

def plan_open(left):
    """predicted scorecard power_open from the planner's 'left to router' lists: chips, FETs and connectors (U, Q, J)
    left on any net but PACK_P (a plane net: its leftovers join through the plane). Matched the scorecard exactly on
    the hand board and 3 base seeds (sweep/README.md); GND opens (return pads) are NOT predicted."""
    return {n: [r for r in v if r[0] in "UQJ"] for n, v in left.items() if n != "PACK_P" and any(r[0] in "UQJ" for r in v)}

def cmd_plan(a):
    """copper planner on the host for each placement (about 1 min each, one at a time): predicted power opens"""
    d, cl, it, cons = inputs(); sys.path.insert(0, HERE); import bare_xform
    rows, _ = ranked(a)
    tags = a.tags.split(",") if a.tags else [r["tag"] for r in rows if not any(g.startswith("duplicate") for g in r["gates"])][:a.top if a.top else None]
    tpl = jload(TPL_BARE) or sys.exit(f"no template cu_dump at {TPL_BARE} (run the hand screen first: tools/score/score_board.sh {HAND_SCREEN} --route=0 --no-hot)")
    for t in tags:
        O = f"{a.out}/runs/{t}/plan"
        if os.path.exists(f"{O}/plan.json") and not a.force: continue
        os.makedirs(O, exist_ok=True); lk = open(LOCK, "w"); fcntl.flock(lk, fcntl.LOCK_EX)
        try:
            wait_load(a.load_max, what=f"plan {t}"); t0 = time.time()
            json.dump(bare_xform.xform(json.loads(json.dumps(tpl)), jload(f"{a.out}/runs/{t}/p.json")), open(f"{O}/bare.json", "w"))
            p = subprocess.Popen([sys.executable, f"{REPO}/tools/copper/plan_copper.py", "bare.json", f"{REPO}/tools/floorplan/example/monolith/constraints.json", "spec.json"],
                                 cwd=O, stdout=open(f"{O}/plan.log", "w"), stderr=subprocess.STDOUT)
            signal.signal(signal.SIGTERM, lambda *_: (p.kill(), sys.exit(143)))       # a killed sweep must not leave the planner running
            p.wait()
            left, ret = parse_plan(open(f"{O}/plan.log").read(), cons)
            rep = (jload(f"{O}/spec.json") or {}).get("report", {})                      # plan.log cuts the return-pad list at 12
            if rep.get("return_pads"): ret = sorted({x.split(".")[0] for x in rep["return_pads"].get("left_to_router", [])})
            res = dict(rc=p.returncode, secs=round(time.time() - t0), left_to_router=left, return_left=ret, predicted_open=plan_open(left),
                       n_left=sum(len(v) for v in left.values()))
            res["n_open"] = sum(len(v) for v in res["predicted_open"].values())
            first = {h["caps"][0] for h in cons["hot_loops"].values()}      # a hot loop's first cap left unjoined -> tier 1 "no closed loop"
            res["hl_cap_left"] = sorted(first & (set(ret) | {r for v in left.values() for r in v}))
            jsave(res, f"{O}/plan.json"); os.remove(f"{O}/bare.json"); os.path.exists(f"{O}/spec.json") and os.remove(f"{O}/spec.json")
            px = jload(f"{a.out}/runs/{t}/proxies.json")
            if px is not None: px.update(plan_n_open=res["n_open"], plan_open=res["predicted_open"], plan_n_left=res["n_left"], plan_hl_cap_left=res["hl_cap_left"]); jsave(px, f"{a.out}/runs/{t}/proxies.json")
            log(f"{t}: plan {res['secs']} s, predicted power opens {res['predicted_open']}, hot-loop first caps left {res['hl_cap_left']} (left to router {left})")
        finally:
            fcntl.flock(lk, fcntl.LOCK_UN); lk.close()

# ----------------------------------------------------------------------------------------------- table, contact sheet
def bcount(s):
    m = re.match(r"(\d+) of (\d+)", str(s.get("blocked_edges", "")))
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)

def extra_open(s):
    ex = []
    for n, refs in (s.get("power_open") or {}).items():
        bad = [r for r in refs if r not in ALLOWED_OPEN.get(n, set())]
        if bad: ex.append(f"{n}@{'+'.join(bad)}")
    return ex

def hot_ok(s):
    h = s.get("hot_loops")
    if not h: return None
    m = re.match(r"(\d+) of (\d+)", h); return bool(m and m.group(1) == m.group(2))

def row_of(tag, kind, O, px):
    s = jload(f"{O}/score.json"); meta = jload(f"{O}/sweep_meta.json", {})
    if not s: return None
    ex = extra_open(s); bl, bt = bcount(s); ho = hot_ok(s)
    hard = not ex and s.get("drc_errors") == 0 and ho is not False
    r = dict(tag=tag, kind=kind, hard_ok=hard, n_extra_open=len(ex), extra_open=" ".join(ex) or "-", drc=s.get("drc_errors"), blocked=bl, blocked_of=bt,
             loss_W=s.get("loss_W"), hot=s.get("hot_loops", "not run"), route=s.get("route", "not run"), wall_min=meta.get("wall_min", ""), outdir=O)
    for k in PCOLS: r[k] = (px or {}).get(k, "")
    return r

def all_rows(a):
    rows = []
    for tag in runs(a.out):
        px = jload(f"{a.out}/runs/{tag}/proxies.json")
        for kind in ("screen", "full"):
            r = row_of(tag, kind, f"{a.out}/runs/{tag}/{kind}", px)
            if r: rows.append(r)
    rows.sort(key=lambda r: (not r["hard_ok"], r["n_extra_open"], r["blocked"] if r["blocked"] is not None else 9999, r["loss_W"] or 99))
    return rows

def cmd_table(a):
    rows = all_rows(a); d, cl, it, cons = inputs(); hand = hand_proxies(a.out, d, cl, it, cons)
    ref = row_of("HAND (reference)", "screen", HAND_SCREEN, hand) if os.path.exists(f"{HAND_SCREEN}/score.json") else None
    cols = ["tag", "kind", "hard_ok", "n_extra_open", "extra_open", "drc", "blocked", "blocked_of", "loss_W", "hot", "route", "wall_min"] + PCOLS + ["outdir"]
    with open(f"{a.out}/table.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore"); w.writeheader()
        for r in ([ref] if ref else []) + rows: w.writerow(r)
    sh = ["tag", "kind", "hard_ok", "extra_open", "drc", "blocked", "loss_W", "hot", "route", "sig_tree_mm", "crossings", "power_IxL", "hl_max", "d_U401_J401", "d_U504_U501", "outdir"]
    L = ["Sorted: hard limits (no extra power open, 0 DRC, hot loops all pass when run) first, then fewest extra power opens, then blocked edges, then loss.",
         "Loss is NOT comparable between rows with different opens: an open path carries no current and so has no loss.", "",
         "| " + " | ".join(sh) + " |", "|" + "---|" * len(sh)]
    for r in ([ref] if ref else []) + rows:
        L.append("| " + " | ".join("" if r.get(k) is None else (f"{r[k]} of {r['blocked_of']}" if k == "blocked" and r[k] is not None else str(r[k])) for k in sh) + " |")
    open(f"{a.out}/table.md", "w").write("\n".join(L) + "\n"); print("\n".join(L))
    contact(a, rows, ref)

def contact(a, rows, ref, per_row=4, scale=0.42):
    from PIL import Image, ImageDraw, ImageFont
    items = ([ref] if ref else []) + rows
    items = [r for r in items if os.path.exists(f"{r['outdir']}/F.png")]
    if not items: return
    try: font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 13)
    except OSError: font = ImageFont.load_default()
    th = []
    for r in items:
        ims = []
        for s in ("F", "B"):
            im = Image.open(f"{r['outdir']}/{s}.png").convert("RGB"); im = im.resize((int(im.width * scale), int(im.height * scale))); ims.append(im)
        th.append((r, ims))
    w1 = sum(i.width for i in th[0][1]) + 6; h1 = max(i.height for i in th[0][1]) + 52
    n = len(th); cols = min(per_row, n); rws = (n + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w1, rws * h1), "white"); dr = ImageDraw.Draw(sheet)
    for i, (r, ims) in enumerate(th):
        x0 = (i % cols) * w1; y0 = (i // cols) * h1; x = x0
        for im in ims: sheet.paste(im, (x, y0 + 50)); x += im.width + 2
        bl = f"{r['blocked']}/{r['blocked_of']}" if r["blocked"] is not None else "?"
        c = (0, 110, 0) if r["hard_ok"] else (180, 0, 0)
        dr.text((x0 + 3, y0 + 2), f"{r['tag'][:30]} [{r['kind']}]", fill=(0, 0, 0), font=font)
        dr.text((x0 + 3, y0 + 18), f"blk {bl} {r['loss_W']} W drc {r['drc']} xopen {r['n_extra_open']}", fill=c, font=font)
        dr.text((x0 + 3, y0 + 34), f"open: {r['extra_open'][:34]}", fill=c, font=font)
    sheet.save(f"{a.out}/contact.png"); log(f"contact sheet {a.out}/contact.png ({n} boards, F then B)")

# ----------------------------------------------------------------------------------------------- calibration
def cmd_calib(a):
    from scipy.stats import spearmanr
    rows = [r for r in all_rows(a) if r["kind"] == "screen" and r["blocked"] is not None]
    L = [f"# Proxy vs screen ({len(rows)} screened placements in {a.out})", "",
         "Spearman rank correlation (rho, p). Positive rho with blocked edges = a higher proxy value goes with more blocked edges.", "",
         "| proxy | rho vs blocked edges | p | rho vs extra power opens | p |", "|---|---|---|---|---|"]
    if len(rows) < 4: log("need at least 4 screened placements"); return
    d, cl, it, cons = inputs()
    pred_ok = 0; miss = []
    for r in rows:
        po = plan_open(parse_plan(open(f"{r['outdir']}/plan.log").read(), cons)[0]) if os.path.exists(f"{r['outdir']}/plan.log") else {}
        if r.get("plan_n_open") in ("", None): r["plan_n_open"] = sum(len(v) for v in po.values())
        pred = {f"{n}@{x}" for n, v in po.items() for x in v}
        act = {f"{n.lstrip('/')}@{x}" for n, v in (jload(f"{r['outdir']}/score.json") or {}).get("power_open", {}).items() if n != "GND" for x in v if x not in ALLOWED_OPEN.get(n, set())}
        if pred == act: pred_ok += 1
        else: miss.append(f"{r['tag']}: predicted only {sorted(pred - act)}, missed {sorted(act - pred)}")
    bl = [r["blocked"] for r in rows]; eo = [0 if r["extra_open"] == "-" else len(r["extra_open"].split()) for r in rows]
    lo = [r["loss_W"] for r in rows]
    res = []
    for k in PCOLS + ["score"]:
        if k == "score":
            rk = {x["tag"]: x["score"] for x in ranked(a)[0]}; v = [rk.get(r["tag"]) for r in rows]
        else: v = [r[k] for r in rows]
        if any(x in ("", None) for x in v) or len(set(v)) < 2: continue
        r1 = spearmanr(v, bl); r2 = spearmanr(v, eo) if len(set(eo)) > 1 else None
        res.append((k, r1, r2))
        L.append(f"| {k} | {r1.statistic:+.2f} | {r1.pvalue:.2f} | " + (f"{r2.statistic:+.2f} | {r2.pvalue:.2f}" if r2 else "n/a (no spread) | ") + " |")
    L += ["", f"plan_n_open (the copper planner's 'left to router' chips/FETs/connectors) equals the scorecard's non-GND extra opens on {pred_ok} of {len(rows)} boards.", *miss,
          f"loss vs blocked: rho {spearmanr(lo, bl).statistic:+.2f}; loss vs extra opens: rho {spearmanr(lo, eo).statistic:+.2f}", "", "| tag | blocked | extra opens | loss |", "|---|---|---|---|"]
    L += [f"| {r['tag']} | {r['blocked']} of {r['blocked_of']} | {r['extra_open']} | {r['loss_W']} |" for r in rows]
    open(f"{a.out}/calib.md", "w").write("\n".join(L) + "\n"); print("\n".join(L))

# ----------------------------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["place", "proxies", "plan", "rank", "screen", "full", "table", "calib"]); ap.add_argument("out")
    ap.add_argument("--seeds", default="1-12"); ap.add_argument("--grid"); ap.add_argument("--set", action="append")
    ap.add_argument("--hooks", default=os.environ.get("HOOKS", "")); ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--timeout", type=float, default=1800, help="seconds per placer run")
    ap.add_argument("--load-max", type=float, default=float(os.environ.get("SWEEP_LOAD_MAX", 3.0)))
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--hl-max", type=float, default=4.0, help="gate: first hot-loop cap pads to switch pin pads, centre to centre, worst loop, mm (hand board 3.37)")
    ap.add_argument("--pd-slack", type=float, default=3.0, help="gate: PD chip to connector, mm over the hand board")
    ap.add_argument("--buck-slack", type=float, default=6.0, help="gate: 5 V buck to PD chip, mm over the hand board")
    ap.add_argument("--sprawl-x", type=float, default=2.0, help="flag a section whose bbox/area ratio is over this times the hand board's")
    ap.add_argument("--weights", help="rank weights, e.g. power_IxL=2,hl_sum=2,sig_tree_mm=1")
    ap.add_argument("--top", type=int, help="screen: best K passing the gates (default 4); plan: first K by rank (default all)"); ap.add_argument("--spread", type=int); ap.add_argument("--tags")
    ap.add_argument("--opts", default="--route=0 --no-hot"); ap.add_argument("--tag"); ap.add_argument("--route", default="45")
    ap.add_argument("--no-hot", action="store_true"); ap.add_argument("--bg", action="store_true")
    a = ap.parse_args(); a.out = os.path.abspath(a.out); os.makedirs(a.out, exist_ok=True)
    dict(place=cmd_place, proxies=cmd_proxies, plan=cmd_plan, rank=cmd_rank, screen=cmd_screen, full=cmd_full, table=cmd_table, calib=cmd_calib)[a.cmd](a)

if __name__ == "__main__":
    main()
