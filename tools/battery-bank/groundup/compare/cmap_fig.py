"""Where the switching copper runs relative to analog and bus signals: one PNG per board (4 routing layers)."""
import numpy as np, os
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from peec import Model, LAYERS, FP, SEG, VIA, ZON
from victims import category
from coup import GROUPS, allnets
TAG=os.environ['TAG']; LABEL={'base':'Current board','new':'Ground-up board, first version','fix':'Ground-up board, after fix pass 1','fix2':'Ground-up board'}.get(TAG,TAG)
box=(78.2,121.8,62.6,137.4); h=0.05
agg=set(n for _,ns,_ in GROUPS for n in ns)
ANA={'Current sense','Charger analog','Regulator feedback','Gauge analog'}
col={}
for i,n in enumerate(allnets):
    c=category(n)
    if n in agg: col[i+1]=(0.82,0.16,0.14)
    elif c in ANA: col[i+1]=(0.16,0.47,0.84)
    elif c in ('I2C / SMBus','USB CC'): col[i+1]=(0.0,0.51,0.0)
    elif c: col[i+1]=(0.38,0.31,0.84)
    elif n in ('GND',): col[i+1]=(0.90,0.90,0.88)
    else: col[i+1]=(0.80,0.80,0.77)
m=Model(box,allnets,h=h)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'figure.facecolor':'#fcfcfb'})
Ls=['F.Cu','In2.Cu','In3.Cu','B.Cu']; names={'F.Cu':'F.Cu (top)','In2.Cu':'In2','In3.Cu':'In3','B.Cu':'B.Cu (bottom, seen from the top)'}
fig,axs=plt.subplots(1,4,figsize=(15.5,7.6))
for ax,L in zip(axs,Ls):
    lab=np.asarray(m.lab[L]); img=np.ones(lab.shape+(3,))*0.985
    for nid in np.unique(lab):
        if nid: img[lab==nid]=col[nid]
    ax.imshow(img,extent=(box[0],box[1],box[3],box[2]),interpolation='nearest'); ax.set_title(names[L],fontsize=10,loc='left',weight='bold'); ax.tick_params(labelsize=7)
fig.legend(handles=[Patch(fc=(0.82,0.16,0.14),label='Switching copper: SW nodes, boot and high-side gate nets'),Patch(fc=(0.16,0.47,0.84),label='Analog: current sense, feedback, gauge inputs, NTC'),
    Patch(fc=(0.0,0.51,0.0),label='I2C, SMBus and USB CC'),Patch(fc=(0.38,0.31,0.84),label='Control, debug, RF'),Patch(fc=(0.80,0.80,0.77),label='Other copper'),Patch(fc=(0.90,0.90,0.88),label='GND')],
    loc='lower left',ncol=3,fontsize=8.5,frameon=False,bbox_to_anchor=(0.01,0.0))
fig.suptitle(f'{LABEL}: switching copper and the signals it can disturb',x=0.01,ha='left',fontsize=12,weight='bold')
fig.tight_layout(rect=(0,0.07,1,0.96)); fn=f'img/cmap_{TAG}.png'; os.makedirs('img',exist_ok=True); fig.savefig(fn,dpi=170); plt.close(fig)
from PIL import Image
im=Image.open(fn).convert('RGB').quantize(64,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE); im.save(fn,optimize=True); print(fn,os.path.getsize(fn))
