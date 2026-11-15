"""eroute.py <dir> <base board> <out name> [options]       team E full route
  <dir>/<base>.kicad_pcb is the placed board with its power copper. Writes <dir>/<out>.routes.json, then (unless --noapply)
  <out>.kicad_pcb (zones refilled), <out>.drc.json and <out>.e.json through eapply.sh.
  --routes=FILE     start from earlier routes (kept, rip-able unless --pin)
  --fills=FILE      take every pour as KiCad filled it in this dump (a routed board's .e.json)
  --only=REGEX --skip=REGEX   nets to route
  --rips=N          rip-up budget (default 400)         --maxrip=K   times one net may be pulled (default 4)
  --w=0.2 --neck=0.15   track width and the width used where 0.2 does not fit
  --layers=0,2,3,5  routing layers (0 F, 1 In1, 2 In2, 3 In3, 4 In4, 5 B)
  --pin             earlier routes are fixed
  --taps=FILE       first lay the Kelvin taps listed in FILE (see tap_pass); these stay pinned
  --power[=terms.json]  first join the power pieces (pads that carry current) with wide tracks; these stay pinned"""
import sys, os, re, json, time, subprocess, math
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import er

def load_routes(W, path, pin=False):
    J = json.load(open(path)); n = 0
    W.voids += [v for v in J.get("voids", []) if (v["x"], v["y"]) not in {(u["x"], u["y"]) for u in W.voids}]
    for r in J["routes"]:
        nid = W.netid[r["net"]]
        rid = W.add_route(nid, [tuple(it) for it in r["items"]], dict(r.get("meta", {}), pin=pin or r.get("meta", {}).get("pin", False)))
        n += 1
    return n

def save_routes(W, path):
    J = {"routes": [dict(net=W.netname[rec["net"]], items=[list(it) for it in rec["items"]], meta=rec["meta"]) for rid, rec in sorted(W.dyn.items())]}
    # pour voids: no pour may touch a Kelvin tap's vias (the tap would sense the pour there instead of the shunt pad)
    V = {(v["x"], v["y"]): v for v in W.voids}
    for rec in W.dyn.values():
        if rec["meta"].get("tap"):
            for it in rec["items"]:
                if it[0] == "V": V.setdefault((it[2], it[3]), dict(x=it[2], y=it[3], r=0.52))
    J["voids"] = list(V.values())
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

def join(W, n, opt):
    """Join the pieces of net n without touching other routes. True when it is one piece."""
    while True:
        win, lab, k, cu, thr = W.pieces(n)
        if k < 2: return True
        sizes = np.bincount(lab.ravel(), minlength=k + 1); order = [int(i) for i in np.argsort(sizes) if i > 0 and sizes[i] > 0]
        for sp in order[:max(1, k - 1)]:
            res = W.connect(n, src_piece=sp, w=opt["w"], neck=opt["neck"], layers=opt["layers"], win=win)
            if res and res.get("items"):
                W.add_route(n, res["items"], dict(t=time.time())); break
        else:
            return False

def swap(W, n, opt, depth=0, locked=frozenset(), log=print):
    """Net n cannot be finished. Pull the routes in its way, route n, route them again; keep the result only when
    every net involved ends up whole (otherwise everything is put back). Tries a few different crossings."""
    win, lab, k, cu, thr = W.pieces(n)
    if k < 2: return True
    sizes = np.bincount(lab.ravel(), minlength=k + 1); order = [int(i) for i in np.argsort(sizes) if i > 0 and sizes[i] > 0]
    seen = set(); opts = []
    for sp in order[:3]:
        extra = None
        for alt in range(opt.get("alts", 2)):
            res = W.connect(n, src_piece=sp, w=opt["w"], neck=opt["neck"], layers=opt["layers"], win=win, ghost=True, extra_pen=extra)
            if not res or not res.get("blockers"): break
            bl = frozenset(res["blockers"])
            if any(W.dyn[b]["net"] in locked or W.dyn[b]["meta"].get("pin") for b in bl): bl = None
            elif bl not in seen: seen.add(bl); opts.append(bl)
            # next alternative: make this crossing dear
            if extra is None: extra = np.zeros((er.NL, W.NY, W.NX), np.float32)
            for (L, cy, cx) in res["cells"]: extra[L, max(cy - 3, 0):cy + 4, max(cx - 3, 0):cx + 4] += 15.0
    opts.sort(key=len)
    for bl in opts:
        if any(b not in W.dyn for b in bl): continue
        snap = W.snapshot(); nets = sorted({W.dyn[b]["net"] for b in bl})
        W.rip(bl)
        ok = join(W, n, opt)
        if ok:
            for m in nets:
                if join(W, m, opt): continue
                if depth < opt.get("depth", 1) and swap(W, m, opt, depth + 1, locked | {n}, log): continue
                ok = False; break
        if ok and W.pieces(n)[2] < 2:
            return True
        W.restore(snap)
    return False

def knot(W, n, opt, log=print, grow=1.5, maxnets=4, maxperm=60):
    """Net n is still open after rip-up and swap. Pull every loose route in the box round its unconnected pads that
    belongs to n or to a net with a pad in that box (the local nets), then lay those nets again in every order
    (n first), until one order closes them all. If none does, keep the best order when it leaves fewer connections
    open than before, else put everything back. Returns the nets left open (empty list = all closed), or None."""
    import itertools
    win, lab, k, cu, thr = W.pieces(n)
    if k < 2: return []
    x0, y0, x1, y1 = win
    sizes = np.bincount(lab.ravel(), minlength=k + 1); sizes[0] = 0; big = int(np.argmax(sizes))
    small = [p for p in range(1, k + 1) if p != big]
    c = np.argwhere(np.isin(lab, small))
    if len(c) == 0: return None
    if (c[:, 1].max() - c[:, 1].min() + c[:, 2].max() - c[:, 2].min()) * er.G > 12.0:
        c = np.argwhere(lab == min(small, key=lambda p: sizes[p]))
    bx0, by0 = W.xy(int(c[:, 2].min()) + x0, int(c[:, 1].min()) + y0); bx1, by1 = W.xy(int(c[:, 2].max()) + x0, int(c[:, 1].max()) + y0)
    # the box also holds the cheapest way across (through loose routes) from the smallest piece to the rest
    res = W.connect(n, src_piece=min(small, key=lambda p: sizes[p]), w=opt["w"], neck=opt["neck"], layers=opt["layers"], win=win, ghost=True)
    if res and res.get("cells"):
        for (L, cy, cx) in res["cells"]:
            x, y = W.xy(cx, cy); bx0 = min(bx0, x); bx1 = max(bx1, x); by0 = min(by0, y); by1 = max(by1, y)
    bx0 -= grow; by0 -= grow; bx1 += grow; by1 += grow
    inbox = lambda x, y: bx0 <= x <= bx1 and by0 <= y <= by1
    def touches(items):
        return any((inbox(it[2], it[3]) or (it[0] == "T" and inbox(it[4], it[5]))) for it in items)
    cand = {}
    for rid, rec in W.dyn.items():
        if not rec["meta"].get("pin") and touches(rec["items"]): cand.setdefault(rec["net"], []).append(rid)
    npad = {}
    for m in cand:
        npad[m] = sum(1 for it in W.net_items.get(m, []) if it[0] == "P" and inbox(float(it[2].mean()), float(it[3].mean())))
    local = sorted([m for m in cand if m != n and npad[m] > 0 and m not in W.soft_ids], key=lambda m: -npad[m])[:maxnets]
    nets = [n] + local
    before = sum(W.pieces(m)[2] - 1 for m in nets)
    if opt.get("verbose"): log("  knot %s box %.1f,%.1f,%.1f,%.1f nets %s open %d" % (W.netname[n], bx0, by0, bx1, by1, [W.netname[m].split("/")[-1] for m in nets], before))
    snap0 = W.snapshot()
    W.rip([r for m in nets for r in cand.get(m, [])])
    snap1 = W.snapshot()
    best = None
    perms = list(itertools.permutations(nets))
    if len(perms) > maxperm:
        import random
        random.Random(1).shuffle(perms); perms = perms[:maxperm]
    t0 = time.time()
    for perm in perms:
        if time.time() - t0 > opt.get("knot_s", 60): break
        left = []
        for m in perm:
            if not join(W, m, opt): left.append(m)
        if not left:
            log("  knot at %s closed: order %s" % (W.netname[n], ", ".join(W.netname[m].split("/")[-1] for m in perm)))
            return []
        op = sum(W.pieces(m)[2] - 1 for m in nets)
        if opt.get("verbose"): log("    order %s: open %d (%s)" % ([W.netname[m].split("/")[-1] for m in perm], op, [W.netname[m].split("/")[-1] for m in left]))
        if best is None or op < best[0]: best = (op, perm, left)
        W.restore(snap1)
    if best and best[0] < before:
        for m in best[1]: join(W, m, opt)
        log("  knot at %s: %d of %d connections still open (%s)" % (W.netname[n], best[0], before, ", ".join(W.netname[m].split("/")[-1] for m in best[2])))
        return list(best[2])
    W.restore(snap0)
    return None

def power_pass(W, terms, opt, log=print):
    """Power paths the copper plan left open: join the pieces that hold current-carrying pads (terms.json from go.sh:
    the scorecard's terminals) with wide tracks, widest first, before any signal. These routes are pinned."""
    pads = {}
    for p in W.D["pads"]:
        ls = [er.LAYERS.index(l) for l in p["shapes"]] or [0]
        pads[(p["ref"], p["num"])] = (ls, p["x"], p["y"])
    done = 0; failed = []
    order = sorted(terms.items(), key=lambda kv: -max([g["current_a"] for g in kv[1]] or [0]))
    for net, T in order:
        n = W.netid.get(net)
        if n is None or W.net_window(n) is None: continue
        bad = set()
        while True:
            win, lab, k, cu, thr = W.pieces(n)
            if k < 2: break
            x0, y0, x1, y1 = win; cur = {}; ser = set()
            for g in T:
                for num in g["pads"]:
                    if (g["ref"], num) not in pads: continue
                    ls, px, py = pads[(g["ref"], num)]; cx, cy = W.cell(px, py)
                    for L in ls:
                        pc = int(lab[L, cy - y0, cx - x0])
                        if pc:
                            cur[pc] = max(cur.get(pc, 0.0), g["current_a"])
                            if g["kind"] == "series": ser.add(pc)
                            break
            if len(cur) < 2: break
            sizes = np.bincount(lab.ravel(), minlength=k + 1)
            cand = sorted([p for p in cur if p not in bad and p != max(cur, key=lambda q: sizes[q])], key=lambda p: (-cur[p], sizes[p]))
            # pieces are renumbered after every route, so 'bad' holds piece sizes instead of labels
            cand = [p for p in cand if (int(sizes[p]), round(cur[p], 2)) not in bad]
            if not cand: break
            sp = cand[0]; I = cur[sp]
            w = 0.4 if I <= 1.0 else 0.8 if I <= 2.0 else 1.2
            res = None
            for neck in ([0.25] if w <= 0.4 else [0.4, 0.25, 0.2]):
                res = W.connect(n, src_piece=sp, w=w, neck=neck, layers=opt["layers"], win=win, only_target=[p for p in cur if p != sp],
                                lcost=(1.0, 9, 2.2, 2.2, 9, 1.0), via_cost=120.0, narrow_pen=4.0, pref=(0, 0, 0, 0, 0, 0))
                if res and res.get("items"): break
            ln = sum(math.hypot(it[4] - it[2], it[5] - it[3]) for it in res["items"] if it[0] == "T") if res and res.get("items") else 0
            if sp not in ser and ln > 4.0:
                bad.add((int(sizes[sp]), round(I, 2))); log("  power %s: a capacitor %.1f mm from its net's copper is left to the signal pass" % (net, ln)); continue
            if res and res.get("items"):
                W.add_route(n, res["items"], dict(pin=True, power=I)); done += 1
                log("  power %s: %.1f A piece joined, %.1f mm, %d vias, widths %s" % (net, I, ln, sum(1 for it in res["items"] if it[0] == "V"), sorted({it[6] for it in res["items"] if it[0] == "T"})))
            else:
                bad.add((int(sizes[sp]), round(I, 2))); failed.append((net, I)); log("  power %s: NO PATH for a %.1f A piece" % (net, I))
    return done, failed

def tap_pass(W, path, opt, log=print):
    """Kelvin taps (place/taps.txt): 'NET x,y REF.PAD [layers]' = a thin track of NET from pad REF.PAD to the tap via at
    x, y (a hand via at the inner edge of the shunt pad), arriving on an inner layer (default In3; '2,3' for In2 or In3)
    and keeping the clearance from every other piece of NET's copper. Pinned."""
    ok = bad = 0
    for line in open(path):          # 'void x,y [r]': keep every pour away from a hand via of a tap at x, y
        a = line.split("#")[0].split()
        if a and a[0] == "void":
            vx, vy = [float(v) for v in a[1].split(",")]
            W.voids.append(dict(x=vx, y=vy, r=float(a[2]) if len(a) > 2 else 0.52, hand=True))
    for line in open(path):
        a = line.split("#")[0].split()
        if not a or a[0] == "void": continue
        join = a[0] == "join"
        if join: a = a[1:]
        nm = a[0]
        if "@" in nm: nm = "/USB Port %s/%s" % (nm.split("@")[1], nm.split("@")[0])
        m = [x for x in W.netid if x == nm or x.endswith("/" + nm)]
        if len(m) != 1: log("  tap: net %s matches %s" % (a[0], m)); bad += 1; continue
        n = W.netid[m[0]]; tx, ty = [float(v) for v in a[1].split(",")]
        if join:
            # 'join NET x,y LAYERS W': the piece of NET that has copper at x, y is joined to the rest of the net on the
            # given layers only (5 = B.Cu), at width W; pinned. For a power pin that must leave on one layer.
            ls = tuple(int(v) for v in a[2].split(",")); wj = float(a[3])
            win, lab, k, cu, thr = W.pieces(n); x0, y0, x1, y1 = win; cx, cy = W.cell(tx, ty)
            sp = max(int(lab[L, cy - y0, cx - x0]) for L in range(er.NL))
            res = None
            if k < 2: log("  join %s at %s: already one piece" % (a[0], a[1])); ok += 1; continue
            for neck in (min(wj, 0.4), 0.25):
                res = W.connect(n, src_piece=sp, w=wj, neck=neck, layers=ls, win=win, narrow_pen=4.0, pref=(0,) * 6, lcost=(1.0,) * 6) if sp and k > 1 else None
                if res and res.get("items"): break
            if res and res.get("items"):
                W.add_route(n, res["items"], dict(pin=True, join=a[1])); ok += 1
                log("  join %s at %s: %.1f mm, widths %s" % (a[0], a[1], sum(math.hypot(it[4] - it[2], it[5] - it[3]) for it in res["items"] if it[0] == "T"), sorted({it[6] for it in res["items"] if it[0] == "T"})))
            else: bad += 1; log("  join %s at %s: NO PATH" % (a[0], a[1]))
            continue
        ref, num = a[2].split(".")
        tl = tuple(int(v) for v in a[3].split(",")) if len(a) > 3 else (3,)
        p = [q for q in W.D["pads"] if q["ref"] == ref and q["num"] == num]
        if not p: log("  tap: no pad %s" % a[2]); bad += 1; continue
        win, lab, k, cu, thr = W.pieces(n); x0, y0, x1, y1 = win
        cx, cy = W.cell(p[0]["x"], p[0]["y"]); L = er.LAYERS.index(list(p[0]["shapes"])[0])
        sp = int(lab[L, cy - y0, cx - x0])
        res = W.connect(n, src_piece=sp, w=0.15, neck=0.15, layers=opt["layers"], win=win, tap=(tx, ty, tl), via_cost=40.0) if sp else None
        if res and res.get("items"):
            W.add_route(n, res["items"], dict(pin=True, tap=a[2])); ok += 1
            W.voids += [dict(x=it[2], y=it[3], r=0.52) for it in res["items"] if it[0] == "V"]
            log("  tap %s %s: %.1f mm, %d vias" % (a[0], a[2], sum(math.hypot(it[4] - it[2], it[5] - it[3]) for it in res["items"] if it[0] == "T"), sum(1 for it in res["items"] if it[0] == "V")))
        else: bad += 1; log("  tap %s %s: NO PATH" % (a[0], a[2]))
    return ok, bad

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
    for rnd in range(2):
        for n in list(failed):
            if swap(W, n, opt, log=log): failed.remove(n); log("  swap closed %s" % W.netname[n])
    for n in list(failed):
        if n not in failed or W.pieces(n)[2] < 2: continue
        left = knot(W, n, opt, log)
        if left is None: continue
        for m in set(failed) | set(left):
            if W.pieces(m)[2] < 2 and m in failed: failed.remove(m)
            elif W.pieces(m)[2] > 1 and m not in failed: failed.append(m)
    return failed, stats

if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]; O = dict(x[2:].split("=", 1) if "=" in x else (x[2:], "1") for x in sys.argv[1:] if x.startswith("--"))
    d, base, out = os.path.abspath(a[0]), a[1], a[2]
    dump = "%s/%s.e.json" % (d, base)
    if not os.path.exists(dump) or os.path.getmtime(dump) < os.path.getmtime("%s/%s.kicad_pcb" % (d, base)):
        import shutil; shutil.copy(HERE + "/edump.py", d)
        subprocess.run(["docker", "run", "--rm", "-u", "0", "-v", d + ":/w", "-w", "/w", "kicad/kicad:10.0", "sh", "-c", "python3 edump.py %s.kicad_pcb %s.e.json 2>&1 | grep -v swig" % (base, base)])
    W = er.World(dump)
    if "softpen" in O:             # --softpen=NET:LAYER INDEX:PRICE   e.g. PACK_P:2:2.0
        nm, L, wt = O["softpen"].split(":"); W.set_softpen(W.netid[nm], int(L), float(wt))
    if "fills" in O:
        F = json.load(open(O["fills"])); W.fill_override = {}
        for n in W.net_items: W.net_items[n] = [it for it in W.net_items[n] if it[0] != "Z"]
        for z in F["zones"]:
            L = er.LAYERS.index(z["layer"])
            if z["net"] in er.SOFTNETS and ((0 < L < er.NL - 1) or z["prio"] == 0 or z["name"].startswith("plane_")):
                W.fill_override.setdefault(W.netid[z["net"]], []).append((L, z["fill"]))
            elif z["net"] in W.netid:
                W.net_items.setdefault(W.netid[z["net"]], []).append(("Z", L, z["fill"]))     # hard pours as KiCad really filled them
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
    if "taps" in O:
        print("taps: %d laid, %d failed" % tap_pass(W, O["taps"], opt, lambda s: print(s, flush=True)), flush=True)
    if "power" in O:
        T = json.load(open(O["power"] if O["power"] != "1" else d + "/terms.json"))
        dn, fl = power_pass(W, T, opt, lambda s: print(s, flush=True))
        print("power pass: %d joins, %d failed" % (dn, len(fl)), flush=True)
        nets = [n for n in nets if W.pieces(n)[2] > 1]
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
