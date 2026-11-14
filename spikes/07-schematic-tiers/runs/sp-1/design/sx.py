"""Minimal S-expression reader for KiCad files."""
def parse(text):
    i=0;n=len(text);stack=[[]]
    while i<n:
        c=text[i]
        if c=='(':
            stack.append([]);i+=1
        elif c==')':
            x=stack.pop();stack[-1].append(x);i+=1
        elif c=='"':
            j=i+1;buf=[]
            while text[j]!='"':
                if text[j]=='\\':
                    buf.append(text[j+1]);j+=2
                else:
                    buf.append(text[j]);j+=1
            stack[-1].append(('s',''.join(buf)));i=j+1
        elif c.isspace():
            i+=1
        else:
            j=i
            while j<n and not text[j].isspace() and text[j] not in '()':
                j+=1
            stack[-1].append(text[i:j]);i=j
    return stack[0][0]
def val(x):
    return x[1] if isinstance(x,tuple) else x
def find(node,key):
    return [c for c in node[1:] if isinstance(c,list) and c and c[0]==key]
def first(node,key,default=None):
    f=find(node,key)
    return f[0] if f else default
def get(node,key,default=None):
    f=first(node,key)
    return val(f[1]) if f and len(f)>1 else default
