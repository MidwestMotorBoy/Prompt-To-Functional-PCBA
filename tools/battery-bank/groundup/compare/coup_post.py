"""coup_<tag>.json -> coup_sum_<tag>.json: per victim net, coupling capacitance to each switching group and the step
that a full switch-node edge puts on the node (capacitive divider with the node's own capacitance)."""
import json, os, sys
from victims import *
TAG = os.environ['TAG']
C = json.load(open(f'coup_{TAG}.json')); caps, pins, ln = node_caps()
out = {'groups': {}, 'victims': {}}
for g, d in C.items():
    out['groups'][g] = dict(C_self_pF=d['C_self_pF'], vsw=d['vsw'], to_gnd_pF=d['C'].get('GND', 0) * 1e12,
                            to_planes_pF=sum(v for k, v in d['C'].items() if k in ('GND', 'PACK_P', '3V3')) * 1e12,
                            to_signals_fF=sum(v for k, v in d['C'].items() if category(k)) * 1e15)
    for net, c in d['C'].items():
        cat = category(net)
        if not cat: continue
        cn = caps[net] + 4e-12 * pins[net] + 0.1e-12 * ln[net] + 2e-12
        v = out['victims'].setdefault(net, dict(label=label(net), cat=cat, c_node_pF=cn * 1e12, c_cap_pF=caps[net] * 1e12, len_mm=ln[net], by={}, step_mV={}))
        v['by'][g] = c * 1e15; v['step_mV'][g] = d['vsw'] * c / (c + cn) * 1e3
for net, v in out['victims'].items():
    v['c_total_fF'] = sum(v['by'].values()); w = max(v['step_mV'], key=v['step_mV'].get); v['worst'] = w; v['worst_mV'] = v['step_mV'][w]
json.dump(out, open(f'coup_sum_{TAG}.json', 'w'), indent=1)
for g, d in out['groups'].items(): print(f"{g:22s} C_self {d['C_self_pF']:6.1f} pF  to planes {d['to_planes_pF']:6.1f} pF  to listed signals {d['to_signals_fF']:7.0f} fF")
for net, v in sorted(out['victims'].items(), key=lambda kv: -kv[1]['worst_mV'])[:40]:
    print(f"  {v['label']:18s} {v['cat']:18s} Cc {v['c_total_fF']:7.1f} fF  node {v['c_node_pF']:9.0f} pF  worst {v['worst_mV']:8.3f} mV from {v['worst']}")
