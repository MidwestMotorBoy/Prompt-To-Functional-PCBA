import json,sys
exec(open('/home/claude/work/team/w3/measure.py').read().split('def near')[0])
pl=json.load(open(sys.argv[1])); B=boxes(pl,D)
for r in sys.argv[2:]:
    b=B[r]; print(r, [round(v,2) for v in b[:4]], b[4])
    for kk in D['keepouts']:
        if not kk.get('no_footprints'): continue
        if b[4] not in kk['layers']: continue
        k=kk['box']; ox=min(b[2],k[2])-max(b[0],k[0]); oy=min(b[3],k[3])-max(b[1],k[1])
        if ox>0 and oy>0: print('   KO',kk.get('name'),[round(v,2) for v in k],round(ox,2),round(oy,2))
