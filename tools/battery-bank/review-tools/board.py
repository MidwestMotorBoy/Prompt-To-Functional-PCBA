import math,collections
from sx import *
import os
# Board file: $PCB, or the repo's production board by default
PCB=os.environ.get('PCB',os.path.join(os.path.dirname(os.path.abspath(__file__)),'../../../../hardware/Production/Monolith.kicad_pcb'))
t=parse(open(PCB,encoding='utf-8').read())
def f(x): return float(x)
def netname(n):
    if n is None: return ''
    return n[1] if len(n)>1 else ''
FP=[]
for fp in find(t,'footprint'):
    name=fp[1]
    layer=get(fp,'layer')[1]
    at=get(fp,'at'); x,y=f(at[1]),f(at[2]); rot=f(at[3]) if len(at)>3 else 0
    props={p[1]:p[2] for p in find(fp,'property')}
    pads=[]
    for p in find(fp,'pad'):
        pat=get(p,'at'); px,py=f(pat[1]),f(pat[2]); prot=f(pat[3]) if len(pat)>3 else 0
        a=math.radians(-rot)
        ax=x+px*math.cos(a)-py*math.sin(a); ay=y+px*math.sin(a)+py*math.cos(a)
        sz=get(p,'size'); dr=get(p,'drill')
        pads.append(dict(num=p[1],type=p[2],shape=p[3],x=ax,y=ay,rot=prot,w=f(sz[1]),h=f(sz[2]),
            net=netname(get(p,'net')),layers=get(p,'layers')[1:],drill=dr,pinfn=(get(p,'pinfunction') or [0,''])[1]))
    FP.append(dict(ref=props.get('Reference'),val=props.get('Value'),fp=name,layer=layer,x=x,y=y,rot=rot,pads=pads,props=props,raw=fp))
REF={d['ref']:d for d in FP}
SEG=[]
for s in find(t,'segment'):
    st=get(s,'start');en=get(s,'end')
    SEG.append(dict(x1=f(st[1]),y1=f(st[2]),x2=f(en[1]),y2=f(en[2]),w=f(get(s,'width')[1]),layer=get(s,'layer')[1],net=netname(get(s,'net'))))
VIA=[]
for v in find(t,'via'):
    at=get(v,'at')
    VIA.append(dict(x=f(at[1]),y=f(at[2]),size=f(get(v,'size')[1]),drill=f(get(v,'drill')[1]),net=netname(get(v,'net')),layers=get(v,'layers')[1:]))
ZON=[]
for z in find(t,'zone'):
    net=netname(get(z,'net'))
    nm=get(z,'name'); layers=(get(z,'layers') or get(z,'layer'))[1:]
    pri=get(z,'priority'); fill=get(z,'fill')
    fills=[]
    for fp_ in find(z,'filled_polygon'):
        L=get(fp_,'layer')[1]; pts=[(f(q[1]),f(q[2])) for q in get(fp_,'pts')[1:] if q[0]=='xy']
        fills.append((L,pts))
    outline=[(f(q[1]),f(q[2])) for q in get(get(z,'polygon'),'pts')[1:] if q[0]=='xy'] if get(z,'polygon') else []
    ZON.append(dict(net=net,name=nm[1] if nm else '',layers=layers,priority=pri[1] if pri else '0',keepout=bool(get(z,'keepout')),fills=fills,outline=outline,raw=z))
def seglen(s): return math.hypot(s['x2']-s['x1'],s['y2']-s['y1'])
