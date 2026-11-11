import pcbnew,sys
b=pcbnew.LoadBoard(sys.argv[1])
for d in b.GetDrawings():
    if d.GetClass() in ('PCB_TEXT','PCB_TEXTBOX') and 'Silk' in d.GetLayerName():
        p=d.GetPosition(); bb=d.GetBoundingBox()
        print('TEXT',d.GetLayerName(),round(p.x/1e6,2),round(p.y/1e6,2),repr(d.GetText()[:40]),round(bb.GetWidth()/1e6,1),round(bb.GetHeight()/1e6,1))
n=0;vis=[]
for f in b.GetFootprints():
    r=f.Reference()
    if r.IsVisible(): vis.append(f.GetReference())
print('visible refs',len(vis),' '.join(sorted(vis)))
import collections
c=collections.Counter(d.GetClass()+':'+d.GetLayerName() for d in b.GetDrawings())
print(c)
