"""Time and token totals of the work, from the session logs -> worklog.json (run just before build_page.py)."""
import json, collections, datetime as dt, glob
ps = glob.glob('/root/.claude/projects/*/bde4de1d-544d-5900-88b7-ba4597a5429a.jsonl')
msgs = {}; stamps = set(); snaps = []
for p in ps:
    for line in open(p):
        try: d = json.loads(line)
        except Exception: continue
        t = d.get('timestamp')
        if t: stamps.add(t)
        if d.get('type') == 'cost-state': snaps.append(d)
        if d.get('type') == 'assistant':
            m = d.get('message', {}); u = m.get('usage'); mid = m.get('id')
            if u and mid and (mid not in msgs or (u.get('output_tokens') or 0) >= (msgs[mid][1].get('output_tokens') or 0)): msgs[mid] = (t, u)
P = lambda s: dt.datetime.fromisoformat(s.replace('Z', '+00:00')); st = sorted(stamps)
RATE = dict(output_tokens=40e-6, cache_read_input_tokens=0.2e-6, cache_creation_input_tokens=16e-6, input_tokens=8e-6)   # fits the tool's own cost snapshots
def phase(name, a, b, note=''):
    xs = [P(s) for s in st if a <= s < b]; act = sum((y - x).total_seconds() for x, y in zip(xs, xs[1:]) if (y - x).total_seconds() < 1200)
    c = collections.Counter()
    for t, u in msgs.values():
        if a <= t < b:
            c['turns'] += 1
            for k in RATE: c[k] += u.get(k, 0) or 0
    return dict(name=name, note=note, hours=act / 3600, start=xs[0].isoformat() if xs else None, end=xs[-1].isoformat() if xs else None, usd=sum(c[k] * RATE[k] for k in RATE), **c)
ph = [phase('Ground-up layout', '2026-11-09T22:00', '2026-11-10T13:00', 'placement, router, nine routing passes, rule check, cup fit, write-up'),
      phase('First comparison file', '2026-11-10T13:00', '2026-11-10T13:18:30', 'posting the summary; most of the cost is re-reading the conversation after a pause'),
      phase('Detailed comparison', '2026-11-10T13:18:30', '2026-11-10T14:48', 'loop, coupling, Kelvin, loss and thermal solves on both boards, this page'),
      phase('Cost, renders and via currents', '2026-11-10T14:48', '2026-11-10T15:11', 'second update of this page'),
      phase('Tools and workflow write-up', '2026-11-10T15:11', '2026-11-10T15:15', 'third update of this page'),
      phase('Fix pass 1', '2026-11-10T15:15', '2026-11-10T19:20', 'gate drives, capacitors, vias, signals off the switch nodes, two faults found and corrected, full comparison run again'),
      phase('Fix pass 2', '2026-11-10T19:20', '2027', 'feedback pins, four signals, sense pairs, ground-plane tracks tested, two side effects found and repaired, full comparison run again, this update')]
tot = phase('Total', '2026', '2027')
for k in ('hours', 'usd', 'turns', 'output_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens', 'input_tokens'): tot[k] = sum(p[k] for p in ph)
s = max(snaps, key=lambda d: d['totalCostUSD']) if snaps else None
out = dict(phases=ph, total=tot, rate={k: v * 1e6 for k, v in RATE.items()},
           counter=dict(usd=s['totalCostUSD'], api_h=s['totalAPIDuration'] / 3.6e6, tool_h=s['totalToolDuration'] / 3.6e6, total_h=s['totalDuration'] / 3.6e6) if s else None)
json.dump(out, open('worklog.json', 'w'), indent=1)
for p in ph + [tot]: print(f"{p['name']:32s} {p['hours']:5.2f} h  out {p['output_tokens']/1e6:.2f}M  read {p['cache_read_input_tokens']/1e6:.1f}M  write {p['cache_creation_input_tokens']/1e6:.2f}M  ${p['usd']:.1f}")
