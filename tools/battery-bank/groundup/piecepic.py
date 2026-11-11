"""piecepic.py cu.json out.png x0,y0,x1,y1 [layer=In2] [netsuffix=PACK_P] [hilite net suffix]: plane pieces of one net, each piece its own colour."""
import json, sys
from PIL import Image, ImageDraw
d=json.load(open(sys.argv[1]))
x0,y0,x1,y1=map(float,sys.argv[3].split(',')); sc=70
L=sys.argv[4] if len(sys.argv)>4 else 'In2'; NS=sys.argv[5] if len(sys.argv)>5 else 'PACK_P'; HI=sys.argv[6] if len(sys.argv)>6 else '@@'
im=Image.new('RGB',(int((x1-x0)*sc),int((y1-y0)*sc)),'white'); dr=ImageDraw.Draw(im)
px=lambda x,y:((x-x0)*sc,(y-y0)*sc)
cols=['#c9b6e8','#f4b6b6','#b6e8c1','#f1e3a0','#a0d8f1','#f1a0e0','#bbbbbb']
k=0
for f in d['fills']:
    if f['l']!=L or not f['net'].endswith(NS): continue
    for poly in f['polys']:
        if len(poly[0])<3: continue
        xs=[p[0] for p in poly[0]]; ys=[p[1] for p in poly[0]]
        c=cols[k%len(cols)]; k+=1
        dr.polygon([px(*p) for p in poly[0]],fill=c)
        for h in poly[1:]:
            if len(h)>2: dr.polygon([px(*p) for p in h],fill='white')
        print(k,c,'bbox %.1f %.1f %.1f %.1f'%(min(xs),min(ys),max(xs),max(ys)))
for t in d['tracks']:
    if t['l']==L:
        dr.line([px(t['x1'],t['y1']),px(t['x2'],t['y2'])],fill='#c00' if t['net'].endswith(HI) else '#444',width=max(2,int(t['w']*sc)))
for v in d['vias']:
    x,y=px(v['x'],v['y']); r=0.225*sc
    dr.ellipse([x-r,y-r,x+r,y+r],outline='#006' if v['net'].endswith(NS) else '#090',width=3)
gx=int(x0)
while gx<=x1:
    dr.line([px(gx,y0),px(gx,y1)],fill='#ddd'); dr.text(px(gx+0.05,y0+0.05),str(gx),fill='black'); gx+=1
gy=int(y0)
while gy<=y1:
    dr.line([px(x0,gy),px(x1,gy)],fill='#ddd'); dr.text(px(x0+0.05,gy+0.05),str(gy),fill='black'); gy+=1
im.save(sys.argv[2])
