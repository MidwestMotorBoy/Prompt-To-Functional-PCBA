import sys, re, json, os
sys.path.insert(0, sys.argv[2])
pcb_path = sys.argv[1]
txt = open(pcb_path).read()
def parse(s):
    tok = re.findall(r'"(?:[^"\\]|\\.)*"|[()]|[^\s()]+', s)
    st=[[]]
    for t in tok:
        if t=='(':
            n=[]; st[-1].append(n); st.append(n)
        elif t==')': st.pop()
        else: st[-1].append(t[1:-1] if t.startswith('"') else t)
    return st[0][0]
root = parse(txt)
fps=[]
for n in root:
    if isinstance(n,list) and n and n[0]=='footprint':
        d={'fp':n[1],'pads':{}}
        for c in n:
            if isinstance(c,list):
                if c[0]=='property' and c[1]=='Reference': d['ref']=c[2]
                if c[0]=='property' and c[1]=='Value': d['val']=c[2]
                if c[0]=='at': d['at']=c[1:]
                if c[0]=='layer': d['layer']=c[1]
                if c[0]=='pad':
                    net=[x for x in c if isinstance(x,list) and x[0]=='net']
                    if net: d['pads'][c[1]]=net[0][-1]
        fps.append(d)
fps=[f for f in fps if f.get('pads')]
nets={}
for f in fps:
    for p,nn in f['pads'].items(): nets.setdefault(nn,[]).append(f"{f['ref']}.{p}")
enc={}
enc['raw_kicad_pcb']=txt
sch=''.join(open(os.path.join(os.path.dirname(pcb_path),x)).read() for x in os.listdir(os.path.dirname(pcb_path)) if x.endswith('.kicad_sch'))
enc['raw_kicad_sch_all_sheets']=sch
enc['json_verbose']=json.dumps({'components':[{'reference':f['ref'],'value':f.get('val'),'footprint':f['fp'],'pins':[{'pin':p,'net':n} for p,n in f['pads'].items()]} for f in fps]},indent=1)
enc['json_compact']=json.dumps({f['ref']:[f.get('val'),f['fp'].split(':')[-1],f['pads']] for f in fps},separators=(',',':'))
enc['net_centric_text']='\n'.join(f"{n}: {' '.join(sorted(set(v)))}" for n,v in sorted(nets.items()))+'\n'+'\n'.join(f"{f['ref']} {f.get('val')} {f['fp'].split(':')[-1]}" for f in fps)
# compact: nets with passives folded; group identical 2-pin parts
def kind(r): return re.match(r'[A-Za-z]+',r).group(0)
lines=[]
for f in fps:
    ps=list(f['pads'].items())
    if len(set(f['pads'].values()))<=2 and kind(f['ref']) in('R','C','L','D','FB'):
        u=sorted(set(f['pads'].values()))
        lines.append(f"{f['ref']} {f.get('val')} {' '.join(u)}")
    else:
        lines.append(f"{f['ref']} {f.get('val')}: "+' '.join(f"{p}={n}" for p,n in ps))
enc['component_centric_compact']='\n'.join(lines)
enc['placement_table']='\n'.join(f"{f['ref']} {f['fp'].split(':')[-1]} {' '.join(f.get('at',[]))} {f.get('layer','')}" for f in fps)
# block summary: only ICs/connectors/FETs with pin maps, passives counted
big=[l for f,l in zip(fps,lines) if kind(f['ref']) not in('R','C','L','D','FB','TP','H')]
from collections import Counter
cnt=Counter(kind(f['ref']) for f in fps)
enc['summary_ics_only']='\n'.join(big)+'\ncounts: '+json.dumps(cnt)
import os
os.makedirs('out',exist_ok=True)
for k,v in enc.items(): open('out/'+k+'.txt','w').write(v)
print(f"parts={len(fps)} nets={len(nets)} pads={sum(len(f['pads']) for f in fps)}")
