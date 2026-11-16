import re
def parse(text):
    tok=re.compile(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+')
    stack=[[]]
    for m in tok.finditer(text):
        t=m.group(0)
        if t=='(':
            stack.append([])
        elif t==')':
            x=stack.pop(); stack[-1].append(x)
        elif t[0]=='"':
            stack[-1].append(t[1:-1].replace('\\"','"'))
        else:
            stack[-1].append(t)
    return stack[0][0]
def find(node,name):
    return [c for c in node if isinstance(c,list) and c and c[0]==name]
def get(node,name,default=None):
    r=find(node,name); return r[0] if r else default
