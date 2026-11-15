"""ctrace.py: debug hook (PYTHONPATH=docs/layout-teams/C/corridor HOOKS=...,ctrace): prints the order in which parts are
first evaluated (= placement order of the constructive fill) and where the power-path parts end up."""
import os
seen = []
WATCH = set(os.environ.get("TRACE", "F102,L401,L402,L501,L502,Q101,Q102,Q401,Q402,Q501,Q502,R424,R427,R524,R527,RS101,U204,U401,U404,U501,U504").split(","))
def extra_cost(ctx, r, k, xs, ys):
    if r not in seen:
        seen.append(r)
        if r in WATCH: print(f"  trace: #{len(seen)} {r} placed so far {len([q for q in ctx.P if q in ctx.fill])}", flush=True)
    return 0.0
def post_place(ctx):
    for r in sorted(WATCH):
        if r in ctx.P: print(f"  trace final {r}: {tuple(round(v, 1) for v in ctx.P[r])}")
