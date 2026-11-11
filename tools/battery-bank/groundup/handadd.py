"""handadd.py in.kicad_pcb out.kicad_pcb spec.json keepu.txt (KiCad python)
Add hand-drawn tracks / vias to a routed board; their ids are appended to keepu.txt so the router (--keepu) treats them
as fixed copper. spec: [{"net": n, "layer": "F", "w": 0.2, "pts": [[x, y], ...]}, {"net": n, "via": [x, y], "rul": 1 (optional)}, ...]
With {"lift": net} every router-laid item of that net (not in the keep ids) is removed first.
{"del": [x, y], "net": n, "what": "via" | layer} removes copper first; {"setw": [x1, y1, x2, y2], "layer", "net", "w"} changes
one track's width; a via with "rul": 1 gets no pads on inner layers it does not use (like the router's own vias)."""
import sys, json, pcbnew
mm = pcbnew.FromMM
b = pcbnew.LoadBoard(sys.argv[1]); spec = json.load(open(sys.argv[3]))
L = {"F": pcbnew.F_Cu, "In1": pcbnew.In1_Cu, "In2": pcbnew.In2_Cu, "In3": pcbnew.In3_Cu, "In4": pcbnew.In4_Cu, "B": pcbnew.B_Cu}
ids = []
MM = pcbnew.ToMM
near = lambda p, q: abs(MM(p.x) - q[0]) < 0.02 and abs(MM(p.y) - q[1]) < 0.02
ndel = 0
ALL = list(b.GetTracks()); gone = set()
for s in spec:                              # {"del": [x, y], "net": n, "what": "via" | "F" | "In2" | "In3" | "B"}: remove first
    if "del" not in s: continue
    for t in ALL:
        if id(t) in gone or t.GetNetname() != s["net"]: continue
        if s["what"] == "via":
            hit = t.GetClass() == "PCB_VIA" and near(t.GetPosition(), s["del"])
        else:
            hit = t.GetClass() == "PCB_TRACK" and t.GetLayer() == L[s["what"]] and (near(t.GetStart(), s["del"]) or near(t.GetEnd(), s["del"]))
        if hit: b.Remove(t); gone.add(id(t)); ndel += 1
nw = 0
for s in spec:                              # {"setw": [x1, y1, x2, y2], "layer": "F", "net": n, "w": 0.2}: change one track's width
    if "setw" not in s: continue
    q = s["setw"]
    for t in ALL:
        if id(t) in gone or t.GetClass() != "PCB_TRACK" or t.GetLayer() != L[s["layer"]] or t.GetNetname() != s["net"]: continue
        if (near(t.GetStart(), q[:2]) and near(t.GetEnd(), q[2:])) or (near(t.GetStart(), q[2:]) and near(t.GetEnd(), q[:2])): t.SetWidth(mm(s["w"])); nw += 1
for s in spec:
    if "lift" in s or "del" in s or "setw" in s: continue
    net = b.FindNet(s["net"]); assert net is not None, s["net"]
    if "via" in s:
        v = pcbnew.PCB_VIA(b); v.SetPosition(pcbnew.VECTOR2I(mm(s["via"][0]), mm(s["via"][1])))
        v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetWidth(mm(0.45)); v.SetDrill(mm(0.3)); v.SetNet(net)
        if s.get('rul'): v.SetRemoveUnconnected(True); v.SetKeepStartEnd(True)      # like the router's vias: no pads on unused inner layers
        b.Add(v); ids.append(v.m_Uuid.AsString())
    else:
        for a, c in zip(s["pts"], s["pts"][1:]):
            t = pcbnew.PCB_TRACK(b); t.SetStart(pcbnew.VECTOR2I(mm(a[0]), mm(a[1]))); t.SetEnd(pcbnew.VECTOR2I(mm(c[0]), mm(c[1])))
            t.SetWidth(mm(s.get("w", 0.2))); t.SetLayer(L[s["layer"]]); t.SetNet(net); b.Add(t); ids.append(t.m_Uuid.AsString())
b.BuildConnectivity(); pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[2])
open(sys.argv[4], "a").write("".join(i + "\n" for i in ids))
print("added", len(ids), "deleted", ndel, "width set", nw)
