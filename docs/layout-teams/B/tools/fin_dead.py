"""fin_dead.py <board in> <pieces.json of tools/fin_islands.py --out> <board out>      (KiCad python, kicad/kicad:10.0)
(team B, finishing pass, phase 2 round 2) Removes the dead power copper that tools/fin_islands.py found: every track and
via of a piece that holds no pad (kind "dead": a strap end the router cut off, a slab hanging on one via). Items are
matched by net and geometry (1 um). Then every zone is refilled (a fill island that only that copper held goes too)
and the board is saved. Pieces that hold pads are never touched. Prints 'fin_dead: removed N tracks, M vias'."""
import sys, json
import pcbnew

pin, pj, pout = sys.argv[1:4]
b = pcbnew.LoadBoard(pin); MM = pcbnew.ToMM
P = [p for p in json.load(open(pj))["pieces"] if p["kind"] == "dead"]
want_t = {(p["net"], t["layer"], round(t["a"][0], 3), round(t["a"][1], 3), round(t["b"][0], 3), round(t["b"][1], 3)) for p in P for t in p["tracks"]}
want_t |= {(n, L, c, d, a, bb) for n, L, a, bb, c, d in want_t}
want_v = {(p["net"], round(v["x"], 3), round(v["y"], 3)) for p in P for v in p["vias"]}
nt = nv = 0
for t in list(b.GetTracks()):
    if t.GetClass() == "PCB_VIA":
        c = t.GetPosition()
        if (t.GetNetname(), round(MM(c.x), 3), round(MM(c.y), 3)) in want_v:
            b.Remove(t); nv += 1
    else:
        s, e = t.GetStart(), t.GetEnd()
        if (t.GetNetname(), b.GetLayerName(t.GetLayer()), round(MM(s.x), 3), round(MM(s.y), 3), round(MM(e.x), 3), round(MM(e.y), 3)) in want_t:
            b.Remove(t); nt += 1
b.BuildConnectivity(); pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.BuildConnectivity()
b.Save(pout)
print("fin_dead: removed %d tracks, %d vias of %d dead pieces" % (nt, nv, len(P)))
