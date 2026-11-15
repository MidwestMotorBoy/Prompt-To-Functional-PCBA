"""handroute.py <board in.kicad_pcb> <board out.kicad_pcb> <tracks.json> [--cu=<cu.json of board in>] [--no-drc] [--check]
Lays the last few connections of a routed board by explicit coordinates (team B, phase 2 finishing pass), so that an
agent can route them by looking at zoom pictures (tools/zoom.py on a dir holding the board as cu.kicad_pcb + cu.json).

tracks.json:
  {"board": "<which board the coordinates belong to, e.g. runs/p2b-r1/routed.kicad_pcb>",
   "tracks": [{"net": "/USB Port 1/C_CC2", "layer": "F.Cu", "w": 0.15, "points": [[104.75, 69.17], [104.9, 69.9]]}, ...],
   "vias":   [{"net": "/USB Port 1/C_CC2", "x": 105.85, "y": 70.9}]}          (vias 0.45 / 0.3, through)
Every segment and via is checked exactly before anything is written (tools/pinlib.py on the board's own copper: pads,
tracks, vias and FILLED zones; copper 0.15 mm, 0.25 mm HighCurrent to small signals, edge 0.25 mm, the router's via
spacing; fills of GND / PACK_P / 3V3 may be crossed because the refill carves round the new copper, except hot-loop
pours, which stay closed). New items are also checked against each other. Any fault: nothing is written, exit 1.
Then the items are added with KiCad's python (docker kicad/kicad:10.0), all zones are refilled and the board is saved;
KiCad DRC of the new board follows (errors by type, unconnected items) unless --no-drc. --check stops after the check."""
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
    D, G, _ = pinlib.load_board(bin_, cu)
    faults, n = [], 0
    for t in J.get("tracks", []):
        pts = t["points"]
        for a, b in zip(pts, pts[1:]):
            f = G.check_track(t["net"], t["layer"], a, b, t["w"], soft_ok=True)
            if f: faults.append(("track", t["net"], t["layer"], a, b, f[:3]))
            G.add_track(t["net"], t["layer"], a, b, t["w"]); n += 1
    for v in J.get("vias", []):
        f = G.check_via(v["net"], v["x"], v["y"], soft_ok=True, self_ok=False)
        if f: faults.append(("via", v["net"], v["x"], v["y"], f[:3]))
        G.add_via(v["net"], v["x"], v["y"])
    # ends that touch nothing of their net (a warning: the agent may mean a T on a track drawn in the same file)
    for t in J.get("tracks", []):
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
    json.dump(J, open(os.path.join(tmp, "items.json"), "w"))
    open(os.path.join(tmp, "hw.py"), "w").write('''
import pcbnew, json
b = pcbnew.LoadBoard("in.kicad_pcb"); J = json.load(open("items.json")); FM = pcbnew.FromMM
lid = {pcbnew.BOARD.GetStandardLayerName(l): l for l in b.GetEnabledLayers().CuStack()}
def net(nm):
    c = b.FindNet(nm)
    if c is None: raise SystemExit("no net " + nm)
    return c
for t in J.get("tracks", []):
    for a, c in zip(t["points"], t["points"][1:]):
        s = pcbnew.PCB_TRACK(b); s.SetStart(pcbnew.VECTOR2I(FM(a[0]), FM(a[1]))); s.SetEnd(pcbnew.VECTOR2I(FM(c[0]), FM(c[1])))
        s.SetWidth(FM(t["w"])); s.SetLayer(lid[t["layer"]]); s.SetNet(net(t["net"])); b.Add(s)
for v in J.get("vias", []):
    s = pcbnew.PCB_VIA(b); s.SetPosition(pcbnew.VECTOR2I(FM(v["x"]), FM(v["y"]))); s.SetViaType(pcbnew.VIATYPE_THROUGH)
    s.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); s.SetDrill(FM(0.3)); s.SetNet(net(v["net"]))
    try: s.SetWidth(pcbnew.F_Cu, FM(0.45))
    except TypeError: s.SetWidth(FM(0.45))
    b.Add(s)
b.BuildConnectivity(); pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.BuildConnectivity()
b.Save("out.kicad_pcb"); print("written")
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
