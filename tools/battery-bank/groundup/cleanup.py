"""Remove router-laid tracks / vias that a DRC report flags (run with KiCad's python).
  cleanup.py in.kicad_pcb out.kicad_pcb drc.json keep.kicad_pcb [--errors]
Dangling tracks and vias always go; with --errors also the router items named in clearance, hole, edge and keep-out
errors. Anything that is also in keep.kicad_pcb (the board before signal routing: hand copper) is never touched.
Zones are refilled. Run DRC again afterwards: removing a piece can leave the next piece dangling."""
import sys, json
import pcbnew
src, dst, drcf, keepf = sys.argv[1:5]
ERR = ("clearance", "hole_clearance", "copper_edge_clearance", "items_not_allowed", "shorting_items", "tracks_crossing", "hole_to_hole")
kinds = ("track_dangling", "via_dangling") + (ERR if "--errors" in sys.argv else ())
keep = {t.m_Uuid.AsString() for t in pcbnew.LoadBoard(keepf).GetTracks()}
b = pcbnew.LoadBoard(src)
tr = {t.m_Uuid.AsString(): t for t in b.GetTracks()}
gone = {}
for v in json.load(open(drcf))["violations"]:
    if v["type"] in kinds:
        for it in v["items"]:
            u = it["uuid"]
            if u in tr and u not in keep and u not in gone:
                gone[u] = v["type"]
for u in gone:
    b.Remove(tr[u])
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(dst)
import collections
open(dst + ".cleanup.txt", "w").write("removed %d %s\n" % (len(gone), dict(collections.Counter(gone.values()))))
