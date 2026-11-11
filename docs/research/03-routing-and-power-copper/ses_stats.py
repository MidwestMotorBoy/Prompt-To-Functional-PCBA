import re,sys,math
t=open(sys.argv[1]).read()
res=re.search(r'\(resolution (\w+) (\d+)\)',t); u=res.group(1); r=int(res.group(2))
scale={'um':1e-3,'mil':0.0254,'mm':1.0,'inch':25.4}[u]/r
L=0;n=0;widths={}
for m in re.finditer(r'\(path (\S+) (\d+)((?:\s+-?\d+)+)\s*\)',t):
    w=int(m.group(2))*scale; pts=[int(x) for x in m.group(3).split()]
    for i in range(0,len(pts)-2,2):
        L+=math.hypot(pts[i+2]-pts[i],pts[i+3]-pts[i+1])*scale; n+=1
        widths[round(w,3)]=widths.get(round(w,3),0)+1
print('segments',n,'length_mm',round(L,1),'vias',len(re.findall(r'\(via ',t))-len(re.findall(r'\(library_out|\(padstack ',t))*0,'widths',widths)
