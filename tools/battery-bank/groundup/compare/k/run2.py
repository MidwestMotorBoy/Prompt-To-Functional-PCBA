from solve import *
import sys
box=(77,123,61,138)
P1,P2='/USB Port 1/','/USB Port 2/'
cases=[
 ('PACK_P','Q102',['1','2','3'],'F.Cu','R427',['2'],'F.Cu',9.0),
 ('PACK_P','Q102',['1','2','3'],'F.Cu','R527',['2'],'F.Cu',9.0),
 ('/Cells and Gauge/CELL_P','F102',['2'],'F.Cu','Q101',['1','2','3'],'F.Cu',9.0),
 ('/Cells and Gauge/CELL_P_RAW','J112',['1'],'F.Cu','F102',['1'],'F.Cu',9.0),
 ('CELL_N','J108',['1'],'F.Cu','RS101',['1'],'F.Cu',9.0),
 ('/Cells and Gauge/FET_MID','Q101',['5','6','7','8'],'F.Cu','Q102',['5','6','7','8'],'F.Cu',9.0),
 (P1+'VBUS','J401',['A4','A9','B4','B9'],'F.Cu','U401',['23','32'],'F.Cu',5.0),
 (P2+'VBUS','J501',['A4','A9','B4','B9'],'F.Cu','U501',['23','32'],'F.Cu',5.0),
 (P1+'AC_SNS_N','R424',['2'],'F.Cu','Q401',['2','3','4'],'F.Cu',5.0),
 (P2+'AC_SNS_N','R524',['2'],'F.Cu','Q501',['2','3','4'],'F.Cu',5.0),
 (P1+'BAT_SNS_P','R427',['1'],'F.Cu','Q402',['2','3','4'],'F.Cu',9.0),
 (P2+'BAT_SNS_P','R527',['1'],'F.Cu','Q502',['2','3','4'],'F.Cu',9.0),
 (P1+'PPHV','U401',['20'],'F.Cu','R424',['1'],'F.Cu',5.0),
 (P2+'PPHV','U501',['20'],'F.Cu','R524',['1'],'F.Cu',5.0),
 ('GND','RS101',['2'],'F.Cu','Q401',['5','6','7'],'F.Cu',9.0),
 ('GND','RS101',['2'],'F.Cu','Q501',['5','6','7'],'F.Cu',9.0),
]
only=sys.argv[1:] 
built={}
for k,(net,a,an,al,b,bn,bl,I) in enumerate(cases):
    if only and str(k) not in only: continue
    if net not in built: built[net]=build(net,box)
    B=built[net]
    # only use pads on given nets
    an=[x for x in an if any(p['num']==x and p['net']==net for p in REF[a]['pads'])]
    bn=[x for x in bn if any(p['num']==x and p['net']==net for p in REF[b]['pads'])]
    src=padnodes(B,a,an,al); snk=padnodes(B,b,bn,bl)
    if not src or not snk: print('NO NODES',net,a,an,b,bn); continue
    V,R=solve(B,src,snk,I)
    print(f'[{k}] {net} {a}{an}->{b}{bn}: R={R*1e3:.2f} mOhm; @{I}A drop {R*I*1e3:.0f} mV, loss {R*I*I:.2f} W')
    for L,(pw,pts) in hotspots(B,V,I).items():
        if pw>5: print('     ',L,'loss %.0f mW'%pw,'peak A/mm',[(float(x),float(y),round(float(j),1)) for x,y,j in pts[:2]])
    vc=viacur(B,V,I); print('      top vias A',[(round(float(c),2),round(x,2),round(y,2),La[:3]+'-'+Lb[:3]) for c,x,y,La,Lb in vc[:4]])
