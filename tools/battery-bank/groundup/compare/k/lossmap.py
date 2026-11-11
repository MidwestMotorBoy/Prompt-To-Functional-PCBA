"""Per-port routed-copper resistance and 2 mm loss tiles for the thermal model (cu.py format), plus per-path R."""
import sys, os, json, time
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
def lossgrid(B,V):
    H,W=B['idx']['F.Cu'].shape; Pm=np.zeros((H,W)); per={}
    for L in LAYERS:
        ids=B['idx'][L]; m=ids>=0
        if not m.any(): continue
        VV=np.zeros(ids.shape); VV[m]=V[ids[m]]; g=1/RS[L]; tot=0
        ok=m[:,:-1]&m[:,1:]; p=np.where(ok,(VV[:,:-1]-VV[:,1:])**2*g,0); Pm[:,:-1]+=p/2; Pm[:,1:]+=p/2; tot+=p.sum()
        ok=m[:-1,:]&m[1:,:]; p=np.where(ok,(VV[:-1,:]-VV[1:,:])**2*g,0); Pm[:-1,:]+=p/2; Pm[1:,:]+=p/2; tot+=p.sum()
        per[L]=float(tot)
    for x,y,La,Lb,a,b,g in B['vias']:
        c=B['P'](x,y); Pm[int(round(c[1])),int(round(c[0]))]+=(V[a]-V[b])**2*g
    return Pm,per
def path(net,a,an,b,bn):
    B=B_(net); src=nodes(B,a,an,net); snk=nodes(B,b,bn,net)
    assert src and snk,(net,a,b)
    V=solve2(B,src,snk); R=np.mean(V[src])-np.mean(V[snk]); Pm,per=lossgrid(B,V)
    return R,Pm,per
def tiles(Pm):
    out=[]; H,W=Pm.shape
    xs=box[0]+np.arange(W)*RES; ys=box[2]+np.arange(H)*RES
    tx=np.floor((xs-1)/2).astype(int); ty=np.floor((ys-1)/2).astype(int)   # tile edges on odd mm
    acc={}
    rr,cc=np.nonzero(Pm)
    for r,c in zip(rr,cc): acc[(tx[c],ty[r])]=acc.get((tx[c],ty[r]),0)+Pm[r,c]
    tot=sum(acc.values())
    for (i,j),v in acc.items():
        if v<1e-3*tot: continue
        x0=2*i+1; y0=2*j+1
        out.append([x0-100.0,x0+2-100.0,round(141.47-(y0+2),2),round(141.47-y0,2),float(v)])
    return out
res={'paths':{}}
def group(key,plist):
    Rt=0; Pm=None
    for name,net,a,an,b,bn in plist:
        R,P1,per=path(net,a,an,b,bn); res['paths'][name]=dict(R=float(R),layers=per); Rt+=R; Pm=P1 if Pm is None else Pm+P1
        print(f'{name}: {R*1e3:.2f} mOhm',{L[:3]:round(v/R*100) for L,v in per.items() if v/R>0.02},flush=True)
    res[key]=dict(R=float(Rt),boxes=tiles(Pm)); np.save(f'lossmap_{os.environ["TAG"]}_{key}.npy',Pm.astype(np.float32))
for p in (1,2):
    P=P_[p]; h=str(p+3)
    group(f'cub{p}',[(f'P{p} PACK_P Q102 to RBAT','PACK_P','Q102',['1','2','3'],f'R{h}27',['2']),
                     (f'P{p} BAT_SNS_P RBAT to leg B',P+'BAT_SNS_P',f'R{h}27',['1'],f'Q{h}02',['2','3','4']),
                     (f'P{p} GND shunt to stage','GND','RS101',['2'],f'Q{h}01',['5','6','7'])])
    group(f'cuu{p}',[(f'P{p} VBUS connector to TPS25751',P+'VBUS',f'J{h}01',['A4','A9','B4','B9'],f'U{h}01',['23','32']),
                     (f'P{p} PPHV TPS25751 to RAC',P+'PPHV',f'U{h}01',['20'],f'R{h}24',['1']),
                     (f'P{p} AC_SNS_N RAC to leg A',P+'AC_SNS_N',f'R{h}24',['2'],f'Q{h}01',['2','3','4'])])
group('pack',[('CELL_P fuse to Q101','/Cells and Gauge/CELL_P','F102',['2'],'Q101',['1','2','3']),
              ('CELL_P_RAW J112 to fuse','/Cells and Gauge/CELL_P_RAW','J112',['1'],'F102',['1']),
              ('CELL_N J108 to shunt','CELL_N','J108',['1'],'RS101',['1']),
              ('FET_MID Q101 to Q102','/Cells and Gauge/FET_MID','Q101',['5','6','7','8'],'Q102',['5','6','7','8'])])
json.dump(res,open('cu_%s.json'%os.environ['TAG'],'w'),indent=1)
for k in ('cub1','cub2','cuu1','cuu2','pack'): print(k,'%.2f mOhm'%(res[k]['R']*1e3),len(res[k]['boxes']),'tiles')
