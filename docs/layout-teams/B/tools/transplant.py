"""transplant.py <routed board A.kicad_pcb> <A's plan board (cu.kicad_pcb)> <plan board B (cu.kicad_pcb)> <out.kicad_pcb>
               [--drop=<drop.json>] [--no-drc]
Team B, phase 2 round 3 (lead). Moves the ROUTED copper of board A (every track and via that is not in A's plan board)
onto another plan board B of the same placement, so that a small change of the plan (a pour corner trimmed, a rule
area added, one pin path laid by the plan) does not cost a new 50 minute route with other failures.
drop.json: {"nets": [net, ...],                 routed copper of these nets is left behind (the new plan lays them)
            "vias": [[net, x, y], ...],         single routed vias left behind (e.g. in a new no-via area)
            "tracks": [[net, layer, x, y], ...]} routed tracks with an end within 0.01 mm of x,y left behind
No clearance check is made here: KiCad's DRC of the written board is the arbiter (printed: errors by type, unconnected
items). Use it only where plan A and plan B differ in a few known spots; what no longer fits must be in drop.json, and
the finishing pass (finish.sh --modes=aor) then lays the dropped connections again on plan B."""
import sys, os, json, subprocess, tempfile, shutil, math
from collections import Counter
T_ = os.path.dirname(os.path.abspath(__file__)); R = os.path.abspath(os.path.join(T_, "../../../.."))
sys.path.insert(0, os.path.join(R, "tools/copper"))
from dc_score import load_copper
A = [a for a in sys.argv[1:] if not a.startswith("--")]
O = dict(a[2:].split("=", 1) if "=" in a else (a[2:], "1") for a in sys.argv[1:] if a.startswith("--"))
if len(A) < 4: print(__doc__); sys.exit(2)
ba, ka, kb, out = [os.path.abspath(x) for x in A[:4]]
D = json.load(open(O["drop"])) if "drop" in O else {}
dn = set(D.get("nets", [])); dv = [tuple(v) for v in D.get("vias", [])]; dt = [tuple(t) for t in D.get("tracks", [])]
Z, T, V = load_copper(ba); Zk, Tk, Vk = load_copper(ka)
r = lambda p: (round(p[0], 4), round(p[1], 4))
kt = {(t["net"], t["layer"], r(t["a"]), r(t["b"])) for t in Tk}; kv = {(v["net"], r((v["x"], v["y"]))) for v in Vk}
J = {"tracks": [], "vias": []}; nd = Counter()
for t in T:
    if (t["net"], t["layer"], r(t["a"]), r(t["b"])) in kt: continue
    if t["net"] in dn: nd["track of a dropped net"] += 1; continue
    if any(t["net"] == n and t["layer"] == L and min(math.hypot(t["a"][0] - x, t["a"][1] - y), math.hypot(t["b"][0] - x, t["b"][1] - y)) < 0.01 for n, L, x, y in dt):
        nd["single track"] += 1; continue
    J["tracks"].append(dict(net=t["net"], layer=t["layer"], w=t["w"], a=list(t["a"]), b=list(t["b"])))
for v in V:
    if (v["net"], r((v["x"], v["y"]))) in kv: continue
    if v["net"] in dn: nd["via of a dropped net"] += 1; continue
    if any(v["net"] == n and math.hypot(v["x"] - x, v["y"] - y) < 0.01 for n, x, y in dv): nd["single via"] += 1; continue
    J["vias"].append(dict(net=v["net"], x=v["x"], y=v["y"], size=v.get("size", 0.45), drill=v.get("drill", 0.3)))
print("transplant: %d tracks, %d vias of %s onto %s; left behind %s" % (len(J["tracks"]), len(J["vias"]), A[0], A[2], dict(nd)))
tmp = tempfile.mkdtemp(prefix="tp_", dir=os.path.dirname(out))
try:
    shutil.copy(kb, tmp + "/in.kicad_pcb"); shutil.copy(ba, tmp + "/a.kicad_pcb")
    for e in ("kicad_pro", "kicad_dru"): shutil.copy(os.path.join(R, "tools/score/template/board." + e), tmp + "/in." + e)
    json.dump(J, open(tmp + "/items.json", "w"))
    open(tmp + "/tw.py", "w").write('''
import pcbnew, json
b = pcbnew.LoadBoard("in.kicad_pcb"); J = json.load(open("items.json")); FM = pcbnew.FromMM; MM = pcbnew.ToMM
# the via pad options of board A (the router sets "remove unconnected inner pads, keep start and end": without them the
# plane fills get wider antipads, 52 mm2 less GND on In1 and In4 each and +29 mW on this board)
VA = {}
for t in pcbnew.LoadBoard("a.kicad_pcb").GetTracks():
    if t.GetClass() == "PCB_VIA":
        c = t.GetPosition(); VA[(t.GetNetname(), round(MM(c.x), 3), round(MM(c.y), 3))] = (t.GetRemoveUnconnected(), t.GetKeepStartEnd())
lid = {pcbnew.BOARD.GetStandardLayerName(l): l for l in b.GetEnabledLayers().CuStack()}
def net(nm):
    c = b.FindNet(nm)
    if c is None: raise SystemExit("no net " + nm)
    return c
for t in J["tracks"]:
    s = pcbnew.PCB_TRACK(b); s.SetStart(pcbnew.VECTOR2I(FM(t["a"][0]), FM(t["a"][1]))); s.SetEnd(pcbnew.VECTOR2I(FM(t["b"][0]), FM(t["b"][1])))
    s.SetWidth(FM(t["w"])); s.SetLayer(lid[t["layer"]]); s.SetNet(net(t["net"])); b.Add(s)
nru = 0
for v in J["vias"]:
    s = pcbnew.PCB_VIA(b); s.SetPosition(pcbnew.VECTOR2I(FM(v["x"]), FM(v["y"]))); s.SetViaType(pcbnew.VIATYPE_THROUGH)
    s.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); s.SetDrill(FM(v["drill"])); s.SetNet(net(v["net"]))
    try: s.SetWidth(pcbnew.F_Cu, FM(v["size"]))
    except TypeError: s.SetWidth(FM(v["size"]))
    ru, ks = VA.get((v["net"], round(v["x"], 3), round(v["y"], 3)), (False, False))
    s.SetRemoveUnconnected(ru); s.SetKeepStartEnd(ks); nru += int(bool(ru))
    b.Add(s)
print("vias with unconnected inner pads removed: %d of %d" % (nru, len(J["vias"])))
b.BuildConnectivity(); pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.BuildConnectivity()
b.Save("out.kicad_pcb"); print("written")
''')
    K = ["docker", "run", "--rm", "-u", "0", "-v", tmp + ":/w", "-w", "/w", "kicad/kicad:10.0", "sh", "-c"]
    p = subprocess.run(K + ["python3 tw.py 2>&1 | grep -v swig"], capture_output=True, text=True)
    if "written" not in p.stdout: print(p.stdout, p.stderr); sys.exit(1)
    print("transplant: " + " ".join(l for l in p.stdout.splitlines() if l.startswith("vias with")))
    if "no-drc" not in O:
        shutil.copy(tmp + "/in.kicad_pro", tmp + "/out.kicad_pro"); shutil.copy(tmp + "/in.kicad_dru", tmp + "/out.kicad_dru")
        subprocess.run(K + ["kicad-cli pcb drc --severity-all --format json -o out.drc.json out.kicad_pcb >/dev/null 2>&1"])
        dj = json.load(open(tmp + "/out.drc.json")); shutil.copy(tmp + "/out.drc.json", out[:-10] + ".drc.json")
        er = Counter(v["type"] for v in dj["violations"] if v["severity"] == "error")
        print("transplant: DRC errors %d %s; unconnected items %d" % (sum(er.values()), dict(er), len(dj.get("unconnected_items", []))))
        for v in dj["violations"]:
            if v["severity"] == "error": print("  ERROR %s: %s" % (v["type"], " | ".join("%s @ %.3f,%.3f" % (i["description"], i["pos"]["x"], i["pos"]["y"]) for i in v["items"])))
        for u in dj.get("unconnected_items", []):
            print("  OPEN " + " | ".join("%s @ %.3f,%.3f" % (i["description"], i["pos"]["x"], i["pos"]["y"]) for i in u["items"]))
    shutil.copy(tmp + "/out.kicad_pcb", out)
    for e in ("kicad_pro", "kicad_dru"): shutil.copy(tmp + "/in." + e, out[:-10] + "." + e)
finally:
    shutil.rmtree(tmp, ignore_errors=True)
