import json, pickle, numpy as np, sys, os
from loops import *
from caps import caps_between, dist
H = 0.3
TAG=os.environ['TAG']
P1,P2='/USB Port 1/','/USB Port 2/'
DEF=[('P1 VBUS leg (Q401)',P1+'AC_SNS_N','Q401',['2','3','4'],['5','6','7'],99),
     ('P1 PACK leg (Q402)',P1+'BAT_SNS_P','Q402',['2','3','4'],['5','6','7'],99),
     ('P2 VBUS leg (Q501)',P2+'AC_SNS_N','Q501',['2','3','4'],['5','6','7'],99),
     ('P2 PACK leg (Q502)',P2+'BAT_SNS_P','Q502',['2','3','4'],['5','6','7'],99),
     ('P1 5V buck (U404)','PACK_P','U404',['3'],['4'],6.1),
     ('P2 5V buck (U504)','PACK_P','U504',['3'],['4'],6.1),
     ('3V3 buck (U204)','PACK_P','U204',['2'],['1'],6.1)]
res={}; maps={}
only=sys.argv[1:]
for k,(name,pnet,dev,dp,sp_,rad) in enumerate(DEF):
    if only and str(k) not in only: continue
    caps=[c for c in caps_between(pnet) if dist(c,dev)<rad and REF[c]['fp'].split(':')[1] in ESL]
    caps.sort(key=lambda c:dist(c,dev))
    box=autobox([dev]+caps,1.5)
    o,m=hot_loop(name,box,pnet,caps,dev,dp,sp_,h=H)
    o['box']=box; o['caplist']=caps
    print(fmt(o),flush=True)
    best=min(o['caps'],key=o['caps'].get)
    maps[name]={'box':m.box,'h':m.h,'best':best,'mbest':currmap(m,m.curr[best]),'mall':currmap(m,m.curr['all'])}
    res[name]=o; del m
    json.dump(res,open('hot_%s%s.json'%(TAG,'_'.join(only)),'w'),indent=1,default=float)
    pickle.dump(maps,open('hotmaps_%s%s.pkl'%(TAG,'_'.join(only)),'wb'))
