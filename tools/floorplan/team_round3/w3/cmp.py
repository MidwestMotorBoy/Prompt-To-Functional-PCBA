import json,sys,math,collections
D=json.load(open('/home/claude/work/hp/q7s2_fz_dump.json'))
a=json.load(open(sys.argv[1])); b=json.load(open(sys.argv[2]))
mv=sorted(((math.hypot(a[r][0]-b[r][0],a[r][1]-b[r][1]),r) for r in a if r in b),reverse=True)
print("moved >2mm:",sum(1 for d,r in mv if d>2),"; >5mm:",sum(1 for d,r in mv if d>5)); print([(r,round(d,1)) for d,r in mv[:30]])
pos0={f['ref']:(f['x'],f['y']) for f in D['fps']}
def hp(pl):
    nets=collections.defaultdict(list)
    for p in D['pads']:
        if not p['net']: continue
        r=p['ref']; x0,y0=pos0[r]; vx,vy=p['x']-x0,p['y']-y0
        if r in pl:
            x,y,ang=pl[r][:3]; k=(int(ang)//90)%4
            for _ in range(k): vx,vy=-vy,vx
        else: x,y=x0,y0
        nets[p['net']].append((x+vx,y+vy))
    return {n:(max(q[0] for q in v)-min(q[0] for q in v)+max(q[1] for q in v)-min(q[1] for q in v)) for n,v in nets.items() if len(v)>=2}
ha,hb=hp(a),hp(b); dl=sorted(((hb[n]-ha[n],n) for n in ha),reverse=True)
print([(n,round(d,1),round(hb[n],1)) for d,n in dl[:25]])
