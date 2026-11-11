"""seglib.py: helpers to build handadd 'del' specs from a dumpcu json.  dels(d, net_suffix, layer, pred) -> (spec items, list of
collateral segments that the endpoint match also removes and that the caller has to re-add)."""
import json
def segs(d, net, L): return [t for t in d['tracks'] if t['net'].endswith(net) and t['l'] == L]
def dels(d, net, L, pred):
    S = segs(d, net, L); full = S[0]['net'] if S else net
    kill = [t for t in S if pred(t)]; pts = []; gone = []
    for t in kill:
        if any(abs(t[a] - p[0]) < 2e-3 and abs(t[b] - p[1]) < 2e-3 for p in pts for a, b in (('x1', 'y1'), ('x2', 'y2'))): continue
        pts.append((t['x1'], t['y1']))
    for t in S:
        if any(abs(t[a] - p[0]) < 2e-3 and abs(t[b] - p[1]) < 2e-3 for p in pts for a, b in (('x1', 'y1'), ('x2', 'y2'))): gone.append(t)
    extra = [t for t in gone if t not in kill]
    return [{"del": [p[0], p[1]], "net": full, "what": L} for p in pts], extra
def readd(extra): return [{"net": t['net'], "layer": t['l'], "w": t['w'], "pts": [[t['x1'], t['y1']], [t['x2'], t['y2']]]} for t in extra]
def inbox(t, b): return all(b[0] <= t[x] <= b[2] and b[1] <= t[y] <= b[3] for x, y in (('x1', 'y1'), ('x2', 'y2')))
def vias(d, net, b=None): return [v for v in d['vias'] if v['net'].endswith(net) and (b is None or (b[0] <= v['x'] <= b[2] and b[1] <= v['y'] <= b[3]))]
def delvia(v): return {"del": [v['x'], v['y']], "net": v['net'], "what": "via"}
