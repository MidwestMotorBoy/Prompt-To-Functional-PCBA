"""Per-via current on every power path at its screening current (9 A battery side, 5 A USB side) -> via_<tag>.json"""
import sys, os, json
from solve import *
import pyamg
box=(77,123,61,138); RES=0.1
P_={1:'/USB Port 1/',2:'/USB Port 2/'}
built={}
def B_(net):
    if net not in built: built[net]=build(net,box,RES)
    return built[net]
def nodes(B,ref,nums,net,layer='F.Cu'):
    nums=[x for x in nums if any(p['num']==x and p['net']==net for p in REF[ref]['pads'])]
    return padnodes(B,ref,nums,layer)
def solve2(B,src,snk):
    n=B['n']; b=np.zeros(n); b[src]=1.0/len(src)
    d=np.zeros(n); d[snk]=1e6
    G=(B['G']+sp.diags(d)+sp.identity(n)*1e-9).tocsr()
    ml=pyamg.smoothed_aggregation_solver(G,max_coarse=500)
    return ml.solve(b,tol=1e-10,accel='cg',maxiter=400)
DR={}
for v in VIA: DR[(round(v['x'],3),round(v['y'],3))]=('via',v['drill'])
for fp in FP:
    for p in fp['pads']:
        if p['drill'] is not None and '*.Cu' in p['layers']: DR[(round(p['x'],3),round(p['y'],3))]=(fp['ref']+'.'+p['num'],None)
paths=[]
for p in (1,2):
    P=P_[p]; h=str(p+3)
    paths+=[(f'P{p} PACK_P Q102 to RBAT','PACK_P','Q102',['1','2','3'],f'R{h}27',['2'],9.0),
            (f'P{p} BAT_SNS_P RBAT to leg B',P+'BAT_SNS_P',f'R{h}27',['1'],f'Q{h}02',['2','3','4'],9.0),
            (f'P{p} GND shunt to stage','GND','RS101',['2'],f'Q{h}01',['5','6','7'],9.0),
            (f'P{p} VBUS connector to TPS25751',P+'VBUS',f'J{h}01',['A4','A9','B4','B9'],f'U{h}01',['23','32'],5.0),
            (f'P{p} PPHV TPS25751 to RAC',P+'PPHV',f'U{h}01',['20'],f'R{h}24',['1'],5.0),
            (f'P{p} AC_SNS_N RAC to leg A',P+'AC_SNS_N',f'R{h}24',['2'],f'Q{h}01',['2','3','4'],5.0)]
paths+=[('CELL_P fuse to Q101','/Cells and Gauge/CELL_P','F102',['2'],'Q101',['1','2','3'],9.0),
        ('CELL_P_RAW J112 to fuse','/Cells and Gauge/CELL_P_RAW','J112',['1'],'F102',['1'],9.0),
        ('CELL_N J108 to shunt','CELL_N','J108',['1'],'RS101',['1'],9.0),
        ('FET_MID Q101 to Q102','/Cells and Gauge/FET_MID','Q101',['5','6','7','8'],'Q102',['5','6','7','8'],9.0)]
out={}
for name,net,a,an,b,bn,I in paths:
    B=B_(net); src=nodes(B,a,an,net); snk=nodes(B,b,bn,net); V=solve2(B,src,snk)
    per={}
    for x,y,La,Lb,na,nb,g in B['vias']:
        i=abs(V[na]-V[nb])*g*I; k=(round(x,3),round(y,3))
        if k not in per or i>per[k][0]: per[k]=(i,La,Lb)
    kind=lambda k: DR.get(k,('via',None))
    vv=sorted(((i,k,La,Lb) for k,(i,La,Lb) in per.items() if kind(k)[0]=='via'),reverse=True)
    th=sorted(((i,k,La,Lb) for k,(i,La,Lb) in per.items() if kind(k)[0]!='via'),reverse=True)
    out[name]=dict(I=I,n_vias=len(vv),top=[dict(i=float(i),x=k[0],y=k[1],drill=kind(k)[1],seg=f"{La[:-3]}-{Lb[:-3]}") for i,k,La,Lb in vv[:6]],
                   over1=sum(1 for v in vv if v[0]>=1.0),over2=sum(1 for v in vv if v[0]>=2.0),carrying=sum(1 for v in vv if v[0]>=0.02*I),
                   holes=[dict(i=float(i),ref=kind(k)[0]) for i,k,La,Lb in th[:2] if i>0.05*I])
    t=out[name]['top']
    print(f"{name:34s} {I:.0f} A  vias {len(vv):3d} carrying {out[name]['carrying']:3d}  >1A {out[name]['over1']:2d} >2A {out[name]['over2']:2d}  top "+', '.join(f"{v['i']:.2f}A@({v['x']:.1f},{v['y']:.1f}) {v['seg']}" for v in t[:3]),flush=True)
json.dump(out,open('via_%s.json'%os.environ['TAG'],'w'),indent=1)
