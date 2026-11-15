#!/usr/bin/env python3
"""plan_copper_f.py: team A (final) planner = stagepwr planner A (gate escapes, --sealed, --taps) + ports joinfix.
Same arguments as tools/copper/plan_copper.py, plus
  --sealed=1 --taps=1 --gate_len --gate_w --gate_via --all_gates   (stagepwr/tools/plan_copper_a.py, imported unchanged)
  --joinfix=1   return_join searches its path with the signal escape room kept (tight=False) instead of tight=True
                (ports/tools/plan_copper_joinfix.py: a GND pin of a 0.4 mm QFN otherwise joins under the signal pins
                and seals SDA/SCL/IRQ of U401).
Neither original is edited: plan_copper_a is imported, and the joinfix is a wrapper round Planner.return_join that
makes Planner.path ignore tight=True while return_join runs."""
import sys, os, json
sys.path.insert(0, '/home/claude/repo/docs/layout-teams/A/stagepwr/tools')
sys.path.insert(0, '/home/claude/repo/tools/copper')
import plan_copper_a as pa

JOINFIX = 0


class PlannerF(pa.PlannerA):
    _in_rj = False

    def return_join(self, net, L, sh):
        if not JOINFIX: return super().return_join(net, L, sh)
        self._in_rj = True
        try:
            return super().return_join(net, L, sh)
        finally:
            self._in_rj = False

    def path(self, net, L, start_mask, goal_mask, w, near_mask, tight=False):
        if self._in_rj: tight = False          # joinfix: keep the signal escape room
        return super().path(net, L, start_mask, goal_mask, w, near_mask, tight=tight)


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]; opt = dict(x[2:].split("=", 1) for x in sys.argv[1:] if x.startswith("--"))
    pa.GATE_LEN = float(opt.pop("gate_len", pa.GATE_LEN)); pa.GATE_W = float(opt.pop("gate_w", pa.GATE_W)); pa.GATE_VIA = float(opt.pop("gate_via", pa.GATE_VIA))
    pa.ALL_GATES = int(opt.pop("all_gates", pa.ALL_GATES)); pa.SEALED = int(opt.pop("sealed", pa.SEALED)); pa.TAPS = int(opt.pop("taps", pa.TAPS))
    JOINFIX = int(opt.pop("joinfix", JOINFIX))
    intent = json.load(open(a[3])) if len(a) > 3 else None
    pl = PlannerF(a[0], a[1], intent, escape=float(opt.get("escape", 0.4)), grow=float(opt.get("grow", 1.5)), mirror=float(opt.get("mirror", 3)))
    spec = pl.run(); json.dump(spec, open(a[2], "w"))
    R = spec["report"]
    print(f"plan_copper_f: sealed={pa.SEALED} taps={pa.TAPS} joinfix={JOINFIX}")
    for n, r in R.get("nets", {}).items():
        print(f"{n}: {r['current_a']} A, {r['terminals']} terminals, span {r['span_mm']} mm, layer {r.get('main_layer')}{' + ' + r['inner_layer'] if 'inner_layer' in r else ''}, vias {r['vias']}, left to router {r['left_to_router']}")
    print("hot loops", json.dumps(R.get("hot_loops")))
    print("return pads", json.dumps({k: (v if not isinstance(v, list) else v[:12]) for k, v in R["return_pads"].items()}))
    print("gate escapes", json.dumps(R.get("gate_escapes")))
    print("taps", json.dumps(R.get("taps")))
    print(f"{len(spec['zones'])} zones, {len(spec['vias'])} vias, {len(spec['tracks'])} tracks, {R['seconds']} s; notes: {R['notes']}")
