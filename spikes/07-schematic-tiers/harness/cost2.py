import json,sys,glob
sys.path.insert(0,'.')
from cost import run
from datetime import datetime
D='/root/.claude/projects/-home-claude/62ac6e90-8ed9-5653-9466-d049a0733b8a/subagents'
def active(f,gap=300):
    ts=[]
    for l in open(f):
        d=json.loads(l)
        if d.get("timestamp"): ts.append(datetime.fromisoformat(d["timestamp"].replace("Z","+00:00")))
    ts.sort(); s=0
    for a,b in zip(ts,ts[1:]):
        g=(b-a).total_seconds()
        if g<gap: s+=g
    return s/60
runs={"ss-1":["a6ea878556739cc30"],"ss-2":["afec720effab0da02"],"sb-1":["ad28a417da1f2df5d"],"sb-2":["ad8c0c9fd4e335531"],
"hi-1":["a4aa2963b32d55c67"],"hi-2":["a6fc17cf779d7f019"],"mx-1":["aabeef1c3b9dffc99"],"mx-2":["a2aa2a6e436c4f88a"],
"gm-1":["ac883e85cc0d79769"],"gm-2":["a56b0f97597959e46"],"gh-1":["a8d408078dac89ac5"],"gh-2":["a334195f90308a912"],
"sp-1":["aa28ebb54bdd1f756","abeefd9d014990e06","a0539080f8aa77380","a7d93ec273d159c33","a38abe1cfdae33f18"],
"sp-2":["a26e05d9da6ec3862","a45a261ad72497eeb","a9964dfe6d86e8da7","a29ffcaa8215653f2","a94c1274b34cb7007"]}
out={}
for r,ids in runs.items():
    tot=dict(usd=0,out=0,calls=0,act=0)
    for i in ids:
        fs=glob.glob(f"{D}/*{i}*.jsonl")
        if not fs: print("missing",r,i); continue
        x=run(fs[0]); tot["usd"]+=x["usd"]; tot["out"]+=x["out"]; tot["calls"]+=x["calls"]; tot["act"]+=active(fs[0])
    out[r]=tot; print(r, round(tot["usd"],2), tot["out"], tot["calls"], round(tot["act"],1))
json.dump(out,open("costs_selfloop.json","w"),indent=1)
