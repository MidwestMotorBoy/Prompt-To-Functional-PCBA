import json,sys,collections
d=json.load(open(sys.argv[1]))
V=d.get('violations',[]); U=d.get('unconnected_items',[]); S=d.get('schematic_parity',[])
c=collections.Counter((v['type'],v['severity']) for v in V)
print('violations',len(V),'unconnected',len(U),'parity',len(S))
for k,v in sorted(c.items(),key=lambda kv:-kv[1]): print('  ',v,k)
show=sys.argv[2:] 
for v in V:
    if v['type'] in show or 'all' in show:
        print(v['type'],'|',v['description'][:70],'|',' ; '.join(f"{i['description'][:60]} @({i['pos']['x']:.2f},{i['pos']['y']:.2f})" for i in v['items']))
if 'parity' in show:
    for v in S: print(v)
