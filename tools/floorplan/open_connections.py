"""open_connections.py <board.kicad_pcb> <drc.json>      (KiCad's python: needs pcbnew)
kicad-cli's DRC report lists at most 499 unconnected items, so on a bare board (710 connections on Monolith) a router
that reads its work list from the report silently misses the rest. This replaces the report's unconnected_items with
the full list for a board that has no copper: per net, a minimum spanning tree over pad positions, written in the
report's own format. Pads of one part with the same number count as one point (the largest pad is used)."""
import sys, json, math, collections, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); mm = pcbnew.ToMM; nets = collections.defaultdict(dict)
for f in b.GetFootprints():
    for p in f.Pads():
        n = p.GetNetname()
        if not n: continue
        pth = p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH; lay = "F.Cu" if p.IsOnLayer(pcbnew.F_Cu) else "B.Cu"
        desc = (f"PTH pad {p.GetNumber()} [{n}] of {f.GetReference()}" if pth else f"Pad {p.GetNumber()} [{n}] of {f.GetReference()} on {lay}")
        area = p.GetSize().x * p.GetSize().y; key = (f.GetReference(), p.GetNumber()); old = nets[n].get(key)
        if old is None or (not pth and old[4]) or (pth == old[4] and area > old[0]):
            if old is None or not (pth and not old[4]): nets[n][key] = (area, mm(p.GetPosition().x), mm(p.GetPosition().y), desc, pth)
items = []
for n, pads in sorted(nets.items()):
    P = list(pads.values())
    if len(P) < 2: continue
    inT = [0]; best = {j: (math.hypot(P[j][1] - P[0][1], P[j][2] - P[0][2]), 0) for j in range(1, len(P))}
    while best:
        j = min(best, key=lambda q: best[q][0]); d, i = best.pop(j)
        items.append(dict(description="Missing connection between items", severity="error", type="unconnected_items",
                          items=[dict(description=P[i][3], pos=dict(x=P[i][1], y=P[i][2])), dict(description=P[j][3], pos=dict(x=P[j][1], y=P[j][2]))]))
        for q in best:
            dq = math.hypot(P[q][1] - P[j][1], P[q][2] - P[j][2])
            if dq < best[q][0]: best[q] = (dq, j)
d = json.load(open(sys.argv[2])); was = len(d.get("unconnected_items", [])); d["unconnected_items"] = items
json.dump(d, open(sys.argv[2], "w")); print(f"{sys.argv[2]}: {was} unconnected items in the report, {len(items)} written")
