import sys, json
sys.argv=['x']
sys.path.insert(0,'/home/claude/repo/docs/layout-teams/A/r4_bcu/tools')
import plan_copper_b as B, plan_copper_a as pa, plan_copper_p as pp, plan_copper as pc
import numpy as np
from shapely.geometry import Point, box
opts="--sealed=1 --taps=1 --joinfix=1 --epstrip=1 --directjoin=1 --nogrow_dead=1 --gndesc=1 --connesc=1 --pinesc=1 --pinesc_refs=U501 --pinesc_near=1 --gndpair=1".split()
pa.SEALED=1; pa.TAPS=1
for o in opts:
    k,v=o[2:].split('=')
    if k in pp.OPT: pp.OPT[k]=type(pp.OPT[k])(float(v)) if isinstance(pp.OPT[k],(int,float)) else v
B.OPTB['ret_band']=1.6
pl=B.PlannerB('bare.json','/home/claude/repo/tools/floorplan/example/monolith/constraints.json',None,escape=0.4,grow=1.5,mirror=3)
pl.planes_step(); pl.bus_nets=[]
pl.hot_loops_step()
r=0.225
ok=np.ones((pl.H,pl.W),bool); ok&=~pl.novia
for L in pl.outer:
    rm=pl.room('GND',L,loose=True); 
    for x,y in [(117.6,92.3),(118.2,92.3),(118.8,92.3),(118.2,91.9)]:
        i,j=int((y-pl.y0)/pc.RES),int((x-pl.x0)/pc.RES); print(L,x,y,'room',round(rm[i,j],3),'block',pl.block[L][i,j],'novia',pl.novia[i,j], 'cu',pl.cu[L][i,j], 'pad',pl.padnet[L][i,j], 'via',pl.viamap[i,j])
z=pl.zones[('GND','F.Cu')]['geom']
print([round(v,2) for v in z.intersection(box(116,90,121,94)).bounds])
holes=[(v['x'],v['y']) for v in pl.vias]+[(p[0],p[1]) for p in pl.drilled]
print([h for h in holes if 116<h[0]<121 and 90<h[1]<94])
print([t for t in pl.tracks if 116<t['a'][0]<121 and 90<t['a'][1]<94])
