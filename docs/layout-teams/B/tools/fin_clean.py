"""fin_clean.py <board in> <keep board> <drc.json of board in> <board out>      (team B, finishing pass; KiCad's python)
Removes the dangling ends the router left: every track or via that KiCad DRC reports as track_dangling / via_dangling
and that is not in the keep board (the planned copper before routing, matched by uuid). A dangling end touches
nothing at that end, so taking it away disconnects nothing (finish.sh still checks the unconnected count after it).
Then refills every zone and saves. Prints 'removed <n>'."""
import sys, json
import pcbnew

pin, keep, drc, pout = sys.argv[1:5]
b = pcbnew.LoadBoard(pin)
ku = {t.m_Uuid.AsString() for t in pcbnew.LoadBoard(keep).GetTracks()}
dj = json.load(open(drc))
bad = {i["uuid"] for v in dj["violations"] if v["type"] in ("track_dangling", "via_dangling") for i in v["items"]}
n = 0
for t in list(b.GetTracks()):
    u = t.m_Uuid.AsString()
    if u in bad and u not in ku:
        b.Remove(t); n += 1
b.BuildConnectivity(); pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.BuildConnectivity()
b.Save(pout)
print("removed %d" % n)
