"""ghost_parts.py <outdir> [<outdir> ...]: blocked edges (GHOSTFAIL lines of the scorecard's ghost.log) counted per part."""
import re, sys, collections
for d in sys.argv[1:]:
    c = collections.Counter(); n = 0
    for l in open(d.rstrip("/") + "/ghost.log"):
        if "GHOSTFAIL" in l:
            n += 1
            for r in set(re.findall(r" of ([A-Z]+\d+) ", l)): c[r] += 1
    print(f"{d}: {n} lines; " + ", ".join(f"{r} {k}" for r, k in c.most_common(14)))
