"""hr2.py <dir> <in board name> <out board name> <routes.json> [more ...]
Hand routes on top of an already routed board (all its copper stays). Reads <dir>/<in>.kicad_pcb, applies the routes
files made with obst.HR (routes, vias, drop; cuts and pours are for hr.py only), refills the zones, writes
<dir>/<out>.kicad_pcb and <dir>/<out>.drc.json, and prints every DRC error and the open connections of the nets touched,
plus the totals. "drop" removes existing tracks and vias of a net whose points lie inside a box (use it to re-lay a bad route)."""
import sys, os, json, re, subprocess, shutil
d = os.path.abspath(sys.argv[1]); IN, OUT = sys.argv[2], sys.argv[3]; files = sys.argv[4:]
J = {"routes": [], "vias": [], "drop": []}
for f in files:
    j = json.load(open(f))
    for k in J: J[k] += j.get(k, [])
txt = open("%s/%s.kicad_pcb" % (d, IN), encoding="utf-8").read()
inb = lambda x, y, b: b[0] <= x <= b[2] and b[1] <= y <= b[3]
def keep(m):
    blk = m.group(0); net = re.search(r'\(net "([^"]*)"\)', blk)
    if not net: return blk
    for dr in J["drop"]:
        if dr["net"] != net.group(1): continue
        if blk.lstrip().startswith("(segment"):
            if dr.get("layer") and '(layer "%s")' % dr["layer"] not in blk: continue
            a = re.search(r"\(start ([-\d.]+) ([-\d.]+)\)", blk); b = re.search(r"\(end ([-\d.]+) ([-\d.]+)\)", blk)
            if inb(float(a.group(1)), float(a.group(2)), dr["box"]) and inb(float(b.group(1)), float(b.group(2)), dr["box"]): return ""
        elif not dr.get("tracks_only"):
            a = re.search(r"\(at ([-\d.]+) ([-\d.]+)\)", blk)
            if a and inb(float(a.group(1)), float(a.group(2)), dr["box"]): return ""
    return blk
if J["drop"]: txt = re.sub(r"\n\t\((?:segment|via)\n(?:\t\t.*\n)+?\t\)", keep, txt)
open("%s/_hr2_%s_in.kicad_pcb" % (d, OUT), "w", encoding="utf-8").write(txt)
for e in ("kicad_pro", "kicad_dru"):
    shutil.copy("%s/%s.%s" % (d, IN, e), "%s/_hr2_%s_in.%s" % (d, OUT, e)); shutil.copy("%s/%s.%s" % (d, IN, e), "%s/%s.%s" % (d, OUT, e))
json.dump(J, open(d + "/_hr2_%s.json" % OUT, "w"))
open(d + "/_hr2_%s_apply.py" % OUT, "w").write('''
import json, pcbnew, sys
T = sys.argv[2]; b = pcbnew.LoadBoard("_hr2_%s_in.kicad_pcb" % T); J = json.load(open("_hr2_%s.json" % T)); FM = pcbnew.FromMM
lid = {pcbnew.BOARD.GetStandardLayerName(l): l for l in b.GetEnabledLayers().CuStack()}
def net(n):
    c = b.GetNetcodeFromNetname(n)
    if c < 0: raise SystemExit("no net " + n)
    return c
def via(n, x, y, size=0.45, drill=0.3):
    for t in b.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T and abs(pcbnew.ToMM(t.GetPosition().x) - x) < 0.01 and abs(pcbnew.ToMM(t.GetPosition().y) - y) < 0.01: return
    t = pcbnew.PCB_VIA(b); t.SetPosition(pcbnew.VECTOR2I(FM(x), FM(y))); t.SetDrill(FM(drill)); t.SetNetCode(net(n)); t.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    try: t.SetWidth(pcbnew.F_Cu, FM(size))
    except TypeError: t.SetWidth(FM(size))
    b.Add(t)
for v in J["vias"]: via(v["net"], v["x"], v["y"])
for r in J["routes"]:
    p = r["path"]
    for a, c in zip(p, p[1:]):
        if a[0] != c[0]: via(r["net"], a[1], a[2])
        if (a[1], a[2]) != (c[1], c[2]):
            t = pcbnew.PCB_TRACK(b); t.SetStart(pcbnew.VECTOR2I(FM(a[1]), FM(a[2]))); t.SetEnd(pcbnew.VECTOR2I(FM(c[1]), FM(c[2])))
            t.SetWidth(FM(r.get("w", 0.2))); t.SetLayer(lid[c[0]]); t.SetNetCode(net(r["net"])); b.Add(t)
b.BuildConnectivity(); pcbnew.ZONE_FILLER(b).Fill(b.Zones()); pcbnew.SaveBoard(sys.argv[1], b)
''')
K = ["docker", "run", "--rm", "-u", "0", "-v", d + ":/w", "-w", "/w", "kicad/kicad:10.0", "sh", "-c"]
subprocess.run(K + ["python3 _hr2_{0}_apply.py {0}.kicad_pcb {0} > _hr2_{0}.log 2>&1; cp _hr2_{0}_in.kicad_pro {0}.kicad_pro; kicad-cli pcb drc --severity-all --format json -o {0}.drc.json {0}.kicad_pcb >/dev/null 2>&1".format(OUT)], check=False)
D = json.load(open("%s/%s.drc.json" % (d, OUT))); nets = {r["net"] for r in J["routes"]} | {v["net"] for v in J["vias"]} | {x["net"] for x in J["drop"]}
errs = [v for v in D.get("violations", []) if v.get("severity") == "error"]
for v in errs:
    p = v["items"][0].get("pos", {}); print("  DRC %s at (%.2f, %.2f): %s" % (v["type"], p.get("x", 0), p.get("y", 0), " | ".join(i["description"] for i in v["items"])[:180]))
for u in D.get("unconnected_items", []):
    s = " -> ".join("%s @%.2f,%.2f" % (re.sub(r"\s+", " ", i["description"])[:55], i["pos"]["x"], i["pos"]["y"]) for i in u["items"][:2])
    if any("[%s]" % n in s for n in nets): print("  OPEN", s)
print("totals: DRC errors %d, open connections %d (in %s.drc.json)" % (len(errs), len(D.get("unconnected_items", [])), OUT))
