"""group_hpwl.py <group> <fragment.json> [base fragments ...]
Signal half-perimeter (pad level, nets with 2..11 pads, signal nets only as blib.is_signal_net says) of the nets that
touch a part of <group>, for the fragment placed over the hand placement (or over the given base fragments), next to
the same number for the hand placement. Used for the group gate 'signal half-perimeter of your nets at or under the hand's'."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import blib
from collections import defaultdict

def hp(B, P, g):
    nets = defaultdict(list); touch = set()
    for r in B.parts:
        v = P.get(r)
        for p in B.pads(r, v):
            if not p[1]: continue
            nets[p[1]].append((p[2], p[3]))
            if B.group_of.get(r) == g: touch.add(p[1])
    tot = 0.0; n = 0
    for net in touch:
        ps = nets[net]
        if not 2 <= len(ps) < 12 or not B.is_signal_net(net): continue
        tot += max(x for x, _ in ps) - min(x for x, _ in ps) + max(y for _, y in ps) - min(y for _, y in ps); n += 1
    return tot, n

def main(a):
    g, frag = a[0], a[1]; B = blib.Board(); H = os.path.join(blib.FRAGS, "hand")
    hand = {}
    for f in ("port1", "port2", "pack"): hand.update(blib.load_placement(os.path.join(H, f + ".json")))
    base = dict(hand)
    for f in a[2:]: base.update(blib.load_placement(f))
    mine = dict(base); mine.update(blib.load_placement(frag))
    t0, n0 = hp(B, hand, g); t1, n1 = hp(B, mine, g)
    print(f"{g} signal half-perimeter: hand {t0:.0f} mm, this {t1:.0f} mm ({n1} nets; other groups {'from ' + ', '.join(a[2:]) if a[2:] else 'at the hand placement'})")

if __name__ == "__main__": main(sys.argv[1:])
