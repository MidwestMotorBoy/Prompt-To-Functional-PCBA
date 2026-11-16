"""dccmp.py <base outdir> <outdir> [...]: per-net loss (W) and opens from dc.json, side by side, plus score.json key fields."""
import sys, json
ds = [json.load(open(d + '/dc.json')) for d in sys.argv[1:]]
for d in sys.argv[1:]:
    s = json.load(open(d + '/score.json')); print(d.split('/')[-2] + '/' + d.split('/')[-1], {k: s.get(k) for k in ('loss_W', 'power_open', 'drc_errors', 'blocked_edges', 'hot_loops')})
for n in sorted(ds[0]):
    v = [x.get(n, {}).get('loss_W', 0) for x in ds]
    o = [x.get(n, {}).get('open', []) for x in ds]
    if max(v) > 0.002 or any(o): print(f"{n[-24:]:>24}", ' '.join(f"{a:7.4f}" for a in v), o if any(o) else '')
