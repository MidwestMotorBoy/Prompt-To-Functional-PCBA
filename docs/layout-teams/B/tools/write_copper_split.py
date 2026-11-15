"""write_copper_split.py <bare placed board.kicad_pcb> <spec.json> <out.kicad_pcb>      (KiCad's python: needs pcbnew)
Team B copy of tools/copper/write_copper.py with one change: ONE ZONE PER OUTLINE. The shared writer puts every outline
of a net and layer into one zone; KiCad keeps only the first outline of such a zone when the board is loaded and filled
again, so the router's last refill (and KiCad's own connectivity) loses most F.Cu/B.Cu power pours. With one zone per
outline every pour survives a reload. Puts the power copper plan_copper.py generated into a board, the vias and the
short tracks, then fills all zones and saves. The project file beside the
output (rules, net classes) is kept as it was."""
import sys, os, json, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); S = json.load(open(sys.argv[2])); FM = pcbnew.FromMM
lid = {pcbnew.BOARD.GetStandardLayerName(l): l for l in b.GetEnabledLayers().CuStack()}
def net(n):
    c = b.GetNetcodeFromNetname(n)
    if c < 0: raise SystemExit("no net " + n)
    return c
clr = S.get("clearance_mm", 0.2)
nz = 0
for z in S["zones"]:
    for p in z["polys"]:                                  # one zone per outline: a saved zone keeps only its first outline
        zn = pcbnew.ZONE(b); zn.SetLayer(lid[z["layer"]]); zn.SetNetCode(net(z["net"])); zn.SetZoneName(("plane_" if "plane" in z["kinds"] else "pc_") + z["net"].strip("/").replace("/", "_"))
        o = zn.Outline()
        o.NewOutline(); k = o.OutlineCount() - 1
        for x, y in p["ring"]: o.Append(FM(x), FM(y), k)
        for h in p["holes"]:
            o.NewHole(k)
            for x, y in h: o.Append(FM(x), FM(y), k, o.HoleCount(k) - 1)
        zn.SetAssignedPriority(int(z["priority"])); zn.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL); zn.SetLocalClearance(FM(clr)); zn.SetMinThickness(FM(0.15))
        zn.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS); b.Add(zn); nz += 1
for v in S["vias"]:
    t = pcbnew.PCB_VIA(b); t.SetPosition(pcbnew.VECTOR2I(FM(v["x"]), FM(v["y"]))); t.SetDrill(FM(v["drill"])); t.SetNetCode(net(v["net"])); t.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    try: t.SetWidth(pcbnew.F_Cu, FM(v["size"]))
    except TypeError: t.SetWidth(FM(v["size"]))
    b.Add(t)
for s in S["tracks"]:
    t = pcbnew.PCB_TRACK(b); t.SetStart(pcbnew.VECTOR2I(FM(s["a"][0]), FM(s["a"][1]))); t.SetEnd(pcbnew.VECTOR2I(FM(s["b"][0]), FM(s["b"][1])))
    t.SetWidth(FM(s["w"])); t.SetLayer(lid[s["layer"]]); t.SetNetCode(net(s["net"])); b.Add(t)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pro = sys.argv[3][:-10] + ".kicad_pro"; keep = open(pro, "rb").read() if os.path.exists(pro) else None
b.Save(sys.argv[3])
if keep is not None: open(pro, "wb").write(keep)
print(f"{sys.argv[3]}: {nz} zones (from {len(S['zones'])} planned, one per outline), {len(S['vias'])} vias, {len(S['tracks'])} tracks, filled")
