"""cmp_place.py a.json b.json [tol]: per-part diff of two groundup-format placements {ref:[x,y,rot]}"""
import json,sys
A=json.load(open(sys.argv[1])); B=json.load(open(sys.argv[2])); tol=float(sys.argv[3]) if len(sys.argv)>3 else 1e-3
n=0
for r in sorted(set(A)|set(B)):
    a=A.get(r); b=B.get(r)
    if a is None or b is None: print(r,'only in',sys.argv[1] if b is None else sys.argv[2]); n+=1; continue
    if abs(a[0]-b[0])>tol or abs(a[1]-b[1])>tol or abs((a[2]-b[2]+180)%360-180)>1e-3:
        print(f'{r}: {a} vs {b}  d=({b[0]-a[0]:+.3f},{b[1]-a[1]:+.3f})'); n+=1
print(n,'differ of',len(A))
