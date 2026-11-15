"""apply placement.json {ref:[x,y,rot]} to a board (run inside the KiCad container): apply_place.py in.kicad_pcb placement.json out.kicad_pcb"""
import pcbnew,sys,json
b=pcbnew.LoadBoard(sys.argv[1]); P=json.load(open(sys.argv[2])); n=0
for f in b.GetFootprints():
    r=str(f.GetReference())
    if r not in P: print('not in placement',r); continue
    x,y,rot=P[r]
    p=f.GetPosition()
    if abs(p.x/1e6-x)>1e-4 or abs(p.y/1e6-y)>1e-4 or abs((f.GetOrientationDegrees()-rot+180)%360-180)>1e-3:
        f.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x),pcbnew.FromMM(y))); f.SetOrientationDegrees(rot); n+=1
print('moved',n,'of',len(P))
b.Save(sys.argv[3])
