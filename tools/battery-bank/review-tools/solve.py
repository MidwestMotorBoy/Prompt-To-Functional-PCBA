import math, numpy as np, scipy.sparse as sp, scipy.sparse.linalg as sla
from PIL import Image, ImageDraw
from board import *
LAYERS=['F.Cu','In1.Cu','In2.Cu','In3.Cu','In4.Cu','B.Cu']
RS={'F.Cu':0.246e-3,'B.Cu':0.246e-3,'In1.Cu':0.983e-3,'In2.Cu':0.983e-3,'In3.Cu':0.983e-3,'In4.Cu':0.983e-3}
ZPOS={'F.Cu':0,'In1.Cu':0.27,'In2.Cu':0.59,'In3.Cu':1.0,'In4.Cu':1.32,'B.Cu':1.59}
VIA_R_PER_MM=1.72e-8*1e-3/(math.pi*0.32*0.02*1e-6)  # ohm per mm length for 0.3 drill, 20um plating
def padpoly(p):
    a=math.radians(-p['rot']); w,h=p['w']/2,p['h']/2
    return [(p['x']+dx*math.cos(a)-dy*math.sin(a),p['y']+dx*math.sin(a)+dy*math.cos(a)) for dx,dy in((-w,-h),(w,-h),(w,h),(-w,h))]
def padlayers(p):
    if '*.Cu' in p['layers']: return LAYERS
    return [l for l in p['layers'] if l in LAYERS]
def build(net,box,res=0.1):
    x0,x1,y0,y1=box; W=int((x1-x0)/res)+1; H=int((y1-y0)/res)+1
    def P(x,y): return ((x-x0)/res,(y-y0)/res)
    masks={}
    for L in LAYERS:
        im=Image.new('L',(W,H),0); d=ImageDraw.Draw(im)
        for z in ZON:
            if z['net']!=net: continue
            for LL,pts in z['fills']:
                if LL==L: d.polygon([P(*q) for q in pts],fill=1)
        for s in SEG:
            if s['net']==net and s['layer']==L:
                w=s['w']/res; a=P(s['x1'],s['y1']); b=P(s['x2'],s['y2'])
                d.line([a,b],fill=1,width=max(1,int(round(w))))
                r=w/2; 
                for q in (a,b): d.ellipse([q[0]-r,q[1]-r,q[0]+r,q[1]+r],fill=1)
        for fp in FP:
            for p in fp['pads']:
                if p['net']==net and L in padlayers(p):
                    if p['shape']=='circle':
                        c=P(p['x'],p['y']); r=p['w']/2/res; d.ellipse([c[0]-r,c[1]-r,c[0]+r,c[1]+r],fill=1)
                    else: d.polygon([P(*q) for q in padpoly(p)],fill=1)
        for v in VIA:
            if v['net']==net:
                c=P(v['x'],v['y']); r=v['size']/2/res; d.ellipse([c[0]-r,c[1]-r,c[0]+r,c[1]+r],fill=1)
        masks[L]=np.array(im,dtype=bool)
    idx={}; n=0
    for L in LAYERS:
        m=masks[L]; ids=-np.ones(m.shape,dtype=np.int64); k=m.sum(); ids[m]=np.arange(n,n+k); n+=k; idx[L]=ids
    rows=[];cols=[];vals=[]
    for L in LAYERS:
        ids=idx[L]; g=1.0/RS[L]
        for a,b in ((ids[:,:-1],ids[:,1:]),(ids[:-1,:],ids[1:,:])):
            ok=(a>=0)&(b>=0); rows.append(a[ok]); cols.append(b[ok]); vals.append(np.full(ok.sum(),g))
    vias=[]
    def addvert(x,y,drill,size):
        c=P(x,y); ci,ri=int(round(c[0])),int(round(c[1]))
        present=[L for L in LAYERS if 0<=ri<H and 0<=ci<W and idx[L][ri,ci]>=0]
        for La,Lb in zip(present,present[1:]):
            dz=ZPOS[Lb]-ZPOS[La]
            circ=math.pi*(drill+0.02)*0.02e-6*1e-0
            R=1.72e-8*(dz*1e-3)/(math.pi*(drill+0.02)*1e-3*0.02e-3)
            rows.append(np.array([idx[La][ri,ci]]));cols.append(np.array([idx[Lb][ri,ci]]));vals.append(np.array([1/R]))
            vias.append((x,y,La,Lb,idx[La][ri,ci],idx[Lb][ri,ci],1/R))
    for v in VIA:
        if v['net']==net: addvert(v['x'],v['y'],v['drill'],v['size'])
    for fp in FP:
        for p in fp['pads']:
            if p['net']==net and p['drill'] is not None and '*.Cu' in p['layers']:
                dr=float(p['drill'][1]) if len(p['drill'])>1 and p['drill'][1] not in('oval',) else 0.8
                addvert(p['x'],p['y'],dr,p['w'])
    r=np.concatenate(rows);c=np.concatenate(cols);v=np.concatenate(vals)
    G=sp.coo_matrix((np.concatenate([-v,-v,v,v]),(np.concatenate([r,c,r,c]),np.concatenate([c,r,r,c]))),shape=(n,n)).tocsr()
    return dict(G=G,idx=idx,masks=masks,n=n,P=P,res=res,box=box,vias=vias)
def padnodes(B,ref,nums,layer='F.Cu'):
    out=[]
    for p in REF[ref]['pads']:
        if p['num'] in nums and B['idx'].get(layer) is not None:
            poly=padpoly(p); xs=[q[0] for q in poly]; ys=[q[1] for q in poly]
            for x in np.arange(min(xs)+0.05,max(xs),0.1):
                for y in np.arange(min(ys)+0.05,max(ys),0.1):
                    c=B['P'](x,y); i=B['idx'][layer][int(round(c[1])),int(round(c[0]))] if 0<=int(round(c[1]))<B['idx'][layer].shape[0] and 0<=int(round(c[0]))<B['idx'][layer].shape[1] else -1
                    if i>=0: out.append(i)
    return sorted(set(out))
def solve(B,src,snk,I=1.0):
    n=B['n']; G=B['G'].tolil()
    # tie sink nodes to ground by large conductance; inject current spread over src
    b=np.zeros(n)
    for i in src: b[i]+=I/len(src)
    Gd=B['G'].copy().tolil()
    for i in snk: Gd[i,i]+=1e6
    Gd=Gd.tocsr()
    # tiny leak to make islands nonsingular
    Gd=Gd+sp.identity(n)*1e-9
    V=sla.spsolve(Gd.tocsc(),b)
    Vs=np.mean(V[src]); Vk=np.mean(V[snk])
    return V,(Vs-Vk)/I
def hotspots(B,V,I,top=5):
    out={}
    for L in LAYERS:
        ids=B['idx'][L]; m=ids>=0
        if m.sum()==0: continue
        VV=np.full(ids.shape,np.nan); VV[m]=V[ids[m]]
        gx=np.abs(np.diff(VV,axis=1)); gy=np.abs(np.diff(VV,axis=0))
        # current per edge = dV/Rs ; current density A/mm = dV/Rs / res
        jx=np.nan_to_num(gx)/RS[L]; jy=np.nan_to_num(gy)/RS[L]
        J=np.zeros(ids.shape); J[:,:-1]=np.maximum(J[:,:-1],jx); J[:-1,:]=np.maximum(J[:-1,:],jy)
        J=J/B['res']  # A per mm of width
        Pw=(np.nan_to_num(gx)**2/RS[L]).sum()+(np.nan_to_num(gy)**2/RS[L]).sum()
        flat=np.argsort(J.ravel())[::-1][:top]
        pts=[(round(B['box'][0]+(f%J.shape[1])*B['res'],2),round(B['box'][2]+(f//J.shape[1])*B['res'],2),round(J.ravel()[f],2)) for f in flat]
        out[L]=(round(Pw*1e3,1),pts)
    return out
def viacur(B,V,I):
    res=[]
    for x,y,La,Lb,a,b,g in B['vias']:
        res.append((abs(V[a]-V[b])*g,x,y,La,Lb))
    res.sort(reverse=True); return res
