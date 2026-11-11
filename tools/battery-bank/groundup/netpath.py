"""netpath.py cu.json netregex: tracks of the matching nets chained into paths per layer, plus vias and pads."""
import json, sys, re
d = json.load(open(sys.argv[1])); rx = re.compile(sys.argv[2])
nets = sorted({t['net'] for t in d['tracks'] if rx.search(t['net'])} | {p['net'] for p in d['pads'] if rx.search(p['net'])})
for n in nets:
    print('==', n)
    print('  pads', ' '.join(f"{p['ref']}.{p['n']}({p['x']:.2f},{p['y']:.2f})" for p in d['pads'] if p['net'] == n))
    print('  vias', ' '.join(f"({v['x']:.3f},{v['y']:.3f})" for v in d['vias'] if v['net'] == n))
    for L in ('F', 'In1', 'In2', 'In3', 'In4', 'B'):
        seg = [t for t in d['tracks'] if t['net'] == n and t['l'] == L]
        while seg:
            t = seg.pop(0); ch = [(t['x1'], t['y1']), (t['x2'], t['y2'])]; w = t['w']; grew = True
            while grew:
                grew = False
                for s in seg:
                    a, b = (s['x1'], s['y1']), (s['x2'], s['y2'])
                    for p, q in ((a, b), (b, a)):
                        if abs(p[0] - ch[-1][0]) < 1e-3 and abs(p[1] - ch[-1][1]) < 1e-3: ch.append(q); seg.remove(s); grew = True; break
                        if abs(p[0] - ch[0][0]) < 1e-3 and abs(p[1] - ch[0][1]) < 1e-3: ch.insert(0, q); seg.remove(s); grew = True; break
                    if grew: break
            ln = sum(((ch[i][0]-ch[i+1][0])**2 + (ch[i][1]-ch[i+1][1])**2) ** 0.5 for i in range(len(ch) - 1))
            print(f"  {L} w{w} {ln:.1f}mm", ' '.join(f"({x:.2f},{y:.2f})" for x, y in ch))
