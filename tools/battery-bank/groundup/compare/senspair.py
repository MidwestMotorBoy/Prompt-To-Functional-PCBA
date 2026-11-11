"""Sense-pair routing: follow each Kelvin pair from the sense resistor through its filter resistors to the IC pins,
report route length, where the tap leaves the power copper and the area enclosed between the two lines."""
import os, json, math, heapq, collections
import numpy as np
from board import FP, SEG, VIA, REF, seglen
TAG=os.environ['TAG']
def pad(ref,num,net=None):
    for p in REF[ref]['pads']:
        if p['num']==num and (net is None or p['net'].endswith(net)): return p
def inpad(p,x,y,m=0.05):
    a=math.radians(p['rot']); dx,dy=x-p['x'],y-p['y']
    u=dx*math.cos(a)-dy*math.sin(a); v=dx*math.sin(a)+dy*math.cos(a)
    return (abs(u)<=p['w']/2+m and abs(v)<=p['h']/2+m) or (abs(u)<=p['h']/2+m and abs(v)<=p['w']/2+m and False)
def k(x,y): return (round(x,3),round(y,3))
def graph(net,wmax=9):
    g=collections.defaultdict(list)
    for s in SEG:
        if s['net']==net and s['w']<=wmax:
            a,b=k(s['x1'],s['y1']),k(s['x2'],s['y2']); L=seglen(s); g[a].append((b,L,s['layer'])); g[b].append((a,L,s['layer']))
    return g
def dijk(g,starts):
    d={s:0 for s in starts}; prev={}; h=[(0,s) for s in starts]
    while h:
        c,u=heapq.heappop(h)
        if c>d.get(u,1e9): continue
        for v,L,_ in g[u]:
            if c+L<d.get(v,1e9): d[v]=c+L; prev[v]=u; heapq.heappush(h,(c+L,v))
    return d,prev
def path(prev,t):
    p=[t]
    while p[-1] in prev: p.append(prev[p[-1]])
    return p
def route(net,pa,pb,wmax=9):
    """shortest track route on net from pad pa towards pad pb; returns points, reached(bool), gap to pb"""
    g=graph(net,wmax); starts=[n for n in g if inpad(pa,*n)]
    if not starts: return [(pa['x'],pa['y'])],False,math.hypot(pa['x']-pb['x'],pa['y']-pb['y'])
    d,prev=dijk(g,starts)
    hit=[n for n in d if inpad(pb,*n)]
    if hit:
        t=min(hit,key=d.get); return [(pa['x'],pa['y'])]+path(prev,t)[::-1]+[(pb['x'],pb['y'])],True,0.0
    def gap(n):
        a=math.radians(pb['rot']); dx,dy=n[0]-pb['x'],n[1]-pb['y']; u=abs(dx*math.cos(a)-dy*math.sin(a))-pb['w']/2; v=abs(dx*math.sin(a)+dy*math.cos(a))-pb['h']/2
        return math.hypot(max(u,0),max(v,0))
    t=min(d,key=lambda n:(gap(n),d[n])); return [(pa['x'],pa['y'])]+path(prev,t)[::-1],False,gap(t)
def plen(p): return sum(math.hypot(p[i+1][0]-p[i][0],p[i+1][1]-p[i][1]) for i in range(len(p)-1))
def area(poly):
    x=np.array([q[0] for q in poly]); y=np.array([q[1] for q in poly]); return 0.5*abs(np.dot(x,np.roll(y,-1))-np.dot(y,np.roll(x,-1)))
def pair(name,rs,pnet,nnet,fp_,fn_,pfnet,nfnet,ic,ppin,npin):
    P_=pad(rs[0],rs[1]); N_=pad(rs[0],rs[2])
    fa=pad(fp_,'1'); fb=pad(fp_,'2'); ga=pad(fn_,'1'); gb=pad(fn_,'2')
    ip=pad(ic,ppin); im=pad(ic,npin)
    r1,ok1,gap1=route(pnet,fa,P_,0.45); r2,ok2,gap2=route(nnet,ga,N_,0.45)      # filter -> sense resistor (tap lines)
    r3,_,_=route(pfnet,fb,ip); r4,_,_=route(nfnet,gb,im)                       # filter -> IC pin
    plus=r1[::-1]+r3; minus=r2[::-1]+r4
    poly=plus+minus[::-1]
    lay=collections.Counter()
    for net in (pfnet,nfnet):
        for s in SEG:
            if s['net']==net: lay[s['layer'][:3]]+=seglen(s)
    return dict(name=name,len_plus=plen(plus),len_minus=plen(minus),area=area(poly),tap_plus_on_pad=ok1,tap_minus_on_pad=ok2,gap_plus=gap1,gap_minus=gap2,
                plus=[list(q) for q in plus],minus=[list(q) for q in minus],layers={a:round(b,1) for a,b in lay.items()})
P1,P2='/USB Port 1/','/USB Port 2/'
out=[]
for p,P in ((1,P1),(2,P2)):
    h=str(p+3)
    out.append(pair(f'P{p} battery sense (SRP/SRN)',(f'R{h}27','1','2'),P+'BAT_SNS_P','PACK_P',f'R{h}28',f'R{h}29',P+'SRP_F',P+'SRN_F',f'U{h}03','14','13'))
    out.append(pair(f'P{p} input sense (ACP/ACN)',(f'R{h}24','1','2'),P+'PPHV',P+'AC_SNS_N',f'R{h}25',f'R{h}26',P+'ACP_F',P+'ACN_F',f'U{h}03','30','29'))
out.append(pair('Gauge shunt (SRP/SRN)',('RS101','1','2'),'CELL_N','GND','R107','R108','/Cells and Gauge/SRP','/Cells and Gauge/SRN','U101','8','6'))
json.dump(out,open(f'senspair_{TAG}.json','w'))
for o in out: print(f"{o['name']:28s} length {o['len_plus']:5.1f} / {o['len_minus']:5.1f} mm  enclosed {o['area']:6.2f} mm2  tap on pad {o['tap_plus_on_pad']}/{o['tap_minus_on_pad']} gap {o['gap_plus']:.2f}/{o['gap_minus']:.2f} mm  {o['layers']}")
