import json,sys,collections
D=json.load(open('/home/claude/work/hp/q7s2_fz_dump.json')); pos0={f['ref']:(f['x'],f['y']) for f in D['fps']}
def hp(pl):
    nets=collections.defaultdict(list)
    for p in D['pads']:
        if not p['net']: continue
        r=p['ref']; x0,y0=pos0[r]; vx,vy=p['x']-x0,p['y']-y0
        if pl and r in pl:
            x,y,ang=pl[r][:3]; k=(int(ang)//90)%4
            for _ in range(k): vx,vy=-vy,vx
        else: x,y=x0,y0
        nets[p['net']].append((x+vx,y+vy,r))
    return {n:(round(max(q[0] for q in v)-min(q[0] for q in v)+max(q[1] for q in v)-min(q[1] for q in v),1),len(v),sorted({q[2] for q in v})) for n,v in nets.items() if len(v)>=2}
pl=json.load(open(sys.argv[1])); h=hp(pl)
H=json.load(open('/home/claude/prompt-to-functional-pcba/tools/floorplan/example/monolith/board_dump.json')); pos1={f['ref']:(f['x'],f['y']) for f in H['fps']}
sm=[(v[0],n,v[1],v[2]) for n,v in h.items() if v[1]<=3]; sm.sort(reverse=True)
print("2-3 pad nets total", round(sum(s[0] for s in sm)), "over 6mm:", sum(1 for s in sm if s[0]>6))
for s in sm[:25]: print(s)
