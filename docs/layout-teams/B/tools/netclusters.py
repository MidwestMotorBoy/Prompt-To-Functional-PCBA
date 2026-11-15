"""netclusters.py <board.kicad_pcb> <net substring> [...] [--refill]   (KiCad python, run in kicad/kicad:10.0)
For each net that matches: the copper clusters KiCad's connectivity sees (pads, vias, track count and zone islands
per cluster), so a power net "in pieces" on the unconnected list can be traced to the piece that is cut off.
Uses the fill saved in the board (--refill fills again first)."""
import sys, pcbnew
args = [a for a in sys.argv[1:] if not a.startswith("--")]
b = pcbnew.LoadBoard(args[0])
if "--refill" in sys.argv: pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.BuildConnectivity(); con = b.GetConnectivity(); MM = pcbnew.ToMM
for want in args[1:]:
    nets = sorted({p.GetNetname() for p in b.GetPads() if p.GetNetname() == want or p.GetNetname().endswith(want)})
    for n in nets:
        items = [p for p in b.GetPads() if p.GetNetname() == n] + [t for t in b.GetTracks() if t.GetNetname() == n] + [z for z in b.Zones() if z.GetNetname() == n and not z.GetIsRuleArea()]
        uid = {i.m_Uuid.AsString(): k for k, i in enumerate(items)}
        par = list(range(len(items)))
        def f(x):
            while par[x] != x: par[x] = par[par[x]]; x = par[x]
            return x
        for k, i in enumerate(items):
            for j in con.GetConnectedItems(i):
                q = uid.get(j.m_Uuid.AsString())
                if q is not None: par[f(k)] = f(q)
        cl = {}
        for k, i in enumerate(items): cl.setdefault(f(k), []).append(i)
        print("%s: %d clusters" % (n, len(cl)))
        for c in sorted(cl.values(), key=len, reverse=True):
            pads = ["%s.%s" % (i.GetParentFootprint().GetReference(), i.GetNumber()) for i in c if i.GetClass() == "PAD"]
            vias = ["%.2f,%.2f" % (MM(i.GetPosition().x), MM(i.GetPosition().y)) for i in c if i.GetClass() == "PCB_VIA"]
            trk = sum(1 for i in c if i.GetClass() in ("PCB_TRACK", "PCB_ARC"))
            zs = ["%s@%s" % (b.GetLayerName(i.GetFirstLayer()), "%.1f,%.1f" % (MM(i.GetBoundingBox().GetCenter().x), MM(i.GetBoundingBox().GetCenter().y))) for i in c if i.GetClass() == "ZONE"]
            print("   cluster: %d pads %s | %d vias %s | %d tracks | zones %s" % (len(pads), " ".join(pads[:14]), len(vias), " ".join(vias[:6]), trk, " ".join(zs[:6])))
