"""updprio.py log prio.txt: nets that failed in this pass move to the front of the priority list."""
import sys, re
log, pf = sys.argv[1:3]
fails = []
for l in open(log):
    if l.startswith("FAILKEY "):
        k = l[8:].rstrip("\n")
        if k not in fails: fails.append(k)
try: old = [l.rstrip("\n") for l in open(pf)]
except FileNotFoundError: old = []
open(pf, "w").write("".join(k + "\n" for k in fails + [o for o in old if o not in fails]))
t = open(log).read()
m = re.search(r"unconnected after fill: (\d+)", t); m2 = re.search(r"routed (\d+) edges, (\d+) failed", t)
print(log, "unconnected", m and m.group(1), "routed/failed", m2 and m2.groups(), "prio list", len(fails), "+", len(old))
