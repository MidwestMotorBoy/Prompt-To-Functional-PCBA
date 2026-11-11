"""pinfix.py in.kicad_pcb out.kicad_pcb drc.json (KiCad python)
Fine-pitch pins of a high-current-class net next to a small-signal pin: two tracks that both start at their pad centres are
closer than the 0.25 mm 'HighCurrent copper to small signals' rule although nothing can be done about the pads themselves.
For every such violation between two tracks, each track end that sits inside a pad of its own net is slid along the track
toward the pad edge (it stays inside the pad, so it stays connected); a segment lying wholly inside the pad is removed."""
import sys, json, math
import pcbnew
mm, MM = pcbnew.FromMM, pcbnew.ToMM
b = pcbnew.LoadBoard(sys.argv[1]); d = json.load(open(sys.argv[3]))
tr = {t.m_Uuid.AsString(): t for t in b.GetTracks() if t.GetClass() == "PCB_TRACK"}
pads = [p for f in b.GetFootprints() for p in f.Pads()]
def inside(p, x, y, m):
    return all(p.HitTest(pcbnew.VECTOR2I(mm(x + dx), mm(y + dy))) for dx, dy in ((0, 0), (m, 0), (-m, 0), (0, m), (0, -m)))
done = set(); nmove = nrem = nthin = 0
for v in d.get("violations", []):
    if v["type"] != "clearance" or "HighCurrent copper to small signals" not in v["description"]:
        continue
    for it in v["items"]:
        u = it["uuid"]
        if u in done or u not in tr:
            continue
        done.add(u); t = tr[u]
        P = [(MM(t.GetStart().x), MM(t.GetStart().y)), (MM(t.GetEnd().x), MM(t.GetEnd().y))]
        m = MM(t.GetWidth()) / 2 - 0.02
        for k in (0, 1):
            a, c = P[k], P[1 - k]
            pad = next((p for p in pads if p.GetNetCode() == t.GetNetCode() and p.IsOnLayer(t.GetLayer()) and inside(p, a[0], a[1], 0.0)), None)
            if pad is None:
                continue
            if inside(pad, c[0], c[1], m):
                b.Remove(t); nrem += 1; break
            lo, hi = 0.0, 1.0
            for _ in range(20):
                mid = (lo + hi) / 2
                if inside(pad, a[0] + (c[0] - a[0]) * mid, a[1] + (c[1] - a[1]) * mid, m): lo = mid
                else: hi = mid
            if lo * math.hypot(c[0] - a[0], c[1] - a[1]) < 0.03:      # cannot slide (leaves the pad sideways): make it thin instead
                if MM(t.GetWidth()) > 0.16:
                    t.SetWidth(mm(0.15)); nthin += 1
                break
            q = pcbnew.VECTOR2I(mm(a[0] + (c[0] - a[0]) * lo), mm(a[1] + (c[1] - a[1]) * lo))
            (t.SetStart if k == 0 else t.SetEnd)(q); nmove += 1
            break
b.BuildConnectivity(); pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[2])
print("pin-end tracks moved %d, removed %d, thinned %d" % (nmove, nrem, nthin))
