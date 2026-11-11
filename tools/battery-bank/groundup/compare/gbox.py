from board import *
from run_all_defs import GATES
def autobox(refs, margin=2.0):
    xs = [p['x'] for r in refs for p in REF[r]['pads']]; ys = [p['y'] for r in refs for p in REF[r]['pads']]
    return (min(xs)-margin, max(xs)+margin, min(ys)-margin, max(ys)+margin)
def netbox(nets,m=1.0):
    xs=[];ys=[]
    for s in SEG:
        if s['net'] in nets: xs+=[s['x1'],s['x2']]; ys+=[s['y1'],s['y2']]
    for v in VIA:
        if v['net'] in nets: xs.append(v['x']); ys.append(v['y'])
    return (min(xs)-m,max(xs)+m,min(ys)-m,max(ys)+m)
def gbox(nets,U,R,Q):
    a=autobox([U,R,Q],2.0); drv=[n for n in nets if n!='GND' and 'SW' not in n.split('/')[-1]]
    b=netbox(drv); return (min(a[0],b[0]),max(a[1],b[1]),min(a[2],b[2]),max(a[3],b[3])),a,b
if __name__=='__main__':
    for name,nets,U,dp,rp,R,Q,qp in GATES:
        u,a,b=gbox(nets,U,R,Q); inside=b[0]>=a[0] and b[1]<=a[1] and b[2]>=a[2] and b[3]<=a[3]
        L=[ (s['layer'][:3],round(s['w'],2)) for s in SEG if s['net'] in nets and s['net']!='GND' and 'SW' not in s['net'].split('/')[-1]]
        import collections
        ly=collections.Counter(); 
        for s in SEG:
            if s['net'] in nets and s['net']!='GND' and 'SW' not in s['net'].split('/')[-1]: ly[(s['layer'][:3],round(s['w'],2))]+=round(seglen(s),1)
        print(name,'inside' if inside else 'CLIPPED',[round(x,1) for x in a],[round(x,1) for x in b],{k:round(v,1) for k,v in ly.items()})
