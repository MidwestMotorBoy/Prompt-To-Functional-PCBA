"""draw.py <placement.json> <out.png> [side]: frozen parts grey, keep-outs pink, movable parts blue (red if overlapping)"""
import json,sys,matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
exec(open('/home/claude/work/team/w3/measure.py').read().split('def near')[0])
pl=json.load(open(sys.argv[1])); side=sys.argv[3] if len(sys.argv)>3 else 'F.Cu'
cl=json.load(open('/home/claude/work/hp/q7s2_fz_clusters.json')); mov={r:n for n,p in cl.items() for r in p}
B=boxes(pl,D); fig,ax=plt.subplots(figsize=(8,13))
for k in D['keepouts']:
    if k.get('no_footprints') and side in k['layers']:
        b=k['box']; ax.add_patch(Rectangle((b[0],b[1]),b[2]-b[0],b[3]-b[1],color='#f4b6c2',lw=0))
BF=json.load(open('/home/claude/work/bfp7/floorplan_2.json'))['blocks']
for n,b in BF.items():
    if n.endswith(side): ax.add_patch(Rectangle((b[0],b[1]),b[2]-b[0],b[3]-b[1],fill=False,ec='green',lw=0.6,ls='--'))
for r,b in B.items():
    if b[4]!=side: continue
    if r in mov:
        bad=any(o!=r and B[o][4]==side and min(b[2],B[o][2])-max(b[0],B[o][0])>0.03 and min(b[3],B[o][3])-max(b[1],B[o][1])>0.03 for o in B)
        ax.add_patch(Rectangle((b[0],b[1]),b[2]-b[0],b[3]-b[1],fill=True,fc=('#ff4040' if bad else '#6fa8ff'),ec='k',lw=0.4,alpha=0.8))
        if (b[2]-b[0])*(b[3]-b[1])>6: ax.text((b[0]+b[2])/2,(b[1]+b[3])/2,r,fontsize=6,ha='center',va='center')
    else:
        ax.add_patch(Rectangle((b[0],b[1]),b[2]-b[0],b[3]-b[1],fill=True,fc='#999',ec='k',lw=0.4,alpha=0.7))
        ax.text((b[0]+b[2])/2,(b[1]+b[3])/2,r,fontsize=4,ha='center',va='center')
bx=D['box']; ax.set_xlim(bx[0],bx[2]); ax.set_ylim(bx[3],bx[1]); ax.set_aspect('equal'); plt.tight_layout(); plt.savefig(sys.argv[2],dpi=90)
