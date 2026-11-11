"""chainp.py board netregex : print the net's tracks as ordered polylines per layer, with vias (KiCad python)"""
import sys, re, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); rx = re.compile(sys.argv[2]); M = pcbnew.ToMM
segs = []; 
for t in b.GetTracks():
    if not rx.search(t.GetNetname()): continue
    if t.GetClass() == "PCB_VIA": print("V %.3f,%.3f" % (M(t.GetPosition().x), M(t.GetPosition().y)))
    else: segs.append([b.GetLayerName(t.GetLayer())[:3], (round(M(t.GetStart().x), 3), round(M(t.GetStart().y), 3)), (round(M(t.GetEnd().x), 3), round(M(t.GetEnd().y), 3)), M(t.GetWidth())])
while segs:
    l, a, c, w = segs.pop(0); line = [a, c]; grew = True
    while grew:
        grew = False
        for s in segs:
            if s[0] != l: continue
            for p, q in ((s[1], s[2]), (s[2], s[1])):
                if p == line[-1]: line.append(q); segs.remove(s); grew = True; break
                if p == line[0]: line.insert(0, q); segs.remove(s); grew = True; break
            if grew: break
    print(l, "w%.2f" % w, " ".join("%.3f,%.3f" % p for p in line))
