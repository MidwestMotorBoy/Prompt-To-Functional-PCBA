import pickle, sx
from collections import Counter, defaultdict
b=pickle.load(open('board.pkl','rb'))
F=sx.find; G=sx.get
# outline
for g in F(b,'gr_line')+F(b,'gr_poly')+F(b,'gr_rect')+F(b,'gr_arc'):
    print(g[0], G(g,'layer'), G(g,'start'), G(g,'end'), (G(g,'pts') or [])[:6])
zs=F(b,'zone')
c=Counter()
for z in zs:
    name=G(z,'name',[None,''])[1]; net=G(z,'net',[None,''])[1:] ; lay=G(z,'layer') or G(z,'layers'); ko=G(z,'keepout') is not None
    c[(name,str(net),str(lay[1:]),ko)]+=1
for k,v in sorted(c.items(),key=lambda kv:str(kv[0])): print(v,k)
