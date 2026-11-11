"""render copper json: rc.py cu.json out.png x0 y0 x1 y1 scale layers(e.g. F,In2,In3,B)"""
import json,sys,hashlib,colorsys
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Circle, PathPatch
from matplotlib.path import Path
KEY={'GND':'#9a9a9a','PACK_P':'#e6194b','3V3':'#f58231'}
def col(net):
    s=net.split('/')[-1] if net else ''
    if not s: return '#dddddd'
    if s in KEY: return KEY[s]
    if '2/' in net: s=s+'#2'
    h=int(hashlib.md5(s.encode()).hexdigest()[:6],16); return colorsys.hsv_to_rgb((h%360)/360,0.75,0.85)
def render(d,out,box,scale=40,layers=('F','In2','In3','B'),labels=True):
    x0,y0,x1,y1=box; n=len(layers)
    fig=plt.figure(figsize=((x1-x0)*scale/100*n,(y1-y0)*scale/100),dpi=100)
    for i,L in enumerate(layers):
        ax=fig.add_axes([i/n,0,1/n,1]); ax.set_xlim(x0,x1); ax.set_ylim(y1,y0); ax.set_aspect('equal'); ax.axis('off')
        ax.text(x0+0.3,y0+0.8,L,fontsize=12,color='k')
        for f in d['fills']:
            if f['l']!=L: continue
            for pts,hs in f['polys']:
                if not any(x0-2<x<x1+2 and y0-2<y<y1+2 for x,y in pts[::max(1,len(pts)//200)]) and len(pts)<50: continue
                verts=list(pts)+[pts[0]]; codes=[Path.MOVETO]+[Path.LINETO]*(len(pts)-1)+[Path.CLOSEPOLY]
                for h in hs:
                    verts+=list(h)+[h[0]]; codes+=[Path.MOVETO]+[Path.LINETO]*(len(h)-1)+[Path.CLOSEPOLY]
                ax.add_patch(PathPatch(Path(verts,codes),fc=col(f['net']),ec='none',alpha=0.45))
        for t in d['tracks']:
            if t['l']==L: ax.plot([t['x1'],t['x2']],[t['y1'],t['y2']],color=col(t['net']),lw=t['w']*scale*0.72,solid_capstyle='round',alpha=0.95)
        for p in d['pads']:
            if L in p['L'] and p['L'][L] and x0-2<p['x']<x1+2 and y0-2<p['y']<y1+2:
                ax.add_patch(Polygon(p['L'][L],fc=col(p['net']),ec='k',lw=0.3))
                if labels and scale>=50 and p['net']: ax.text(p['x'],p['y'],p['net'].split('/')[-1][:8],fontsize=scale*0.06,ha='center',va='center')
        if labels and scale>=50:
            cen={}
            for p in d['pads']:
                if L in p['L'] and p['L'][L]: cen.setdefault(p['ref'],[]).append((p['x'],p['y'],p['n']))
            for r,ps in cen.items():
                cx=sum(q[0] for q in ps)/len(ps); cy=sum(q[1] for q in ps)/len(ps)
                if x0<cx<x1 and y0<cy<y1:
                    ax.text(cx,cy,r,fontsize=scale*0.075,ha='center',va='center',color='#0000aa',weight='bold',bbox=dict(fc='w',ec='none',alpha=0.6,pad=0.5))
                    if len(ps)>4:
                        for q in ps:
                            if x0<q[0]<x1 and y0<q[1]<y1: ax.text(q[0],q[1]+0.12,q[2],fontsize=scale*0.045,ha='center',va='center',color='#aa0000')
        for v in d['vias']:
            if x0<v['x']<x1 and y0<v['y']<y1:
                ax.add_patch(Circle((v['x'],v['y']),v['d']/2,fc=col(v['net']),ec='k',lw=0.4)); ax.add_patch(Circle((v['x'],v['y']),v['drill']/2,fc='w',ec='none'))
        for gx in range(int(x0)//5*5,int(x1)+1,5): ax.axvline(gx,color='#00000022',lw=0.4); ax.text(gx,y0+0.4,str(gx),fontsize=6,color='gray')
        for gy in range(int(y0)//5*5,int(y1)+1,5): ax.axhline(gy,color='#00000022',lw=0.4); ax.text(x0+0.1,gy,str(gy),fontsize=6,color='gray')
    fig.savefig(out); plt.close(fig)
if __name__=='__main__':
    d=json.load(open(sys.argv[1])); box=tuple(map(float,sys.argv[3:7]))
    render(d,sys.argv[2],box,float(sys.argv[7]) if len(sys.argv)>7 else 40,tuple(sys.argv[8].split(',')) if len(sys.argv)>8 else ('F','In2','In3','B'))
