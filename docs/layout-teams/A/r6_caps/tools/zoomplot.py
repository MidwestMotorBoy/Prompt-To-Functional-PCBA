#!/usr/bin/env python3
"""zoomplot.py <spec.json> <bare.json> <out.png> x0 y0 x1 y1 [layers=F.Cu,In4.Cu] : quick matplotlib view of planned zones/tracks/vias + pads"""
import sys, json, matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from shapely.geometry import Polygon
S=json.load(open(sys.argv[1])); D=json.load(open(sys.argv[2])); out=sys.argv[3]; x0,y0,x1,y1=map(float,sys.argv[4:8])
lays=(sys.argv[8] if len(sys.argv)>8 else 'F.Cu,In4.Cu').split(',')
col={'3V3':'g','PACK_P':'r','GND':'0.8'}
fig,ax=plt.subplots(figsize=(12,12*(y1-y0)/(x1-x0)))
for z in S['zones']:
    if z['layer'] in lays and z['net']!='GND':
        for q in z['polys']:
            P=Polygon(q['ring']); x,y=P.exterior.xy
            c=col.get(z['net'],'c'); ax.fill(x,y,alpha=.25,color=c, hatch='//' if z['layer']=='In4.Cu' else None); ax.plot(x,y,color=c,lw=.6)
for t in S['tracks']:
    if t['layer'] in lays: ax.plot([t['a'][0],t['b'][0]],[t['a'][1],t['b'][1]],color=col.get(t['net'],'b'),lw=max(.5,t['w']*20),alpha=.6)
for v in S['vias']:
    ax.add_patch(plt.Circle((v['x'],v['y']),v['size']/2,color=col.get(v['net'],'k')))
for p in D['pads']:
    for L,recs in p['shapes'].items():
        if L in lays or (p['drill'] and True):
            for r in recs:
                P=Polygon(r['ring']); x,y=P.exterior.xy; ax.plot(x,y,color=col.get(p['net'],'k'),lw=.8)
    if x0<p['x']<x1 and y0<p['y']<y1: ax.text(p['x'],p['y'],f"{p['ref']}.{p['num']}",fontsize=6)
ax.set_xlim(x0,x1); ax.set_ylim(y1,y0); ax.set_aspect('equal'); ax.grid(alpha=.3)
plt.savefig(out,dpi=90,bbox_inches='tight')
