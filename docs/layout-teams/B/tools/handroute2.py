"""handroute2.py <board in.kicad_pcb> <board out.kicad_pcb> <tracks.json> [--cu=<cu.json of board in>] [--no-drc] [--check]
             [--keep=<board before routing>]
Lays the last few connections of a routed board by explicit coordinates (team B, phase 2 finishing pass), so that an
agent can route them by looking at zoom pictures (tools/zoom.py on a dir holding the board as cu.kicad_pcb + cu.json).

tracks.json:
  {"board": "<which board the coordinates belong to, e.g. runs/p2b-r1/routed.kicad_pcb>",
   "tracks": [{"net": "/USB Port 1/C_CC2", "layer": "F.Cu", "w": 0.15, "points": [[104.75, 69.17], [104.9, 69.9]]}, ...],
   "vias":   [{"net": "/USB Port 1/C_CC2", "x": 105.85, "y": 70.9}]}          (vias 0.45 / 0.3, through)
      a via may carry "inpad": true (lead, round 3): allowed in a small pad of its own net, as the router's via-in-pad
  "lift": ["/USB Port 1/SS_5V", ...]   (round 2) nets whose ROUTED copper (every track and via not in the --keep board,
                                       i.e. not plan copper) is removed first; the new tracks then lay that net again
  "remove": [{"net": n, "layer": L, "a": [x, y], "b": [x, y]} | {"net": n, "via": [x, y]}]   single items removed first
  a track may give "from" and "to" instead of "points" ("REF.PAD" or [x, y]): the path is then searched in the free
  area of that layer (pinlib free_area + path_in, exact clearances, hot-loop pours closed), after the removals and the
  earlier tracks of the file, and printed; it starts and ends on the pad centres
Removed items are taken out of the check too. If a lifted net's pads are not joined again by the new tracks, KiCad's DRC
after it shows the open connection (finish.sh then drops the hand step).
Every segment and via is checked exactly before anything is written (tools/pinlib.py on the board's own copper: pads,
tracks, vias and FILLED zones; copper 0.15 mm, 0.25 mm HighCurrent to small signals, edge 0.25 mm, the router's via
spacing; fills of GND / PACK_P / 3V3 may be crossed because the refill carves round the new copper, except hot-loop
pours, which stay closed). New items are also checked against each other. Any fault: nothing is written, exit 1.
Then the items are added with KiCad's python (docker kicad/kicad:10.0), all zones are refilled and the board is saved;
KiCad DRC of the new board follows (errors by type, unconnected items) unless --no-drc. --check stops after the check.
handroute2.py (team B, phase 2 round 4, EN_5V1 worker): a copy of handroute.py with two changes.
  1. Removals ("lift", "remove") on inner layers work: handroute.py matched KiCad items by b.GetLayerName(), which
     returns the USER name of a layer ("In2.Cu (signal V + 3V3)" on the Monolith boards), so inner-layer items were
     never found and the write stopped with "removed 5 of 32 items". Here the standard name is used.
  2. A via may carry "rmun": true: written like the router's vias (SetRemoveUnconnected + SetKeepStartEnd), so the
     plane fills keep the narrow antipad on layers where the via has no track (a plain via costs plane area).
  3. The layer table is built without LSET.CuStack() (not wrapped in the KiCad 10 image: AttributeError).
  4. The KiCad python step ends with os._exit(0) after the save: in the KiCad 10 image the interpreter spun at 100 %
     CPU after b.Save() (13 min and still running on the Monolith board), so handroute.py never returned.
  5. Every new or removed item's python wrapper is kept alive (list KEEP): in the KiCad 10 image a new track whose
     wrapper was collected (the loop variable reassigned) left a freed item in the board, and b.Zones() before the
     refill crashed (segmentation fault, nothing written). handroute.py has the same fault for files with tracks.
Hand files for handroute.py work unchanged."""
import sys, os, json, subprocess, tempfile, shutil, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pinlib

A = [a for a in sys.argv[1:] if not a.startswith("--")]
O = dict(a[2:].split("=", 1) if "=" in a else (a[2:], "1") for a in sys.argv[1:] if a.startswith("--"))
if len(A) < 3: print(__doc__); sys.exit(2)
bin_, bout, js = [os.path.abspath(x) for x in A[:3]]
J = json.load(open(js))
K = "kicad/kicad:10.0"


def docker(wd, cmd):
    return subprocess.run(["docker", "run", "--rm", "-u", "0", "-v", wd + ":/w", "-w", "/w", K, "sh", "-c", cmd],
                          capture_output=True, text=True)


tmp = tempfile.mkdtemp(prefix="hr_", dir=os.path.dirname(bout))
try:
    cu = O.get("cu")
    if not cu:
        shutil.copy(bin_, os.path.join(tmp, "in.kicad_pcb"))
        shutil.copy(os.path.join(pinlib.REPO, "tools/copper/cu_dump.py"), tmp)
        docker(tmp, "python3 cu_dump.py in.kicad_pcb in.json >/dev/null 2>&1")
        cu = os.path.join(tmp, "in.json")
    D, G, (Z0, T0, V0) = pinlib.load_board(bin_, cu)
    # round 2: with --keep, the hot-loop pours of the board before routing are obstacles too (tools/hot_tracks.py
    # measures against those, and the routed board's fills have been carved round the router's copper)
    if "keep" in O:
        sys.path.insert(0, os.path.join(pinlib.REPO, "tools/copper"))
        from dc_score import load_copper as _lc
        ZK, _, _ = _lc(O["keep"]); zk = {}
        for z in ZK:
            if len(z["pts"]) > 2 and z["layer"] in ("F.Cu", "B.Cu"):
                zk.setdefault((z["net"], z["layer"]), []).append(pinlib.Polygon(z["pts"]).buffer(0))
        zks = [dict(net=n_, layer=L_, geoms=g_) for (n_, L_), g_ in zk.items()]
        nh = 0
        for zi, pi in pinlib.hot_polys(zks, D["pads"]):
            z = zks[zi]; G.items[z["layer"]].append((z["net"], "hotzone", z["geoms"][pi], dict(z, soft=True))); nh += 1
        G._index()
        print("handroute: %d hot-loop pours of the plan board are obstacles" % nh)
    # round 2: routed copper of the lifted nets and single items to remove (before the check)
    REM_T, REM_V = [], []
    lift = set(J.get("lift", []))
    if lift:
        if "keep" not in O: print("handroute: 'lift' needs --keep=<board before routing>"); sys.exit(2)
        sys.path.insert(0, os.path.join(pinlib.REPO, "tools/copper"))
        from dc_score import load_copper
        _, TK, VK = load_copper(O["keep"])
        kt = {(t["net"], t["layer"], round(t["a"][0], 4), round(t["a"][1], 4), round(t["b"][0], 4), round(t["b"][1], 4)) for t in TK}
        kv = {(v["net"], round(v["x"], 4), round(v["y"], 4)) for v in VK}
        REM_T += [t for t in T0 if t["net"] in lift and (t["net"], t["layer"], round(t["a"][0], 4), round(t["a"][1], 4), round(t["b"][0], 4), round(t["b"][1], 4)) not in kt]
        REM_V += [v for v in V0 if v["net"] in lift and (v["net"], round(v["x"], 4), round(v["y"], 4)) not in kv]
    for r in J.get("remove", []):
        if "via" in r:
            REM_V += [v for v in V0 if v["net"] == r["net"] and math.hypot(v["x"] - r["via"][0], v["y"] - r["via"][1]) < 0.002]
        else:
            REM_T += [t for t in T0 if t["net"] == r["net"] and t["layer"] == r["layer"] and
                      {(round(t["a"][0], 3), round(t["a"][1], 3)), (round(t["b"][0], 3), round(t["b"][1], 3))} ==
                      {(round(r["a"][0], 3), round(r["a"][1], 3)), (round(r["b"][0], 3), round(r["b"][1], 3))}]
    if REM_T or REM_V:
        gl = [pinlib.LineString([tuple(t["a"]), tuple(t["b"])]).buffer(t["w"] / 2, 16) if tuple(t["a"]) != tuple(t["b"]) else pinlib.Point(t["a"]).buffer(t["w"] / 2, 16) for t in REM_T]
        gv = [pinlib.Point(v["x"], v["y"]).buffer(v["size"] / 2, 24) for v in REM_V]
        def _gone(L, it):
            if it[1] == "track" and L in ("F.Cu", "In2.Cu", "In3.Cu", "B.Cu", "In1.Cu", "In4.Cu"):
                return any(it[0] == t["net"] and t["layer"] == L and it[2].equals_exact(g, 1e-6) for t, g in zip(REM_T, gl))
            if it[1] == "via":
                return any(it[0] == v["net"] and it[2].equals_exact(g, 1e-6) for v, g in zip(REM_V, gv))
            return False
        G.remove_where(_gone)
        rv = {(v["x"], v["y"], v["net"]) for v in REM_V}
        G.vias = [q for q in G.vias if q not in rv]; G._index()
        print("handroute: removing %d tracks, %d vias first (lift %s)" % (len(REM_T), len(REM_V), sorted(lift)))
    faults, n = [], 0
    def _end(e, L):
        if isinstance(e, str):
            ref, num = e.split(".")
            ps = pinlib.pad_of(D, ref, num)
            q = ps[0]
            g = pinlib.unary_union([pinlib.poly(r) for r in q["shapes"].get(L, []) or [rr for rs in q["shapes"].values() for rr in rs]])
            return (q["x"], q["y"]), g
        return tuple(e), pinlib.Point(e).buffer(0.05)
    for t in J.get("tracks", []):
        if "points" not in t:                              # searched path from / to
            (a, ga), (b, gb) = _end(t["from"], t["layer"]), _end(t["to"], t["layer"])
            m = float(t.get("margin", 1.5))
            bx = (min(a[0], b[0]) - m, min(a[1], b[1]) - m, max(a[0], b[0]) + m, max(a[1], b[1]) + m)
            free = G.free_area(t["net"], t["layer"], t["w"], bx, soft_ok=True).union(ga.buffer(-0.01))
            path = pinlib.path_in(free, a, gb, step=float(t.get("step", 0.02)))
            if not path:
                faults.append(("track", t["net"], t["layer"], a, b, [("no path", 0, 0)])); t["points"] = []; continue
            if isinstance(t["to"], str) and tuple(path[-1]) != tuple(b): path = list(path) + [b]
            t["points"] = [list(p) for p in path]
            print("  path %s %s %s -> %s: %s" % (t["net"], t["layer"], t["from"], t["to"], t["points"]))
        pts = t["points"]
        for a, b in zip(pts, pts[1:]):
            f = G.check_track(t["net"], t["layer"], a, b, t["w"], soft_ok=True)
            if f: faults.append(("track", t["net"], t["layer"], a, b, f[:3]))
            G.add_track(t["net"], t["layer"], a, b, t["w"]); n += 1
    for v in J.get("vias", []):
        f = G.check_via(v["net"], v["x"], v["y"], soft_ok=True, self_ok=False, inpad=bool(v.get("inpad")))
        if f: faults.append(("via", v["net"], v["x"], v["y"], f[:3]))
        G.add_via(v["net"], v["x"], v["y"])
    # ends that touch nothing of their net (a warning: the agent may mean a T on a track drawn in the same file)
    for t in J.get("tracks", []):
        if not t["points"]: continue
        for e in (t["points"][0], t["points"][-1]):
            own = G.own(t["net"], t["layer"], (e[0] - 0.05, e[1] - 0.05, e[0] + 0.05, e[1] + 0.05))
            if own.is_empty or own.distance(pinlib.Point(e)) > 0.01:
                print("  WARNING: end %s of a %s track touches no %s copper on %s" % (e, t["net"], t["net"], t["layer"]))
    for f in faults: print("  FAULT", f)
    print("handroute: %d segments, %d vias checked, %d faults (coordinates for %s)" % (n, len(J.get("vias", [])), len(faults), J.get("board", "?")))
    if faults: sys.exit(1)
    if "check" in O: sys.exit(0)
    # write with KiCad's python
    shutil.copy(bin_, os.path.join(tmp, "in.kicad_pcb"))
    for e in ("kicad_pro", "kicad_dru"):         # the board's rules, or the zone refill ignores the custom DRC rules
        src = bin_[:-10] + "." + e
        shutil.copy(src if os.path.exists(src) else os.path.join(pinlib.REPO, "tools/score/template/board." + e), os.path.join(tmp, "in." + e))
    J["_rem_t"] = [dict(net=t["net"], layer=t["layer"], a=list(t["a"]), b=list(t["b"])) for t in REM_T]
    J["_rem_v"] = [dict(net=v["net"], x=v["x"], y=v["y"]) for v in REM_V]
    json.dump(J, open(os.path.join(tmp, "items.json"), "w"))
    open(os.path.join(tmp, "hw.py"), "w").write('''
import pcbnew, json
b = pcbnew.LoadBoard("in.kicad_pcb"); J = json.load(open("items.json")); FM = pcbnew.FromMM; MM = pcbnew.ToMM
RT = {(t["net"], t["layer"], round(t["a"][0], 4), round(t["a"][1], 4), round(t["b"][0], 4), round(t["b"][1], 4)) for t in J.get("_rem_t", [])}
RV = {(v["net"], round(v["x"], 4), round(v["y"], 4)) for v in J.get("_rem_v", [])}
nr = 0; KEEP = []                    # every wrapper stays alive until os._exit (KiCad 10: a collected wrapper frees the item)
for t in list(b.GetTracks()):
    if t.GetClass() == "PCB_VIA":
        c = t.GetPosition()
        if (t.GetNetname(), round(MM(c.x), 4), round(MM(c.y), 4)) in RV: b.Remove(t); KEEP.append(t); nr += 1
    else:
        s_, e_ = t.GetStart(), t.GetEnd()
        if (t.GetNetname(), pcbnew.BOARD.GetStandardLayerName(t.GetLayer()), round(MM(s_.x), 4), round(MM(s_.y), 4), round(MM(e_.x), 4), round(MM(e_.y), 4)) in RT: b.Remove(t); KEEP.append(t); nr += 1
if nr != len(RT) + len(RV): raise SystemExit("removed %d of %d items" % (nr, len(RT) + len(RV)))
lid = {pcbnew.BOARD.GetStandardLayerName(l): l for l in range(pcbnew.PCB_LAYER_ID_COUNT) if pcbnew.IsCopperLayer(l)}
def net(nm):
    c = b.FindNet(nm)
    if c is None: raise SystemExit("no net " + nm)
    return c
for t in J.get("tracks", []):
    for a, c in zip(t["points"], t["points"][1:]):
        s = pcbnew.PCB_TRACK(b); s.SetStart(pcbnew.VECTOR2I(FM(a[0]), FM(a[1]))); s.SetEnd(pcbnew.VECTOR2I(FM(c[0]), FM(c[1])))
        s.SetWidth(FM(t["w"])); s.SetLayer(lid[t["layer"]]); s.SetNet(net(t["net"])); b.Add(s); KEEP.append(s)
for v in J.get("vias", []):
    s = pcbnew.PCB_VIA(b); s.SetPosition(pcbnew.VECTOR2I(FM(v["x"]), FM(v["y"]))); s.SetViaType(pcbnew.VIATYPE_THROUGH)
    s.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); s.SetDrill(FM(0.3)); s.SetNet(net(v["net"]))
    try: s.SetWidth(pcbnew.F_Cu, FM(0.45))
    except TypeError: s.SetWidth(FM(0.45))
    if v.get("rmun"):
        s.SetRemoveUnconnected(True); s.SetKeepStartEnd(True)
    b.Add(s); KEEP.append(s)
b.BuildConnectivity(); pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.BuildConnectivity()
b.Save("out.kicad_pcb"); print("written", flush=True)
import os; os._exit(0)
''')
    r = docker(tmp, "python3 hw.py 2>&1 | grep -v swig")
    if "written" not in r.stdout: print(r.stdout, r.stderr); sys.exit(1)
    shutil.copy(os.path.join(tmp, "out.kicad_pcb"), bout)
    for e in ("kicad_pro", "kicad_dru"):
        src = bin_[:-10] + "." + e
        if os.path.exists(src) and not os.path.exists(bout[:-10] + "." + e): shutil.copy(src, bout[:-10] + "." + e)
    if "no-drc" not in O:
        d = os.path.dirname(bout); nm = os.path.basename(bout)
        docker(d, "kicad-cli pcb drc --severity-all --format json -o %s.drc.json %s >/dev/null 2>&1" % (nm[:-10], nm))
        dj = json.load(open(os.path.join(d, nm[:-10] + ".drc.json")))
        from collections import Counter
        er = Counter(v["type"] for v in dj["violations"] if v["severity"] == "error")
        print("handroute: wrote %s; DRC errors %d %s; unconnected items %d" % (bout, sum(er.values()), dict(er), len(dj.get("unconnected_items", []))))
finally:
    shutil.rmtree(tmp, ignore_errors=True)
