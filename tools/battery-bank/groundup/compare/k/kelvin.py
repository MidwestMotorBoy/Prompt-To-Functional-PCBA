import sys, os, json, time
from solve import *
import pyamg
RES=float(os.environ.get('RES','0.1'))
box=(77,123,61,138)
P1,P2='/USB Port 1/','/USB Port 2/'
built={}
def B_(net):
    if net not in built:
        t=time.time(); built[net]=build(net,box,RES); built[net]['ml']=None
        print('  built',net,built[net]['n'],'nodes %.0fs'%(time.time()-t),flush=True)
    return built[net]
def nodes(B,ref,nums,net):
    nums=[x for x in nums if any(p['num']==x and p['net']==net for p in REF[ref]['pads'])]
    return padnodes(B,ref,nums,REF[ref]['layer'])
def solve2(B,src,snk,I):
    n=B['n']; b=np.zeros(n)
    for i in src: b[i]+=I/len(src)
    d=np.zeros(n); d[snk]=1e6
    G=(B['G']+sp.diags(d)+sp.identity(n)*1e-9).tocsr()
    ml=pyamg.smoothed_aggregation_solver(G,max_coarse=500)
    V=ml.solve(b,tol=1e-10,accel='cg',maxiter=400)
    return V
# (name, Rs, plus net, far end (ref,pads), sense pad (ref,pads), tap (ref,pad), minus net, sense pad, far end, tap, I)
def port(p,P):
    return [
     (f'P{p} RBAT (BQ25756 SRP/SRN)',5e-3, P+'BAT_SNS_P',(f'Q{p+3}02',['2','3','4']),(f'R{p+3}27',['1']),(f'R{p+3}28','1'),
        'PACK_P',(f'R{p+3}27',['2']),('Q102',['1','2','3']),(f'R{p+3}29','1'),9.0),
     (f'P{p} RAC (BQ25756 ACP/ACN)',5e-3, P+'PPHV',(f'U{p+3}01',['20']),(f'R{p+3}24',['1']),(f'R{p+3}25','1'),
        P+'AC_SNS_N',(f'R{p+3}24',['2']),(f'Q{p+3}01',['2','3','4']),(f'R{p+3}26','1'),5.0)]
CASES=port(1,P1)+port(2,P2)+[
     ('Gauge shunt RS101, port 1 current',1e-3,'CELL_N',('J108',['1']),('RS101',['1']),('R107','1'),'GND',('RS101',['2']),('Q401',['5','6','7']),('R108','1'),9.0),
     ('Gauge shunt RS101, port 2 current',1e-3,'CELL_N',('J108',['1']),('RS101',['1']),('R107','1'),'GND',('RS101',['2']),('Q501',['5','6','7']),('R108','1'),9.0)]
out={}
for name,Rs,pn,pfar,psns,ptap,mn,msns,mfar,mtap,I in CASES:
    Bp=B_(pn); src=nodes(Bp,*pfar,pn); snk=nodes(Bp,*psns,pn); tap=nodes(Bp,ptap[0],[ptap[1]],pn)
    if not(src and snk and tap): print('NO NODES +',name,len(src),len(snk),len(tap)); continue
    V=solve2(Bp,src,snk,I); dp=np.mean(V[tap])-np.mean(V[snk]); Rp=(np.mean(V[src])-np.mean(V[snk]))/I
    Bm=B_(mn); src=nodes(Bm,*msns,mn); snk=nodes(Bm,*mfar,mn); tap=nodes(Bm,mtap[0],[mtap[1]],mn)
    if not(src and snk and tap): print('NO NODES -',name,len(src),len(snk),len(tap)); continue
    V=solve2(Bm,src,snk,I); dm=np.mean(V[tap])-np.mean(V[src]); Rm=(np.mean(V[src])-np.mean(V[snk]))/I
    # spread of voltage across the sense pad itself (how well defined "pad voltage" is)
    err=(dp-dm)/(I*Rs)
    out[name]=dict(Rs=Rs,I=I,dplus_uV=dp*1e6,dminus_uV=dm*1e6,err_pct=err*100,Rplus_mohm=Rp*1e3,Rminus_mohm=Rm*1e3)
    print(f'{name}: + tap {dp*1e6:+.0f} uV, - tap {dm*1e6:+.0f} uV at {I} A -> error {err*100:+.2f} %  (path R {Rp*1e3:.2f} / {Rm*1e3:.2f} mOhm)',flush=True)
# cross-port offset: other port's 9 A on PACK_P / GND seen at this port's taps
for p,o in ((1,2),(2,1)):
    Bm=B_('PACK_P'); src=nodes(Bm,f'R{o+3}27',['2'],'PACK_P'); snk=nodes(Bm,'Q102',['1','2','3'],'PACK_P')
    V=solve2(Bm,src,snk,9.0); tap=nodes(Bm,f'R{p+3}29',['1'],'PACK_P'); pad=nodes(Bm,f'R{p+3}27',['2'],'PACK_P')
    d=np.mean(V[tap])-np.mean(V[pad]); out[f'P{p} RBAT offset from 9 A on port {o}']=dict(uV=d*1e6,equiv_mA=d/5e-3*1e3)
    print(f'P{p} RBAT: 9 A on port {o} shifts the reading by {d*1e6:+.1f} uV = {d/5e-3*1e3:+.1f} mA',flush=True)
json.dump(out,open('kelvin_%s.json'%os.environ['TAG'],'w'),indent=1,default=float)
