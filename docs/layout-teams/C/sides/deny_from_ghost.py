"""deny_from_ghost.py <ghost.log> [...]: prints a comma list of the moved-to-B parts (those in a GHOSTFAIL line with a
pad on B.Cu, minus the 12 template bottom parts) for SIDE_DENY. Several logs (several seeds/settings) are merged."""
import sys, re
FIXED_B = {"C208", "C209", "C210", "C211", "C212", "C213", "C421", "C456", "C521", "C556", "TH101", "TH104"}
out = set()
for f in sys.argv[1:]:
    for l in open(f):
        if l.startswith("GHOSTFAIL"): out.update(r for r in re.findall(r"of (\S+) on B\.Cu", l) if r not in FIXED_B)
print(",".join(sorted(out)))
