from placelib import *
P=start()
EXPL=globals().get('EXPL',{})   # hand-placed parts, recorded on the first run and reserved on the second
P.update(globals().get('RESERVE',{}))
def put(ref,x,y,rot=0): P[ref]=(round(x,3),round(y,3),rot); EXPL[ref]=P[ref]
import placelib as _plr
_plr.RINGS.update({'U401':1.2,'U501':1.2,'U102':0.9,'U101':0.6,'U404':0.5,'U504':0.5,'U405':0.6,'U505':0.6})
# ---------------- port 1 power stage (port 2 = translate by DX2) ----------------
DX2=88.785-111.811
S={}   # port-1 stage parts that port 2 copies by translation
def sp(ref,x,y,rot=0): S[ref]=(x,y,rot)
UY=111.24                                  # BQ25756, 0.8 mm lower than the old board: room for the gate fan-out
sp('Q401',109.55,99.80,180); sp('Q402',114.05,99.80,180)
sp('C430',111.81,97.32,0); sp('TH401',109.55,102.78,90); sp('C438',115.3,97.32,0)
sp('U403',110.84,UY,90)
# AC column: four 1210 lying down, + pad toward the stage
for i,r in enumerate(('C420','C423','C424','C427')): sp(r,104.96,100.10-3.28*i,180)
# BAT column
sp('C431',118.61,100.10,0); sp('C434',118.61,96.82,0)
sp('R427',118.45,104.10,-90)
# gate drive
sp('R445',107.93,102.70,90); sp('R444',111.19,102.70,90); sp('R447',112.43,102.70,90); sp('R446',115.69,102.70,90)
sp('C412',109.59,107.0,180); sp('C413',113.29,107.25,90)
sp('C411',111.64,106.35,90); sp('C410',111.67,104.13,0)
for r,v in S.items():
    put(r,*v); put(port2(r),v[0]+DX2,v[1],v[2])
if __name__=='__main__':
    pass
    show(P,'img/p_stage1.png',(100,86,122,118),70,padnames=True,netlabels=True)
