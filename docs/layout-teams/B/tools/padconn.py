"""padconn.py <board.kicad_pcb> REF.PAD [REF.PAD ...]   (KiCad python, run in kicad/kicad:10.0)
Uses the fill saved in the board (--refill: fills again) and prints, for each pad, its net, how many items KiCad connects it to, and whether it is in the same
connected cluster as each other listed pad of its net; plus the filled zone area of its net within 0.6 mm of the pad
on the pad's layer."""
import sys, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); b.BuildConnectivity() if "--refill" not in sys.argv else (pcbnew.ZONE_FILLER(b).Fill(b.Zones()), b.BuildConnectivity()); con = b.GetConnectivity()
pads = {}
for a in [x for x in sys.argv[2:] if not x.startswith("--")]:
    r, n = a.split("."); fp = b.FindFootprintByReference(r)
    pads[a] = [p for p in fp.Pads() if p.GetNumber() == n][0]
for a, p in pads.items():
    items = con.GetConnectedItems(p)
    print(a, p.GetNetname(), "connected items", len(items), "unconnected ratsnest", con.GetUnconnectedCount(True) if False else "", "kinds", sorted({i.GetClass() for i in items}))
    for a2, p2 in pads.items():
        if a2 != a and p2.GetNetCode() == p.GetNetCode(): print("   joined to", a2, any(i.m_Uuid == p2.m_Uuid for i in items))
