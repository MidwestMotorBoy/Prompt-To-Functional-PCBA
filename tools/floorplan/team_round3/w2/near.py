"""near.py <placement.json|-> [skp.json]: parts within 2.5 mm (courtyard gap) of U403 U503 U401 U501; '-' = hand board"""
import sys, json
E='/home/claude/prompt-to-functional-pcba/tools/floorplan/example/monolith'
D=json.load(open(E+'/board_dump.json')); fp={f['ref']:f for f in D['fps']}
P={}
for a in sys.argv[1:]:
    if a!='-': P.update(json.load(open(a)))
def turn(v,q):
    x,y=v
    for _ in range(q%4): x,y=-y,x
    return x,y
def court(r):
    f=fp[r]; c=f.get('court') or [f['x']-.5,f['y']-.5,f['x']+.5,f['y']+.5]
    if r not in P: return c, f['side']
    x,y,a=P[r][:3]; q=int(a)//90
    a_=turn((c[0]-f['x'],c[1]-f['y']),q); b_=turn((c[2]-f['x'],c[3]-f['y']),q)
    side=f['side']
    if len(P[r])>3 and isinstance(P[r][3],str): side=P[r][3]
    return [x+min(a_[0],b_[0]),y+min(a_[1],b_[1]),x+max(a_[0],b_[0]),y+max(a_[1],b_[1])], side
def gap(a,b): return max(a[0]-b[2],b[0]-a[2],a[1]-b[3],b[1]-a[3],0)
out=[]
for ic in ('U403','U503','U401','U501'):
    c,sd=court(ic); n=sum(1 for r in fp if r!=ic and court(r)[1]==sd and gap(court(r)[0],c)<=2.5)
    out.append(f'{ic}:{n}')
print(' '.join(out))
