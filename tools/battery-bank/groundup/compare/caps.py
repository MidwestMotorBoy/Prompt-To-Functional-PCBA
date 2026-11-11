from board import *
import math
def caps_between(pnet,nnet='GND'):
    out=[]
    for d in FP:
        if not d['ref'] or not d['ref'].startswith('C'): continue
        nets={p['net'] for p in d['pads']}
        if pnet in nets and nnet in nets: out.append(d['ref'])
    return out
def dist(a,b): return math.hypot(REF[a]['x']-REF[b]['x'],REF[a]['y']-REF[b]['y'])
if __name__=='__main__':
    for pn,dev in (('/USB Port 1/AC_SNS_N','Q401'),('/USB Port 1/BAT_SNS_P','Q402'),('/USB Port 2/AC_SNS_N','Q501'),('/USB Port 2/BAT_SNS_P','Q502'),('PACK_P','U404'),('PACK_P','U504'),('PACK_P','U204')):
        cs=sorted(caps_between(pn),key=lambda c:dist(c,dev))
        print(pn,dev,[(c,round(dist(c,dev),1),REF[c]['val'],REF[c]['fp'].split(':')[1][2:6],REF[c]['layer'][0]) for c in cs if dist(c,dev)<14])
    for d in ('U404','U504','U204','Q401','Q402'):
        print(d,[(p['num'],p['net'].split('/')[-1]) for p in REF[d]['pads']])
