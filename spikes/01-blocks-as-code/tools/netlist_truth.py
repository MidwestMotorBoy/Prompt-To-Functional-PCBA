"""KiCad sexpr netlist -> truth JSON: {comps:{ref:{...}}, nets:{name:[[ref,pin,pinfunction]]}}"""
import sys,json
sys.path.insert(0,__file__.rsplit('/',1)[0])
from sx import parse,find,first,get,val
def load(path):
    t=parse(open(path).read())
    comps={}
    for c in find(first(t,'components'),'comp'):
        ref=get(c,'ref')
        ls=first(c,'libsource')
        sp=first(c,'sheetpath')
        fields={get(f,'name'):(val(f[2]) if len(f)>2 else '') for f in find(first(c,'fields',['fields']),'field')}
        props={val(p[1][1]):val(p[2][1]) for p in find(c,'property') if len(p)>2}
        comps[ref]=dict(value=get(c,'value'),footprint=get(c,'footprint',''),lib=get(ls,'lib')+':'+get(ls,'part'),
                        sheet=get(sp,'names'),fields=fields,props=props)
    nets={}
    for n in find(first(t,'nets'),'net'):
        nets[get(n,'name')]=sorted([get(x,'ref'),get(x,'pin'),get(x,'pinfunction','')] for x in find(n,'node'))
    return dict(comps=comps,nets=nets)
if __name__=='__main__':
    json.dump(load(sys.argv[1]),open(sys.argv[2],'w'),indent=1)
