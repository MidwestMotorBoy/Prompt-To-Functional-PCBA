"""Copper loss density at 100 W out (SOC 50 %: 7.6 A battery side, 5 A USB side), both boards, port 1 and port 2."""
import numpy as np, os, json
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm, LinearSegmentedColormap
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'figure.facecolor':'#fcfcfb'})
box=(77,123,61,138); IB,IU=7.64,5.0
CM=LinearSegmentedColormap.from_list('s',['#f3efe6','#f6cf9c','#eb8a4a','#c9431d','#7a1408','#2b0300'])
fig,axs=plt.subplots(1,4,figsize=(15.5,6.6))
tot={}
NT=os.environ.get('NTAG','new')
for j,(tag,port) in enumerate((('base',1),(NT,1),('base',2),(NT,2))):
    P=np.load(f'k/lossmap_{tag}_cub{port}.npy')*IB**2+np.load(f'k/lossmap_{tag}_cuu{port}.npy')*IU**2+np.load(f'k/lossmap_{tag}_pack.npy')*IB**2
    H,W=P.shape; b=5; Pb=P[:H//b*b,:W//b*b].reshape(H//b,b,W//b,b).sum((1,3))/(0.5*0.5)*1e3     # mW/mm2
    tot[(tag,port)]=P.sum()
    ax=axs[j]; ax.set_facecolor('#fcfcfb')
    ax.add_patch(plt.Rectangle((78.4,62.82),43.2,74.35,fc='#f3efe6',ec='#898781',lw=0.8,zorder=0))
    im=ax.imshow(np.ma.masked_less(Pb,0.02),extent=(box[0],box[0]+Pb.shape[1]*0.5,box[2]+Pb.shape[0]*0.5,box[2]),cmap=CM,norm=LogNorm(0.02,20),interpolation='nearest',zorder=2)
    ax.set_xlim(77.5,122.5); ax.set_ylim(138,62); ax.set_aspect('equal'); ax.tick_params(labelsize=7)
    ax.set_title(f"{'Current board' if tag=='base' else 'Ground-up board'}, port {port}",fontsize=10,loc='left',weight='bold')
cb=fig.colorbar(im,ax=axs,orientation='horizontal',fraction=0.035,pad=0.06,aspect=60); cb.set_label('Copper loss density, mW per mm² of board (all layers summed), log scale',fontsize=9)
fig.suptitle('Where the copper loss sits at 100 W out, pack at 50 % (7.6 A battery side, 5 A USB side)',x=0.01,ha='left',fontsize=12,weight='bold')
fn=f'img/lossmap_{NT}.png'; fig.savefig(fn,dpi=120,bbox_inches='tight'); plt.close(fig)
from PIL import Image
im=Image.open(fn).convert('RGB').quantize(128,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE); im.save(fn,optimize=True); print(fn,os.path.getsize(fn),{k:round(v*1e3) for k,v in tot.items()})
