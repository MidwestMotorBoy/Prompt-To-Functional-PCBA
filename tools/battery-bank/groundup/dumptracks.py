import pcbnew,sys,json
b=pcbnew.LoadBoard(sys.argv[1]); out=[]
for t in b.GetTracks():
    if t.GetClass()=='PCB_VIA':
        p=t.GetPosition(); out.append(dict(k='v',x=p.x/1e6,y=p.y/1e6,d=t.GetWidth(pcbnew.F_Cu)/1e6,net=str(t.GetNetname())))
    else:
        s=t.GetStart(); e=t.GetEnd(); out.append(dict(k='t',x1=s.x/1e6,y1=s.y/1e6,x2=e.x/1e6,y2=e.y/1e6,w=t.GetWidth()/1e6,l=str(b.GetLayerName(t.GetLayer()))[:3],net=str(t.GetNetname())))
json.dump(out,open(sys.argv[2],'w'))
