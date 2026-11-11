"""Placement helpers: P = {ref: (x, y, rot)}; check() finds courtyard overlaps and keep-out hits; show() renders."""
import json, math, re
from fpdb import DB
import render
db=DB('base.json')
EDGE=(78.4,62.8245,121.6,137.175)
LIP_Y=114.475          # F.Cu lips over the long edges for y < this (pack z >= 27)
LIP_X=(79.4,120.96)     # keep part courtyards inside this where the lips run
PEGS=[(91.4,73.475),(108.6,73.475),(91.4,127.475),(108.6,127.475)]
PEG_R=2.2
FIXED=[r for r,f in db.fp.items() if f['locked'] or f['layer']=='B.Cu' or r in('J113','J114','J117','J118','J119','J120','U301','L401','L501','J301','J302','C313','C314','C315','R321','C301','C302','C303','R304')]
def start():
    return {r:db.fp[r]['base'] for r in FIXED}
def port2(ref):
    m=re.match(r'([A-Z]+)4(\d\d)$',ref); return f'{m.group(1)}5{m.group(2)}'
def world(P): return {r:db.world(r,*P[r]) for r in P}
def check(P,verbose=True):
    Wd=world(P); errs=[]
    refs=[r for r in Wd]
    F=[r for r in refs if Wd[r]['layer']=='F.Cu']; B=[r for r in refs if Wd[r]['layer']=='B.Cu']
    for grp in (F,B):
        for i,a in enumerate(grp):
            A=Wd[a]['bb']
            for b in grp[i+1:]:
                Bb=Wd[b]['bb']
                ox=min(A[2],Bb[2])-max(A[0],Bb[0]); oy=min(A[3],Bb[3])-max(A[1],Bb[1])
                if ox>0.08 and oy>0.08 and not (a in FIXED and b in FIXED): errs.append(f'overlap {a}/{b} {ox:.2f}x{oy:.2f}')
    for r in F:
        if r in FIXED: continue
        bb=Wd[r]['bb']
        if r.startswith('TP'): lim=(78.9,121.1)
        else: lim=LIP_X if bb[1]<LIP_Y else (78.8,121.2)
        if bb[0]<lim[0]-1e-6 or bb[2]>lim[1]+1e-6: errs.append(f'edge-x {r} {bb[0]:.2f}..{bb[2]:.2f}')
        if bb[1]<63.9 or bb[3]>136.8: errs.append(f'edge-y {r}')
        if bb[3]>132.375-0.4 and (bb[0]<83.4+0.4 or bb[2]>116.6-0.4): errs.append(f'notch {r}')
        for px,py in PEGS:
            dx=max(bb[0]-px,0,px-bb[2]); dy=max(bb[1]-py,0,py-bb[3])
            if math.hypot(dx,dy)<PEG_R: errs.append(f'peg {r} {math.hypot(dx,dy):.2f}')
    missing=[r for r in db.fp if r not in P]
    if verbose:
        for e in errs: print('  !',e)
        print(f'  placed {len(P)}/{len(db.fp)}, missing {len(missing)}: {" ".join(sorted(missing))[:600]}')
    return errs,missing
def show(P,out,box=None,scale=30,padnames=False,netlabels=False,side='F',extra=None):
    Wd=world(P)
    d=dict(fps=list(Wd.values()),zones=db.d['zones'])
    render.render(d,out,box,side,scale,padnames=padnames,netlabels=netlabels,extra=extra)
def pad(P,ref,n): return db.pad(P,ref,n)

# ---------------- greedy auto-placer ----------------
import numpy as np
BIG={'GND','PACK_P','3V3'}
def _padpts(P,nets_only=None):
    out={}
    for r,(x,y,rot) in P.items():
        for p in db.fp[r]['pads']:
            if not p['net'] or (r,) is None: continue
            dx,dy=__import__('fpdb').rotv(p['lx'],p['ly'],rot)
            out.setdefault(p['net'],[]).append((x+dx,y+dy,r,p['n']))
    return out
def auto(P,ref,at=None,**k):
    for R in (k.pop('R',4.0),8.0,14.0):
        try: return _auto(P,ref,at,R=R,**k)
        except RuntimeError as e: err=e
    raise err
import os
KEEPV=[(x-0.4,y-0.4,x+0.4,y+0.4) for x,y in json.load(open('keep_vias.json'))] if os.path.exists('keep_vias.json') else []   # hand-placed via spots: no automatic part on them
GHOST=[]      # extra blocked boxes (port 1 spots whose port 2 copy would land on a part)
GAP=float(os.environ.get('GAP','0')); RING=float(os.environ.get('RING','0'))
RINGS={}   # per-part clear band (mm) round an IC, overrides RING; small ICs (5..12 pads) only get a band through this
def _auto(P,ref,at=None,pins=None,rots=(0,90,180,270),R=4.0,grid=0.05,gap=None,box=None,wpull=0.15,big=(),verbose=True):
    """place ref at the free spot that minimises the Manhattan distance of its pads to their nets on placed parts.
    at=(x,y) or 'REF.pad': search centre (default: centroid of the connected pads). pins={padnum:'REF.pad' or (x,y)}:
    explicit per-pad targets (replace the automatic ones). big: nets from BIG to pull to anyway. box=(x0,y0,x1,y1) limit."""
    from fpdb import rotv
    f=db.fp[ref]; nets=_padpts(P)
    def res(t):
        if isinstance(t,str):
            r,n=t.split('.'); return pad(P,r,n)
        return t
    targets=[]   # (lx,ly,[pts]) per pad
    for p in f['pads']:
        if pins and p['n'] in pins:
            targets.append((p['lx'],p['ly'],np.array([res(pins[p['n']])]),1.0)); continue
        if pins and p['n'] not in pins and not p['net']: continue
        if not p['net'] or (p['net'] in BIG and p['net'] not in big) or p['net'].startswith('unconnected'): continue
        pts=[(a,b) for a,b,r,n in nets.get(p['net'],[]) if r!=ref]
        if pts: targets.append((p['lx'],p['ly'],np.array(pts),1.0))
    if at is None:
        if not targets: raise ValueError(f'{ref}: no anchors, give at=')
        c=np.mean([t[2].mean(0) if len(t[2])<3 else t[2][0] for t in targets],0); at=(float(c[0]),float(c[1]))
    at=res(at)
    xs=np.arange(-R,R+1e-9,grid); gx,gy=np.meshgrid(xs,xs); gx=gx.ravel()+round(at[0]/grid)*grid; gy=gy.ravel()+round(at[1]/grid)*grid
    lay=f['layer']
    others=[(r,db.world(r,*P[r])['bb']) for r in P if r!=ref and db.fp[r]['layer']==lay]
    others+=[('ghost',b) for b in GHOST]
    others+=[('via',b) for b in KEEPV]
    if gap is None: gap=GAP if re.match(r'(R|C|D|TH|Q[^4-5])',ref) else 0.0
    _rg=lambda r: RINGS.get(r,RING if (re.match(r'U\d+$',r) and len(db.fp[r]['pads'])>12) else 0.0)
    others=[(r,(b[0]-_rg(r),b[1]-_rg(r),b[2]+_rg(r),b[3]+_rg(r))) for r,b in others]
    ob=np.array([b for _,b in others]) if others else np.zeros((0,4))
    best=None
    for rot in rots:
        b=f['box']; cs=[rotv(cx,cy,rot) for cx,cy in((b[0],b[1]),(b[2],b[1]),(b[2],b[3]),(b[0],b[3]))]
        x0=gx+min(c[0] for c in cs)-gap; x1=gx+max(c[0] for c in cs)+gap; y0=gy+min(c[1] for c in cs)-gap; y1=gy+max(c[1] for c in cs)+gap
        ok=np.ones(len(gx),bool)
        for k in range(0,len(ob)):
            o=ob[k]
            ok&=~((np.minimum(x1,o[2])-np.maximum(x0,o[0])>0.05)&(np.minimum(y1,o[3])-np.maximum(y0,o[1])>0.05))
        tp=ref.startswith('TP')
        lx0=np.where(y0<LIP_Y,78.9 if tp else LIP_X[0],78.8); lx1=np.where(y0<LIP_Y,121.1 if tp else LIP_X[1],121.2)
        ok&=(x0+gap>=lx0)&(x1-gap<=lx1)&(y0+gap>=63.9)&(y1-gap<=136.8)
        ok&=~((y1-gap>132.375-0.4)&((x0+gap<83.4+0.4)|(x1-gap>116.6-0.4)))
        for px,py in PEGS:
            dx=np.maximum(np.maximum(x0+gap-px,0),px-(x1-gap)); dy=np.maximum(np.maximum(y0+gap-py,0),py-(y1-gap))
            ok&=np.hypot(dx,dy)>=PEG_R
        if box: ok&=(x0+gap>=box[0])&(y0+gap>=box[1])&(x1-gap<=box[2])&(y1-gap<=box[3])
        cost=wpull*(np.abs(gx-at[0])+np.abs(gy-at[1])) if (pins is None and targets) else 0.02*(np.abs(gx-at[0])+np.abs(gy-at[1]))
        if not targets: cost=np.abs(gx-at[0])+np.abs(gy-at[1])
        for lx,ly,pts,w in targets:
            dx,dy=rotv(lx,ly,rot); px=gx+dx; py=gy+dy
            d=np.min(np.abs(px[:,None]-pts[None,:,0])+np.abs(py[:,None]-pts[None,:,1]),axis=1)
            cost=cost+w*d
        cost=np.where(ok,cost,1e9); i=int(np.argmin(cost))
        if cost[i]<1e9 and (best is None or cost[i]<best[0]-1e-6): best=(float(cost[i]),round(float(gx[i]),3),round(float(gy[i]),3),rot)
    if best is None: raise RuntimeError(f'{ref}: no free spot near {at}')
    P[ref]=best[1:]
    if verbose: print(f'  auto {ref} -> {best[1:]} cost {best[0]:.2f}')
    return best
