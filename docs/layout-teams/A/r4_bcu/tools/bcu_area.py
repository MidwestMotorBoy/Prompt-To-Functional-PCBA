#!/usr/bin/env python3
"""bcu_area.py <spec.json | outdir> [constraints.json] [--nets]
Switch-node copper and bottom-layer power copper of a planned board (r4_bcu metrics, lower is better).

Reads the planner spec (zones / tracks / vias; the scorecard writes it as <outdir>/spec.json, after split_spec and
bus4). Prints:
  SWNODE <layer> <mm2>   switch-node copper (nets of kind 'switching' in constraints.json): union of zone outlines
                         + track area, per layer, and the via count of those nets
  BCU_NONGND <mm2>       all hard (non-soft) B.Cu zone area of nets other than the return net (GND) + B.Cu power tracks
  with --nets: one line per net and layer off F.Cu (inner planes / buses excluded unless --inner): area, zone kinds,
  track length, so the inventory table can be written from it.
A JSON summary goes to stdout's last line (prefix BCU_JSON)."""
import sys, os, json
from shapely.geometry import Polygon, LineString
from shapely.ops import unary_union

C_DEF = '/home/claude/repo/tools/floorplan/example/monolith/constraints.json'


def poly(p):
    return Polygon(p['ring'], p.get('holes', [])).buffer(0)


def main():
    a = [x for x in sys.argv[1:] if not x.startswith('--')]; flags = {x for x in sys.argv[1:] if x.startswith('--')}
    sp = a[0]
    if os.path.isdir(sp): sp = os.path.join(sp, 'spec.json')
    C = json.load(open(a[1] if len(a) > 1 else C_DEF))
    sw = {('/' + n if not n.startswith('/') else n) for n, v in C['nets'].items() if v.get('kind') == 'switching'}
    sw |= {n for n, v in C['nets'].items() if v.get('kind') == 'switching'}
    ret = {hl['ret'] for hl in C.get('hot_loops', {}).values()} | {'GND'}
    S = json.load(open(sp))
    geo = {}; kinds = {}; trk = {}; tlen = {}
    for z in S['zones']:
        k = (z['net'], z['layer'])
        g = unary_union([poly(p) for p in z['polys']] or [Polygon()])
        geo.setdefault(k, []).append((g, z.get('soft', False)))
        kinds.setdefault(k, set()).update(z.get('kinds', []))
    for t in S['tracks']:
        k = (t['net'], t['layer'])
        trk.setdefault(k, []).append(LineString([t['a'], t['b']]).buffer(t['w'] / 2, 4))
        tlen[k] = tlen.get(k, 0) + LineString([t['a'], t['b']]).length
    keys = sorted(set(geo) | set(trk), key=lambda k: (k[1], k[0]))
    area = {}
    for k in keys:
        hard = [g for g, s in geo.get(k, []) if not s]
        area[k] = unary_union(hard + trk.get(k, []) or [Polygon()]).area
    out = dict(swnode={}, swnode_vias=0, bcu_nongnd=0.0, bcu_by_net={})
    for k in keys:
        n, L = k
        if n in sw: out['swnode'][L] = round(out['swnode'].get(L, 0) + area[k], 1)
        if L == 'B.Cu' and n not in ret and area[k] > 0:
            out['bcu_nongnd'] += area[k]; out['bcu_by_net'][n] = round(area[k], 1)
    out['bcu_nongnd'] = round(out['bcu_nongnd'], 1)
    out['swnode_vias'] = sum(1 for v in S['vias'] if v['net'] in sw)
    out['swnode_bcu'] = out['swnode'].get('B.Cu', 0.0)
    for L, v in sorted(out['swnode'].items()): print(f'SWNODE {L} {v} mm2')
    print(f"SWNODE vias {out['swnode_vias']}")
    print(f"BCU_NONGND {out['bcu_nongnd']} mm2")
    if '--nets' in flags:
        for k in keys:
            n, L = k
            if L == 'F.Cu' and n not in sw: continue
            if L.startswith('In') and '--inner' not in flags: continue
            print(f"  {L:6s} {n:28s} {area[k]:8.1f} mm2  kinds={sorted(kinds.get(k, []))} tracks={tlen.get(k, 0):.1f} mm")
    print('BCU_JSON', json.dumps(out))


if __name__ == '__main__':
    main()
