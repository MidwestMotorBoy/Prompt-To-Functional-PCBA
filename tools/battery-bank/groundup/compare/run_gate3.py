"""Gate-drive loop inductance, both boards with one method: model box = driver + resistor + FET + the whole drive net;
ground kept within COR mm of the loop's own copper, on the same layer and on the ground plane next to it."""
import json, pickle, os, time, numpy as np
from scipy import ndimage
from loops import *
from peec import Model
from run_all_defs import GATES
from gbox import gbox
TAG=os.environ['TAG']; COR=2.0; MAXBR=int(os.environ.get('MAXBR','30000')); BOTH=os.environ.get('BOTH')=='1'; ONLY=os.environ.get('ONLY'); SUF=os.environ.get('SUF','')
def gate_loop2(name, box, nets, U, drvpin, retpins, R, Q, qpads, h=0.15):
    t0=time.time()
    m=Model(box,nets,h=h,top=[x for x in nets if x!='GND'])
    gid=m.nid['GND']
    ADJ={'F.Cu':('F.Cu','In1.Cu'),'In1.Cu':('In1.Cu',),'In2.Cu':('In1.Cu','In2.Cu'),'In3.Cu':('In3.Cu','In4.Cu'),'In4.Cu':('In4.Cu',),'B.Cu':('In4.Cu','B.Cu')}
    keep={L:np.zeros((m.H,m.W),bool) for L in m.layers}
    for Ls in m.layers:
        seed=(np.asarray(m.lab[Ls])>0)&(np.asarray(m.lab[Ls])!=gid)
        if Ls=='F.Cu':
            for ref in (U,R,Q):
                for p in REF[ref]['pads']:
                    c=m.P(p['x'],p['y']); ci,ri=int(c[0]),int(c[1])
                    if 0<=ri<m.H and 0<=ci<m.W: seed[ri,ci]=True
        if not seed.any(): continue
        near=ndimage.distance_transform_edt(~seed)*h<=COR
        for Lg in ADJ[Ls]+(('In1.Cu','In4.Cu') if BOTH else ()): keep[Lg]|=near
    for L in m.layers: m.lab[L][(m.lab[L]==gid)&~keep[L]]=0
    groups={'P':[(U,[drvpin])],'N':[(U,retpins)],'R':[(R,['1','2'])],'F':[(Q,qpads)]}
    m.build(groups)
    if len(m.br)>MAXBR: return None,len(m.br),None
    m.K()
    L_=m.solve(('P','N'),[])
    mo,I=m.moment(m.phi,[('N','P',1.0,-0.3)])
    return {'name':name,'L':L_,'area':mo.tolist(),'nodes':m.N,'branches':len(m.br),'t':time.time()-t0},m,I
fn='gate3%s_%s.json'%(SUF,TAG); fm='gate3maps%s_%s.pkl'%(SUF,TAG)
res=json.load(open(fn)) if os.path.exists(fn) else {}; maps=pickle.load(open(fm,'rb')) if os.path.exists(fm) else {}
for name,nets,U,dp,rp,R,Q,qp in GATES:
    if name in res and name in maps: continue
    if ONLY and not any(x in name for x in ONLY.split(',')): continue
    box,_,_=gbox(nets,U,R,Q)
    hh=0.15
    while True:
        o,m,I=gate_loop2(name,box,nets,U,dp,rp,R,Q,qp,h=hh)
        if o is not None: break
        print(f"{name}: {m} branches at h={hh}, coarsening",flush=True); hh=round(hh+0.025,3)
    o['h']=hh
    a=np.array(o['area']); o['box']=box
    print(f"{name}: L={o['L']*1e9:.2f} nH |A|={np.linalg.norm(a):.2f} mm2 (Az {a[2]:.2f}, vert {np.hypot(a[0],a[1]):.2f}) N={o['nodes']} {o['t']:.0f}s",flush=True)
    res[name]=o; maps[name]={'box':m.box,'h':m.h,'map':currmap(m,I)}
    del m
    json.dump(res,open(fn,'w'),indent=1,default=float); pickle.dump(maps,open(fm,'wb'))
