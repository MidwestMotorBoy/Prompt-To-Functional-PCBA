"""quick 2-D renderer from a dump.py JSON: courtyards, pads coloured by net, refs"""
import json, sys, math, hashlib
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Polygon, Circle
KEY={'GND':'#888888','PACK_P':'#e6194b','3V3':'#f58231'}
def col(net):
    if not net: return '#dddddd'
    s=net.split('/')[-1]
    for k,v in KEY.items():
        if s==k: return v
    h=int(hashlib.md5(s.encode()).hexdigest()[:6],16)
    import colorsys
    r,g,b=colorsys.hsv_to_rgb((h%360)/360,0.75,0.85); return (r,g,b)
def render(d,out,box=None,side='F',scale=30,labels=True,padnames=False,extra=None,netlabels=False):
    x0,y0,x1,y1=box or (78,62,122,138)
    fig=plt.figure(figsize=((x1-x0)*scale/100,(y1-y0)*scale/100),dpi=100)
    ax=fig.add_axes([0,0,1,1]); ax.set_xlim(x0,x1); ax.set_ylim(y1,y0); ax.set_aspect('equal'); ax.axis('off')
    ax.add_patch(Rectangle((78.4,62.8245),43.2,74.35,fill=False,ec='k',lw=1))
    for z in d.get('zones',[]):
        if z['rulearea'] and (side[0]+'.Cu') in ' '.join(z['layers']):
            ax.add_patch(Polygon(z['pts'],fill=True,fc='#ff000011',ec='#ff0000',lw=0.6,ls='--'))
    for f in d['fps']:
        on=f['layer'][0]==side
        bb=f['bb']
        if on: ax.add_patch(Rectangle((bb[0],bb[1]),bb[2]-bb[0],bb[3]-bb[1],fill=False,ec='#3355ff' if not f['locked'] else '#aa00aa',lw=0.5))
        for p in f['pads']:
            th=p['drill']>0
            if not (on or th): continue
            if not(x0-3<p['x']<x1+3 and y0-3<p['y']<y1+3): continue
            a=math.radians(-p['rot']); sx,sy=p['sx']/2,p['sy']/2
            pts=[(p['x']+cx*math.cos(a)-cy*math.sin(a),p['y']+cx*math.sin(a)+cy*math.cos(a)) for cx,cy in((-sx,-sy),(sx,-sy),(sx,sy),(-sx,sy))]
            ax.add_patch(Polygon(pts,fc=col(p['net']),ec='none',alpha=0.9))
            if th: ax.add_patch(Circle((p['x'],p['y']),p['drill']/2,fc='w',ec='k',lw=0.3))
            if padnames and len(f['pads'])>2: ax.text(p['x'],p['y'],p['n'],fontsize=scale*0.11,ha='center',va='center')
            if netlabels and p['net'] and p['net']!='GND': ax.text(p['x'],p['y']+0.1,p['net'].split('/')[-1][:9],fontsize=scale*0.07,ha='center',va='center',color='k')
        if on and labels: ax.text((bb[0]+bb[2])/2,(bb[1]+bb[3])/2,f['ref'],fontsize=max(3,scale*0.16),ha='center',va='center',color='#000088')
    if extra: extra(ax)
    for gx in range(int(x0)//5*5,int(x1)+1,5): ax.axvline(gx,color='#00000018',lw=0.4); ax.text(gx,y0+0.5,str(gx),fontsize=6,color='gray')
    for gy in range(int(y0)//5*5,int(y1)+1,5): ax.axhline(gy,color='#00000018',lw=0.4); ax.text(x0+0.1,gy,str(gy),fontsize=6,color='gray')
    fig.savefig(out); plt.close(fig)
if __name__=='__main__':
    d=json.load(open(sys.argv[1])); box=tuple(map(float,sys.argv[3:7])) if len(sys.argv)>6 else None
    render(d,sys.argv[2],box,side=sys.argv[7] if len(sys.argv)>7 else 'F',scale=float(sys.argv[8]) if len(sys.argv)>8 else 30,padnames=len(sys.argv)>9)
