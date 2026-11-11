"""strip tracks, vias and copper zones (keep rule areas) from a .kicad_pcb as text; usage: strip.py in out"""
import sys,collections
OLDKO=('0c0e9fcd-921c-4c75-9bd5-cb1e62766f4c','cf3149b8-acea-42c0-b0b3-2bb6b73edcb5','e473e460-a11e-466d-b974-342995372945','8d97034c-1ac6-4f35-8cc0-1e4ac3c808a9','9af5120d-b093-4f02-88b5-871ad9c9d419')
s=open(sys.argv[1],newline='').read()
# top-level children of (kicad_pcb ...)
out=[]; i=s.index('(kicad_pcb')+1; depth=1; start=None; last=i; n=len(s); inq=False; kept=collections.Counter(); dropped=collections.Counter()
res=[s[:i]]
j=i
while j<n:
    c=s[j]
    if inq:
        if c=='\\': j+=2; continue
        if c=='"': inq=False
    elif c=='"': inq=True
    elif c=='(':
        if depth==1: start=j
        depth+=1
    elif c==')':
        depth-=1
        if depth==1:
            blk=s[start:j+1]; head=blk[1:blk.index(' ') if ' ' in blk[:40] else 40].split()[0].strip()
            head=blk[1:].split(None,1)[0].rstrip(')')
            drop = head in('segment','via','arc') or (head=='zone' and '(keepout' not in blk) or (head=='zone' and any(u in blk for u in OLDKO))
            if drop:
                dropped[head]+=1
                # remove the block and the whitespace before it
                pre=s[last:start]
                res.append(pre.rstrip(' \t\r\n') if False else pre[:len(pre)-len(pre)+len(pre.rstrip(' \t'))] )
                # drop trailing newline belonging to this block
                k=j+1
                while k<n and s[k] in '\r\n': k+=1
                last=k
                # ensure previous kept text ends with newline
            else:
                kept[head]+=1
        if depth==0: break
    j+=1
res.append(s[last:])
o=''.join(res)
open(sys.argv[2],'w',newline='').write(o)
print('kept',dict(kept)); print('dropped',dict(dropped)); print(len(s),'->',len(o))
