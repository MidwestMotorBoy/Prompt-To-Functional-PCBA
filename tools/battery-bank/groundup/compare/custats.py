import numpy as np, os, json
from peec import Model, LAYERS, REF, FP, SEG, VIA, ZON, TH
allnets=sorted(set([p['net'] for fp in FP for p in fp['pads'] if p['net']]+[s['net'] for s in SEG if s['net']]+[z['net'] for z in ZON if z['net']]))
h=0.1; box=(78.4,121.6,62.82,137.17)
m=Model(box,allnets,h=h)
out={}
def zone(name,x0,x1,y0,y1):
    c0,c1=int((x0-box[0])/h),int((x1-box[0])/h); r0,r1=int((y0-box[2])/h),int((y1-box[2])/h)
    cov={L:float((m.lab[L][r0:r1,c0:c1]>0).mean()) for L in LAYERS}
    tcu=sum(cov[L]*TH[L] for L in LAYERS)
    nv=[v for v in VIA if x0<=v['x']<=x1 and y0<=v['y']<=y1]
    nth=[p for fp in FP for p in fp['pads'] if p['drill'] is not None and '*.Cu' in p['layers'] and x0<=p['x']<=x1 and y0<=p['y']<=y1]
    A=(x1-x0)*(y1-y0)
    abar=sum(np.pi*(v['drill']+0.02)*0.02 for v in nv)
    kthru=0.45+385*abar/A
    kin=385*tcu/1.6+0.3
    out[name]=dict(cov=cov,cu_mm=tcu,k_in=kin,vias=len(nv),k_thru=kthru,gnd_vias=sum(1 for v in nv if v['net']=='GND'))
    print(name,'cov',{L[:3]:round(c,2) for L,c in cov.items()},'k_in %.1f'%kin,'vias',len(nv),'k_thru %.2f'%kthru)
zone('board',*box)
zone('fill1',107,116,88.47,114.47)   # port 1 filler zone: model y 7..16, z 27..53
zone('fill2',84,93,88.47,114.47)
zone('stage1',100,121.6,80,116)
zone('stage2',78.4,100,80,116)
json.dump(out,open('custats_%s.json'%os.environ['TAG'],'w'),indent=1)
