"""Footprint geometry database built from a dump.py JSON of the current board: local pads + courtyard box per ref.
Local frame = footprint at rot 0 on its own side. World: dx = lx*cos + ly*sin, dy = -lx*sin + ly*cos (KiCad, y down)."""
import json, math, copy
def rotv(lx,ly,rot):
    a=math.radians(rot); c,s=math.cos(a),math.sin(a)
    return lx*c+ly*s, -lx*s+ly*c
def unrot(dx,dy,rot):
    a=math.radians(rot); c,s=math.cos(a),math.sin(a)
    return dx*c-dy*s, dx*s+dy*c
class DB:
    def __init__(s,path='base.json'):
        s.d=json.load(open(path)); s.fp={}
        for f in s.d['fps']:
            pads=[]
            for p in f['pads']:
                lx,ly=unrot(p['x']-f['x'],p['y']-f['y'],f['rot'])
                r=(p['rot']-f['rot'])%180
                sx,sy=(p['sx'],p['sy']) if (abs(r)<1 or abs(r-180)<1) else (p['sy'],p['sx'])
                pads.append(dict(n=p['n'],net=p['net'],lx=lx,ly=ly,sx=sx,sy=sy,drill=p['drill'],pinfn=p['pinfn']))
            # courtyard corners -> local box
            x0,y0,x1,y1=f['bb']; cs=[unrot(x-f['x'],y-f['y'],f['rot']) for x,y in((x0,y0),(x1,y0),(x1,y1),(x0,y1))]
            box=(min(c[0] for c in cs),min(c[1] for c in cs),max(c[0] for c in cs),max(c[1] for c in cs))
            s.fp[f['ref']]=dict(ref=f['ref'],val=f['val'],fp=f['fp'],layer=f['layer'],pads=pads,box=box,base=(f['x'],f['y'],f['rot']),locked=f['locked'],sheet=f['sheet'])
    def world(s,ref,x,y,rot):
        f=s.fp[ref]; b=f['box']
        cs=[rotv(cx,cy,rot) for cx,cy in((b[0],b[1]),(b[2],b[1]),(b[2],b[3]),(b[0],b[3]))]
        bb=[x+min(c[0] for c in cs),y+min(c[1] for c in cs),x+max(c[0] for c in cs),y+max(c[1] for c in cs)]
        pads=[]
        for p in f['pads']:
            dx,dy=rotv(p['lx'],p['ly'],rot)
            sx,sy=(p['sx'],p['sy']) if round(rot/90)%2==0 else (p['sy'],p['sx'])
            pads.append(dict(n=p['n'],net=p['net'],x=x+dx,y=y+dy,sx=sx,sy=sy,drill=p['drill'],rot=0,pinfn=p['pinfn']))
        return dict(ref=ref,val=f['val'],fp=f['fp'],layer=f['layer'],x=x,y=y,rot=rot,bb=bb,pads=pads,locked=f['locked'],sheet=f['sheet'])
    def pad(s,P,ref,n):
        """world centre of pad n of ref in placement dict P {ref:(x,y,rot)}"""
        x,y,rot=P[ref]
        for p in s.fp[ref]['pads']:
            if p['n']==str(n):
                dx,dy=rotv(p['lx'],p['ly'],rot); return (round(x+dx,3),round(y+dy,3))
        raise KeyError((ref,n))
