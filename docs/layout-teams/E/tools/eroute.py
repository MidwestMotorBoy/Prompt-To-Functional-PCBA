"""eroute.py <dir> <base board> <out name> [options]       team E full route
  <dir>/<base>.kicad_pcb is the placed board with its power copper. Writes <dir>/<out>.routes.json, then (unless --noapply)
  <out>.kicad_pcb (zones refilled), <out>.drc.json and <out>.e.json through eapply.sh.
  --routes=FILE     start from earlier routes (kept, rip-able unless --pin)
  --fills=FILE      take the soft pours (GND, PACK_P, 3V3 planes) as filled in this dump (a routed board's .e.json)
  --only=REGEX --skip=REGEX   nets to route
  --rips=N          rip-up budget (default 400)         --maxrip=K   times one net may be pulled (default 4)
  --w=0.2 --neck=0.15   track width and the width used where 0.2 does not fit
  --layers=0,2,3,5  routing layers (0 F, 1 In1, 2 In2, 3 In3, 4 In4, 5 B)
  --pin             earlier routes are fixed"""
import sys, os, re, json, time, subprocess, math
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import er

def load_routes(W, path, pin=False):
    J = json.load(open(path)); n = 0
    for r in J["routes"]:
        nid = W.netid[r["net"]]
        rid = W.add_route(nid, [tuple(it) for it in r["items"]], dict(r.get("meta", {}), pin=pin or r.get("meta", {}).get("pin", False)))
        n += 1
    return n

def save_routes(W, path):
    J = {"routes": [dict(net=W.netname[rec["net"]], items=[list(it) for it in rec["items"]], meta=rec["meta"]) for rid, rec in sorted(W.dyn.items())]}
    json.dump(J, open(path, "w"))

def net_span(W, n):
    xs, ys = [], []
    for it in W.net_items.get(n, []):
        if it[0] == "P": xs += [it[2].mean()]; ys += [it[3].mean()]
    if len(xs) < 2: return 0.0
    return (max(xs) - min(xs)) + (max(ys) - min(ys))

def route_net(W, n, opt, stats, log):
    """Join all pieces of net n. Returns (ok, ripped net ids)."""
    ripped = []
    tried_fail = 0
    while True:
        win, lab, k, cu, thr = W.pieces(n)
        if k < 2: return True, ripped
        sizes = np.bincount(lab.ravel(), minlength=k + 1); order = [int(i) for i in np.argsort(sizes) if i > 0 and sizes[i] > 0]
        done = False
        for sp in order[:max(1, k - 1)]:
            res = W.connect(n, src_piece=sp, w=opt["w"], neck=opt["neck"], layers=opt["layers"], win=win)
            if res and res.get("items"):
                W.add_route(n, res["items"], dict(t=time.time())); stats["routed"] += 1; done = True; break
        if done: continue
        # no clean path from any piece: look for the cheapest crossing of other routes
        best = None
        if stats["rips"] < opt["rips"]:
            for sp in order[:max(1, k - 1)]:
                res = W.connect(n, src_piece=sp, w=opt["w"], neck=opt["neck"], layers=opt["layers"], win=win, ghost=True)
                if res and res.get("blockers"):
                    bl = res["blockers"]
                    if any(W.dyn[b]["meta"].get("pin") or stats["ripcount"].get(W.dyn[b]["net"], 0) >= opt["maxrip"] for b in bl): continue
                    if best is None or len(bl) < len(best[1]): best = (sp, bl)
        if best is None:
            return False, ripped
        sp, bl = best
        nets = sorted({W.dyn[b]["net"] for b in bl})
        for m in nets: stats["ripcount"][m] = stats["ripcount"].get(m, 0) + 1
        W.rip(bl); stats["rips"] += len(bl); ripped += nets
        res = W.connect(n, src_piece=sp, w=opt["w"], neck=opt["neck"], layers=opt["layers"], win=win)
        if res and res.get("items"):
            W.add_route(n, res["items"], dict(t=time.time())); stats["routed"] += 1
        else:
            tried_fail += 1
            if tried_fail > 3: return False, ripped

def route_all(W, nets, opt, log=print):
    stats = dict(routed=0, rips=0, ripcount={})
    queue = list(nets); failed = []; t0 = time.time(); it = 0
    while queue:
        n = queue.pop(0); it += 1
        ok, ripped = route_net(W, n, opt, stats, log)
        for m in ripped:
            if m not in queue: queue.insert(0, m)
            if m in failed: failed.remove(m)
        if not ok:
            if n not in failed: failed.append(n)
            log("  FAIL %s (%d pieces left)" % (W.netname[n], W.pieces(n)[2]))
        if it % 25 == 0: log("  .. %d nets done, %d in queue, %d routes, %d rips, %d failed, %.0f s" % (it, len(queue), stats["routed"], stats["rips"], len(failed), time.time() - t0))
    # second chance for failed nets (things have moved)
    for n in list(failed):
        ok, ripped = route_net(W, n, opt, stats, log)
        if ok: failed.remove(n)
        for m in ripped:
            ok2, _ = route_net(W, m, opt, stats, log)
            if not ok2 and m not in failed: failed.append(m)
    return failed, stats

if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]; O = dict(x[2:].split("=", 1) if "=" in x else (x[2:], "1") for x in sys.argv[1:] if x.startswith("--"))
    d, base, out = os.path.abspath(a[0]), a[1], a[2]
    dump = "%s/%s.e.json" % (d, base)
    if not os.path.exists(dump) or os.path.getmtime(dump) < os.path.getmtime("%s/%s.kicad_pcb" % (d, base)):
        import shutil; shutil.copy(HERE + "/edump.py", d)
        subprocess.run(["docker", "run", "--rm", "-u", "0", "-v", d + ":/w", "-w", "/w", "kicad/kicad:10.0", "sh", "-c", "python3 edump.py %s.kicad_pcb %s.e.json 2>&1 | grep -v swig" % (base, base)])
    W = er.World(dump)
    if "fills" in O:
        F = json.load(open(O["fills"])); W.fill_override = {}
        for z in F["zones"]:
            if z["net"] in er.SOFTNETS:
                L = er.LAYERS.index(z["layer"])
                if (0 < L < er.NL - 1) or z["prio"] == 0 or z["name"].startswith("plane_"):
                    W.fill_override.setdefault(W.netid[z["net"]], []).append((L, z["fill"]))
    if "routes" in O: print("loaded %d earlier routes" % load_routes(W, O["routes"], "pin" in O))
    only = re.compile(O["only"]) if "only" in O else None; skip = re.compile(O["skip"]) if "skip" in O else None
    opt = dict(w=float(O.get("w", 0.2)), neck=float(O.get("neck", 0.15)), layers=tuple(int(v) for v in O.get("layers", "0,2,3,5").split(",")),
               rips=int(O.get("rips", 400)), maxrip=int(O.get("maxrip", 4)))
    nets = []
    for n, nm in W.netname.items():
        if (only and not only.search(nm)) or (skip and skip.search(nm)): continue
        if W.net_window(n) is None: continue
        k = W.pieces(n)[2]
        if k > 1: nets.append(n)
    def key(n):
        c = W.cls.get(n, "")
        rank = 0 if "Kelvin" in c else 1 if "GateDrive" in c else 3 if W.netname[n] in er.SOFTNETS else 2
        return (rank, net_span(W, n))
    nets.sort(key=key)
    need = sum(W.pieces(n)[2] - 1 for n in nets)
    print("nets to route: %d, connections: %d" % (len(nets), need), flush=True)
    t0 = time.time()
    failed, stats = route_all(W, nets, opt, lambda s: print(s, flush=True))
    left = sum(W.pieces(n)[2] - 1 for n in failed)
    print("routed %d connections, %d rips, %d nets failed (%d connections open) in %.0f s" % (stats["routed"], stats["rips"], len(failed), left, time.time() - t0))
    for n in failed: print("  open: %s (%d pieces)" % (W.netname[n], W.pieces(n)[2]))
    save_routes(W, "%s/%s.routes.json" % (d, out))
    if "noapply" not in O:
        subprocess.run(["bash", HERE + "/eapply.sh", d, base, "%s/%s.routes.json" % (d, out), out])
