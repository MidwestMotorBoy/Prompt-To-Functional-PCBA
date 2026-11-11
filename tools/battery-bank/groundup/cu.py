"""copper description helpers: Z (zone), T (track), V (via), VG (via grid) -> copper.json"""
import json,math
from fpdb import DB
ITEMS=[]
P=json.load(open('placement.json'))
db=DB('base.json')
DX2=88.785-111.811
def pad(ref,n):
    return db.pad(P,ref,n)
def padbox(ref,n):
    """(x0,y0,x1,y1) of pad n of ref (first match)"""
    w=db.world(ref,*P[ref])
    for p in w['pads']:
        if p['n']==str(n): return (p['x']-p['sx']/2,p['y']-p['sy']/2,p['x']+p['sx']/2,p['y']+p['sy']/2)
    raise KeyError((ref,n))
def rect(x0,y0,x1,y1): return [(x0,y0),(x1,y0),(x1,y1),(x0,y1)]
def Z(net,layers,pts,prio=10,clr=0.25,minw=0.25,name='',dx=0,holes=None,islands='remove'):
    if isinstance(layers,str): layers=[layers]
    ITEMS.append(dict(k='zone',net=net,layers=layers,pts=[(round(x+dx,4),round(y,4)) for x,y in pts],prio=prio,clr=clr,minw=minw,name=name,islands=islands,
                      holes=[[(round(x+dx,4),round(y,4)) for x,y in h] for h in (holes or [])]))
def T(net,layer,pts,w=0.2,dx=0):
    ITEMS.append(dict(k='track',net=net,layer=layer,pts=[(round(x+dx,4),round(y,4)) for x,y in pts],w=w))
def V(net,x,y,d=0.45,drill=0.3,dx=0):
    ITEMS.append(dict(k='via',net=net,x=round(x+dx,4),y=round(y,4),d=d,drill=drill))
def VG(net,x0,y0,x1,y1,px=1.0,py=None,d=0.45,drill=0.3,dx=0,stagger=False):
    py=py or px; nx=int((x1-x0)/px+1e-6)+1; ny=int((y1-y0)/py+1e-6)+1
    ox=(x1-x0-(nx-1)*px)/2; oy=(y1-y0-(ny-1)*py)/2
    for j in range(ny):
        for i in range(nx):
            xx=x0+ox+i*px+(px/2 if stagger and j%2 else 0)
            if xx>x1+1e-6: continue
            V(net,xx,y0+oy+j*py,d,drill,dx)
def save(path='copper.json'):
    json.dump(ITEMS,open(path,'w')); print('copper items',len(ITEMS))

# ---- via helper with pad / via / hole checks -------------------------------------------------------------------
import numpy as np
_W={r:db.world(r,*P[r]) for r in P}
PADS=[]   # (x0,y0,x1,y1,net,layers)
for r,w in _W.items():
    for p in w['pads']:
        lay='FB' if p['drill']>0 else w['layer'][0]
        if p['n']=='' and p['drill']==0: continue      # paste-only apertures
        PADS.append((p['x']-p['sx']/2,p['y']-p['sy']/2,p['x']+p['sx']/2,p['y']+p['sy']/2,p['net'],lay,r,p['n'],p['drill']))
VIAS=[]   # (x,y,d,net)
HOLES=[(p[0]+(p[2]-p[0])/2,p[1]+(p[3]-p[1])/2,p[8]) for p in PADS if p[8]>0]
_V0=V
def via_ok(net,x,y,d=0.45,clr=0.2,vv=0.2):
    r=d/2
    if not (78.4+0.3+r<x<121.6-0.3-r and 62.8245+0.3+r<y<137.175-0.3-r): return False
    if y>132.375-0.3-r and (x<83.4+0.3+r or x>116.6-0.3-r): return False
    if 118.12-0.3-r<x<121.32+0.3+r and 119.88-0.3-r<y<125.28+0.3+r: return False     # antenna
    for x0,y0,x1,y1,n,lay,ref,pn,dr in PADS:
        if x0-r-0.6<x<x1+r+0.6 and y0-r-0.6<y<y1+r+0.6:
            dx=max(x0-x,0,x-x1); dy=max(y0-y,0,y-y1); dist=math.hypot(dx,dy)
            if n!=net and dist<r+clr: return False
            if n==net and dr>0 and dist<r+0.25: return False
            if n=='' and dist<r+0.3: return False
    for vx,vy,vd,vn in VIAS:
        if math.hypot(vx-x,vy-y)<(vd+d)/2+ (vv if vn!=net else 0.15): return False
    return True
def V(net,x,y,d=0.45,drill=0.3,dx=0,check=True):
    x+=dx
    if check and not via_ok(net,x,y,d):
        print('  via dropped (no room):',net,round(x,3),round(y,3)); return False
    VIAS.append((x,y,d,net)); _V0(net,x,y,d,drill); return True
def VG(net,x0,y0,x1,y1,px=1.0,py=None,d=0.45,drill=0.3,dx=0,stagger=False):
    py=py or px; nx=int((x1-x0)/px+1e-6)+1; ny=int((y1-y0)/py+1e-6)+1; n=0
    ox=(x1-x0-(nx-1)*px)/2; oy=(y1-y0-(ny-1)*py)/2
    for j in range(ny):
        for i in range(nx):
            xx=x0+ox+i*px+(px/2 if stagger and j%2 else 0)
            if xx>x1+1e-6: continue
            n+=bool(V(net,xx,y0+oy+j*py,d,drill,dx))
    return n
def KO(layers,pts,name='',dx=0):
    if isinstance(layers,str): layers=[layers]
    ITEMS.append(dict(k='ko',layers=layers,pts=[(round(x+dx,4),round(y,4)) for x,y in pts],name=name))
