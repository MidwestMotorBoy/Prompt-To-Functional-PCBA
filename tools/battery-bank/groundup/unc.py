import json,re,sys,collections
d=json.load(open(sys.argv[1])); c=collections.Counter()
for u in d['unconnected_items']:
    a,b=u['items'][0],u['items'][1]
    m=re.search(r'\[(.*?)\]',a['description']); n=m.group(1) if m else '?'
    c[n]+=1
    if n in('GND','3V3','PACK_P') and 'all' not in sys.argv: continue
    print(n,'|',a['description'][:46],'(%.2f,%.2f)'%(a['pos']['x'],a['pos']['y']),'->',b['description'][:46],'(%.2f,%.2f)'%(b['pos']['x'],b['pos']['y']))
print(dict(c))
