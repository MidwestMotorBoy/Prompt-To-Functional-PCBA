"""inject_zones.py <board.kicad_pcb> <spec.json> <layer> <out.kicad_pcb>  (KiCad python)
Team A strapfix: add the spec's zones on <layer> (e.g. the bus4.py In4 PACK_P zones) to an already ROUTED board,
refill every zone and save. Because router.py never routes on In1/In4, this gives the routed board the In4 copper
would have had, without routing again."""
import sys, os, json, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); S = json.load(open(sys.argv[2])); LAY = sys.argv[3]; FM = pcbnew.FromMM
lid = {pcbnew.BOARD.GetStandardLayerName(l): l for l in b.GetEnabledLayers().CuStack()}
n = 0
for z in S["zones"]:
    if z["layer"] != LAY or z["net"] == "GND": continue
    zn = pcbnew.ZONE(b); zn.SetLayer(lid[LAY]); zn.SetNetCode(b.GetNetcodeFromNetname(z["net"])); zn.SetZoneName("pc_" + z["net"].strip("/").replace("/", "_"))
    o = zn.Outline()
    for p in z["polys"]:
        o.NewOutline(); k = o.OutlineCount() - 1
        for x, y in p["ring"]: o.Append(FM(x), FM(y), k)
        for h in p["holes"]:
            o.NewHole(k)
            for x, y in h: o.Append(FM(x), FM(y), k, o.HoleCount(k) - 1)
    zn.SetAssignedPriority(int(z["priority"])); zn.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL); zn.SetLocalClearance(FM(S.get("clearance_mm", 0.2))); zn.SetMinThickness(FM(0.15))
    zn.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS); b.Add(zn); n += 1
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pro = sys.argv[4][:-10] + ".kicad_pro"; keep = open(pro, "rb").read() if os.path.exists(pro) else None
b.Save(sys.argv[4])
if keep is not None: open(pro, "wb").write(keep)
print("injected", n, "zones on", LAY)
