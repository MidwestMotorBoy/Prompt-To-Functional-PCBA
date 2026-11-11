"""Current maps of the hot loops and gate loops for one board (PCB env, TAG env) -> img/<kind>_<i>_<tag>.png"""
import pickle, numpy as np, sys, math, os, json
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from matplotlib.colors import LinearSegmentedColormap, PowerNorm
from peec import Model, padpoly, LAYERS, FP, SEG, ZON, REF
TAG=os.environ['TAG']; OUT='img'; os.makedirs(OUT,exist_ok=True)
LABEL={'base':'Current board','new':'Ground-up board, first version','fix':'Ground-up board, after fix pass 1','fix2':'Ground-up board'}.get(TAG,TAG)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'figure.facecolor':'#fcfcfb','axes.facecolor':'#fcfcfb'})
HEAT = LinearSegmentedColormap.from_list('h', [(1,0.95,0.85,0),(0.98,0.75,0.45,0.55),(0.93,0.42,0.18,0.85),(0.7,0.15,0.05,1),(0.35,0.02,0.0,1)])
allnets=sorted(set([p['net'] for fp in FP for p in fp['pads'] if p['net']]+[s['net'] for s in SEG if s['net']]+[z['net'] for z in ZON if z['net']]))
def netcolor(n, loopnets):
    if n=='GND': return (0.80,0.80,0.80)
    if n in loopnets: return loopnets[n]
    return (0.90,0.90,0.88)
def panel(ax, box, h, cur, L, loopnets, refs, vmax, title):
    m=Model(box, allnets, h=0.05, layers=[L]); lab=m.lab[L]
    img=np.ones(lab.shape+(3,))*0.985
    for nid in np.unique(lab):
        if nid==0: continue
        img[lab==nid]=netcolor(allnets[nid-1], loopnets)
    ext=(box[0],box[0]+lab.shape[1]*0.05,box[2]+lab.shape[0]*0.05,box[2])
    ax.imshow(img,extent=ext,interpolation='nearest')
    c=cur.copy()
    ax.imshow(np.ma.masked_less(c, vmax*0.06), extent=(box[0],box[0]+c.shape[1]*h,box[2]+c.shape[0]*h,box[2]), cmap=HEAT, norm=PowerNorm(0.6,vmin=vmax*0.06,vmax=vmax), interpolation='nearest')
    for fp in FP:
        if fp['ref'] not in refs: continue
        for p in fp['pads']:
            if p['net'] and (L in p['layers'] or '*.Cu' in p['layers']):
                ax.add_patch(Polygon(padpoly(p),fill=False,lw=0.6,ec='#222'))
        if fp['layer']==L and box[0]<fp['x']<box[1] and box[2]<fp['y']<box[3]:
            ax.text(fp['x'],fp['y'],fp['ref'],fontsize=7.5,ha='center',va='center',color='#0b3d91',weight='bold',
                    bbox=dict(boxstyle='round,pad=0.12',fc='white',ec='none',alpha=0.75))
    ax.set_xlim(box[0],box[1]); ax.set_ylim(box[3],box[2]); ax.set_aspect('equal')
    ax.set_title(title,fontsize=9,loc='left',weight='bold'); ax.tick_params(labelsize=7)
def figure(d, mp, fn, title, sub, loopnets, refs, npanels=4):
    box=d['box']; h=d['h']
    pk={L:np.percentile(mp[L],99.7) for L in mp}
    Ls=sorted([L for L in LAYERS if pk.get(L,0)>0.10*max(pk.values())],key=lambda L:-pk[L])[:npanels-1]
    Ls=[L for L in LAYERS if L in Ls]
    plan=sum(mp[L] for L in mp); vmax=max(pk[L] for L in Ls)
    asp=(box[3]-box[2])/(box[1]-box[0]); pw=3.5; ph=min(5.2,max(2.6,pw*asp))
    fig,axs=plt.subplots(1,npanels,figsize=(pw*npanels+0.4,ph+1.0),squeeze=False)
    names={'F.Cu':'F.Cu (top)','In1.Cu':'In1 (GND)','In2.Cu':'In2','In3.Cu':'In3','In4.Cu':'In4 (GND)','B.Cu':'B.Cu (bottom)'}
    panel(axs[0][0],box,h,plan,'F.Cu',loopnets,refs,np.percentile(plan,99.7),'All layers, seen from the top')
    for ax,L in zip(axs[0][1:],Ls): panel(ax,box,h,mp[L],L,loopnets,refs,vmax,names[L])
    for ax in axs[0][1+len(Ls):]: ax.axis('off')
    fig.suptitle(title,x=0.01,y=0.995,ha='left',fontsize=11,weight='bold')
    fig.text(0.01,1-0.42/(ph+1.0),sub,fontsize=8.5,color='#52514e',ha='left',va='top')
    fig.tight_layout(rect=(0,0,1,1-0.62/(ph+1.0))); fig.savefig(fn,dpi=105); plt.close(fig)
    from PIL import Image
    im=Image.open(fn).convert('RGB').quantize(160,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE); im.save(fn,optimize=True)
BLUE=(0.55,0.70,0.95); PURP=(0.80,0.65,0.95); GREEN=(0.65,0.88,0.65); PINK=(0.97,0.72,0.85); TEAL=(0.6,0.88,0.88)
which=sys.argv[1:] or ['hot','gate']
if 'hot' in which:
    hot=json.load(open(f'hot_{TAG}.json')); maps=pickle.load(open(f'hotmaps_{TAG}.pkl','rb'))
    IND={'Q401':'L401','Q402':'L401','Q501':'L501','Q502':'L501','U404':'L402','U504':'L502','U204':'L201'}
    for i,(k,o) in enumerate(hot.items()):
        dev=k.split('(')[1][:-1]; best=min(o['caps'],key=o['caps'].get)
        pn={'Q401':'/USB Port 1/AC_SNS_N','Q402':'/USB Port 1/BAT_SNS_P','Q501':'/USB Port 2/AC_SNS_N','Q502':'/USB Port 2/BAT_SNS_P'}.get(dev,'PACK_P')
        sub=f"Effective {o['eff_all']*1e9:.2f} nH with all caps (ESL incl.)   |   {best}: {o['caps'][best]*1e9:.2f} nH board, carries {o['share'][best]*100:.0f} %   |   loop area {np.linalg.norm(o['area']['all']):.1f} mm²"
        figure(maps[k],maps[k]['mall'],f'{OUT}/hot_{i}_{TAG}.png',f'{LABEL}: {k}',sub,{pn:PURP if 'AC_SNS' in pn else (GREEN if 'BAT' in pn else BLUE)},[dev]+o['caplist']+[IND[dev]])
if 'gate' in which:
    g=json.load(open(f'gate3_{TAG}.json')); gm=pickle.load(open(f'gate3maps_{TAG}.pkl','rb'))
    for i,(k,d) in enumerate(gm.items()):
        p=k[1]; U='U403' if p=='1' else 'U503'
        Q=k.split('(')[1][:-1]; legA='leg A' in k; hs='HS' in k; num=('1' if legA else '2')
        idx={(True,True):'4',(True,False):'5',(False,True):'6',(False,False):'7'}[(legA,hs)]
        rr=f'R{4 if p=="1" else 5}4{idx}'
        drv=f'/USB Port {p}/{"HIDRV" if hs else "LODRV"}{num}'; gnet=f'/USB Port {p}/{"HG" if hs else "LG"}{num}'; ret=f'/USB Port {p}/SW{num}' if hs else 'GND'
        ln={drv:BLUE,gnet:TEAL}
        if hs: ln[ret]=PINK
        o=g[k]
        sub=f"L = {o['L']*1e9:.1f} nH   |   loop area {np.linalg.norm(o['area']):.1f} mm²   (blue = driver trace, teal = gate after {rr}, pink = SW return, grey = GND, heat = HF current)"
        figure(d,d['map'],f'{OUT}/gate_{i}_{TAG}.png',f'{LABEL}: {k}',sub,ln,[U,Q,rr],npanels=4)
print('done')
