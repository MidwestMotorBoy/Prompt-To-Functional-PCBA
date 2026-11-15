import json, os, sys
os.chdir(sys.argv[1] if len(sys.argv) > 1 else ".")
for f, dr in (('dc.json', 'drc.json'), ('dc_routed.json', 'drc_routed.json')):
    if not os.path.exists(f): continue
    n = json.load(open(f)); d = json.load(open(dr)) if os.path.exists(dr) else {'violations': []}
    print(f, 'loss_W', round(sum(v.get('loss_W', 0) for v in n.values() if isinstance(v, dict)), 3), 'PACK_P', round(n['PACK_P']['loss_W'], 3), 'GND', round(n['GND']['loss_W'], 3),
          'open', {k: v.get('open') for k, v in n.items() if isinstance(v, dict) and v.get('open')}, 'DRC', sum(1 for v in d['violations'] if v['severity'] == 'error'), 'unconn', len(d.get('unconnected_items', [])))
