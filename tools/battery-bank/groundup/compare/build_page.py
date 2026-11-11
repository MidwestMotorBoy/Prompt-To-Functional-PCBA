"""Assemble the comparison page: reads every result file of both boards, writes one self-contained HTML."""
import json, base64, os, math, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
def J(p): return json.load(open(os.path.join(HERE, p)))
def img(p): return 'data:image/png;base64,' + base64.b64encode(open(os.path.join(HERE, p), 'rb').read()).decode()
D = {'img': {}}
B, N = 'base', os.environ.get('NTAG', 'fix')
KT = {B: 'base', N: 'new'}          # picture keys the template uses

# ---- hot loops ----
hot = {t: J(f'hot_{t}.json') for t in (B, N)}
SHORT = {'P1 VBUS leg (Q401)': 'P1 VBUS leg', 'P1 PACK leg (Q402)': 'P1 pack leg', 'P2 VBUS leg (Q501)': 'P2 VBUS leg', 'P2 PACK leg (Q502)': 'P2 pack leg',
         'P1 5V buck (U404)': 'P1 5 V buck', 'P2 5V buck (U504)': 'P2 5 V buck', '3V3 buck (U204)': '3V3 buck'}
LONG = {'P1 VBUS leg (Q401)': 'Port 1 VBUS leg', 'P1 PACK leg (Q402)': 'Port 1 pack leg', 'P2 VBUS leg (Q501)': 'Port 2 VBUS leg', 'P2 PACK leg (Q502)': 'Port 2 pack leg',
        'P1 5V buck (U404)': 'Port 1 5 V buck', 'P2 5V buck (U504)': 'Port 2 5 V buck', '3V3 buck (U204)': '3V3 buck'}
def hrow(o, charger):
    best = min(o['caps'], key=o['caps'].get)
    return dict(eff=o['eff_all'] * 1e9, best=f"{best} {o['caps'][best]*1e9:.2f} nH, {o['share'][best]*100:.0f} %", area=float(np.linalg.norm(o['area']['all'])),
                ring=1 / (2 * math.pi * math.sqrt((o['eff_all'] + 0.3e-9) * 170e-12)) / 1e6 if charger else float('nan'), ncap=len(o['caplist']))
D['hot'] = []
for i, k in enumerate(hot[B]):
    dev = k.split('(')[1][:-1]; ch = dev.startswith('Q')
    D['hot'].append(dict(name=LONG[k], short=SHORT[k], sub=f"{dev}, {len(hot[B][k]['caplist'])} capacitor{'s' if len(hot[B][k]['caplist'])>1 else ''}" if len(hot[B][k]['caplist']) == len(hot[N][k]['caplist'])
                         else f"{dev}, {len(hot[B][k]['caplist'])} / {len(hot[N][k]['caplist'])} capacitors in reach", b=hrow(hot[B][k], ch), n=hrow(hot[N][k], ch)))
    for t in (B, N): D['img'][f'hot_{i}_{KT[t]}'] = img(f'img/hot_{i}_{t}.png')

# ---- switch-node copper + coupling ----
cs = {t: J(f'coup_sum_{t}.json') for t in (B, N)}
D['sw'] = [dict(name=g.replace('P1', 'Port 1').replace('P2', 'Port 2'), sub=f"{cs[B]['groups'][g]['vsw']:.1f} V swing",
                b=dict(cself=cs[B]['groups'][g]['C_self_pF'], planes=cs[B]['groups'][g]['to_planes_pF'], sig=cs[B]['groups'][g]['to_signals_fF']),
                n=dict(cself=cs[N]['groups'][g]['C_self_pF'], planes=cs[N]['groups'][g]['to_planes_pF'], sig=cs[N]['groups'][g]['to_signals_fF'])) for g in cs[B]['groups']]
nets = sorted(set(cs[B]['victims']) | set(cs[N]['victims']), key=lambda n: -max(cs[B]['victims'].get(n, {}).get('worst_mV', 0), cs[N]['victims'].get(n, {}).get('worst_mV', 0)))
def cv(v):
    if not v: return None
    return dict(c=v['c_total_fF'], mv=v['worst_mV'], w=v['worst'].split(' (')[0])
D['coup_all'] = []
for n in nets:
    a, b = cs[B]['victims'].get(n), cs[N]['victims'].get(n); m = a or b
    D['coup_all'].append(dict(label=m['label'], cat=m['cat'], cn=m['c_node_pF'], b=cv(a), n=cv(b)))
D['coup'] = [r for r in D['coup_all'] if max((r['b'] or {}).get('mv', 0), (r['n'] or {}).get('mv', 0)) >= 0.01][:26]
D['img']['cmap_base'] = img('img/cmap_base.png'); D['img']['cmap_new'] = img(f'img/cmap_{N}.png')

# ---- gate loops ----
gate = {t: J(f'gate3_{t}.json') for t in (B, N)}; gr = {t: J(f'groute_{t}.json') for t in (B, N)}
def rt(r): return ', '.join(f"{k} {v:.1f} mm" for k, v in r['layers'].items()) + f", {r['wmin']:.2f} mm min width"
D['gate'] = []
for i, k in enumerate(gate[B]):
    hs = 'HS' in k; leg = 'A' if 'leg A' in k else 'B'; p = k[1]; q = k.split('(')[1][:-1]
    D['gate'].append(dict(name=f"Port {p} {'high' if hs else 'low'} side, leg {leg}", short=f"P{p} {'HS' if hs else 'LS'} {leg}", sub=f"{q}, track {gr[B][k]['total']:.0f} / {gr[N][k]['total']:.0f} mm",
                          b=dict(L=gate[B][k]['L'] * 1e9, area=float(np.linalg.norm(gate[B][k]['area'])), route=rt(gr[B][k])),
                          n=dict(L=gate[N][k]['L'] * 1e9, area=float(np.linalg.norm(gate[N][k]['area'])), route=rt(gr[N][k]), h=gate[N][k].get('h', 0.15))))
    for t in (B, N): D['img'][f'gate_{i}_{KT[t]}'] = img(f'img/gate_{i}_{t}.png')

# ---- losses ----
ll = J(f'thermal/lossload_{N}.json'); D['loss'] = []
for i in range(0, len(ll), 2):
    a, b = ll[i], ll[i + 1]; assert a['board'] == 'base' and b['board'] == N
    D['loss'].append(dict(load=a['load'], port=a['port'], soc=a['soc'], ib=a['i_bat'], iu=a['i_usb'],
                          b=dict(cu=a['cu_total'], cub=a['cu_batt'], cuu=a['cu_usb'], tot=a['total']), n=dict(cu=b['cu_total'], cub=b['cu_batt'], cuu=b['cu_usb'], tot=b['total'])))
cu = {t: J(f'k/cu_{t}.json') for t in (B, N)}
def lay(d): return ', '.join(f"{k.replace('.Cu','')} {v/d['R']*100:.0f} %" for k, v in d['layers'].items() if v / d['R'] > 0.03) + (f", vias {max(0,(1-sum(d['layers'].values())/d['R']))*100:.0f} %" if 1 - sum(d['layers'].values()) / d['R'] > 0.03 else '')
PN = [('PACK_P Q102 to RBAT', 'PACK_P', 'protection FET to sense resistor'), ('BAT_SNS_P RBAT to leg B', 'BAT_SNS_P', 'sense resistor to pack-leg FET'),
      ('GND shunt to stage', 'GND', 'shunt to VBUS-leg FET source'), ('VBUS connector to TPS25751', 'VBUS', 'connector to TPS25751'),
      ('PPHV TPS25751 to RAC', 'PPHV', 'TPS25751 to sense resistor'), ('AC_SNS_N RAC to leg A', 'AC_SNS_N', 'sense resistor to VBUS-leg FET')]
D['paths'] = []
for p in (1, 2):
    for key, nm, sub in PN:
        k = f'P{p} {key}'; D['paths'].append(dict(port=p, name=nm, sub=sub, b=cu[B]['paths'][k]['R'] * 1e3, n=cu[N]['paths'][k]['R'] * 1e3, bl=lay(cu[B]['paths'][k]), nl=lay(cu[N]['paths'][k])))
for k, nm, sub in (('CELL_P fuse to Q101', 'CELL_P', 'fuse to protection FET'), ('CELL_P_RAW J112 to fuse', 'CELL_P_RAW', 'pack + wire pad to fuse'), ('CELL_N J108 to shunt', 'CELL_N', 'pack − wire pad to shunt')):
    D['paths'].append(dict(port=0, name=nm, sub=sub, b=cu[B]['paths'][k]['R'] * 1e3, n=cu[N]['paths'][k]['R'] * 1e3, bl=lay(cu[B]['paths'][k]), nl=lay(cu[N]['paths'][k])))
D['img']['lossmap'] = img(f'img/lossmap_{N}.png')

# ---- thermals ----
th = J('thermal/summary_pc.json')
if N == 'fix2':                      # no new thermal runs for the second fix pass (signal re-routes, copper loss within 4 mW): reuse the runs of the first
    for k in list(th):
        if k.startswith('fix/') or k.startswith('fix_k38/'): th[k.replace('fix', 'fix2', 1)] = th[k]
CASES = [('dis100', '100 W, port 1', 60, 65, 120, [0, 10, 20, 30, 40, 50, 60]), ('dis100u2', '100 W, port 2', 60, 65, 120, [0, 10, 20, 30, 40, 50, 60]),
         ('dis100x2', '65 W + 35 W, both ports', 60, 65, 120, [0, 10, 20, 30, 40, 50, 60]), ('dis60', '60 W, port 1', 100, 65, 120, [0, 20, 40, 60, 80, 100]),
         ('chg1', 'Charging, port 1', 100, 65, 120, [0, 20, 40, 60, 80, 100])]
def ser(r): return {k: r[k] for k in ('s_t', 's_p', 's_part', 's_can')}
D['thermal'] = dict(cases=[dict(key=k, label=l, xmax=xm, tmax=tm, pmax=pm, xt=xt, base=ser(th[f'base/{k}']), new=ser(th[f'{N}/{k}'])) for k, l, xm, tm, pm, xt in CASES])
rows = []
for k, l, *_ in CASES:
    for b, bl in (('base', 'Current'), (N, 'Ground-up'), (N + '_k38', 'Ground-up, no credit for extra copper')):
        r = th.get(f'{b}/{k}')
        if not r: continue
        chg = k == 'chg1'
        rows.append([l, bl, 'n/a' if chg else f"{r['burst_min']:.1f}", 'n/a' if chg else f"{r['Wh40']:.1f}", f"{r['part_max']:.1f}",
                     f"{max(r['part_peak'].get('fetA1', 0), r['part_peak'].get('fetA2', 0)):.1f}", f"{max(r['part_peak'].get('ind1', 0), r['part_peak'].get('ind2', 0)):.1f}", f"{max(r['part_peak'].get('rac1', 0), r['part_peak'].get('rac2', 0)):.1f}",
                     f"{r['can_max']:.1f}", f"{r['skin_max']:.1f}", f"{r['q_board_4min']:.2f}", f"{r['t_end']:.0f}"])
D['thermal']['head'] = ['Case', 'Board', 'Minutes at full power', 'Wh out in 40 min', 'Hottest part °C', 'Hottest FET °C', 'Inductor °C', 'Board at input sense resistor °C', 'Hottest can °C', 'Cup skin °C', 'Board heat, first 4 min W', 'Run ends, min']
D['thermal']['rows'] = rows
st = {t: J(f'custats_{t}.json') for t in (B, N)}
stT = J('custats_fix.json') if N == 'fix2' else st[N]      # the board the thermal runs were made on
D['thermal']['note'] = (f"Model inputs that differ between the boards: part positions, copper loss tiles, vias in the two gap-filler zones "
    f"({st[B]['fill1']['vias']} and {st[B]['fill2']['vias']} on the current board, {stT['fill1']['vias']} and {stT['fill2']['vias']} on the ground-up board as it was run, "
    f"so through-board conductivity there is set to 8.0 and {0.45 + 7.55 * (stT['fill1']['vias'] + stT['fill2']['vias']) / (st[B]['fill1']['vias'] + st[B]['fill2']['vias']):.1f} W/mK), and copper cover round the power stages "
    f"({st[B]['stage1']['k_in']:.0f} against {stT['stage1']['k_in']:.0f} W/mK in-plane by copper area, so the model uses 38 and {38 * {'new': 1.20, 'fix': 1.27, 'fix2': 1.27}[N]:.1f} W/mK). "
    f"The third row takes that copper-cover credit away again. 25 °C ambient, still air, d44 derate policy, steps of 10 s.")

# ---- kelvin ----
kv = {t: J(f'k/r05_{t}/kelvin_{t}.json') for t in (B, N)}
KN = [('P1 RBAT (BQ25756 SRP/SRN)', 'Port 1 battery current', 'R427 5 mΩ to BQ25756 SRP/SRN'), ('P1 RAC (BQ25756 ACP/ACN)', 'Port 1 input current', 'R424 5 mΩ to BQ25756 ACP/ACN'),
      ('P2 RBAT (BQ25756 SRP/SRN)', 'Port 2 battery current', 'R527 5 mΩ to BQ25756 SRP/SRN'), ('P2 RAC (BQ25756 ACP/ACN)', 'Port 2 input current', 'R524 5 mΩ to BQ25756 ACP/ACN'),
      ('Gauge shunt RS101, port 1 current', 'Gauge shunt, port 1 load', 'RS101 1 mΩ to BQ40Z50 SRP/SRN'), ('Gauge shunt RS101, port 2 current', 'Gauge shunt, port 2 load', 'RS101 1 mΩ to BQ40Z50 SRP/SRN')]
D['kelvin'] = [dict(name=n, sub=s, b=kv[B][k]['err_pct'], n=kv[N][k]['err_pct'], bt=f"{kv[B][k]['dplus_uV']:+.0f} / {kv[B][k]['dminus_uV']:+.0f}",
                    nt=f"{kv[N][k]['dplus_uV']:+.0f} / {kv[N][k]['dminus_uV']:+.0f}", at=f"{kv[B][k]['I']:.0f} A") for k, n, s in KN]
D['kelvin_x'] = {t: {k: v for k, v in kv[t].items() if 'offset' in k} for t in (B, N)}
sp = {t: J(f'senspair_{t}.json') for t in (B, N)}
PNAME = {'P1 battery sense (SRP/SRN)': ('Port 1 battery sense pair', 'R427 to U403 pins 14/13'), 'P1 input sense (ACP/ACN)': ('Port 1 input sense pair', 'R424 to U403 pins 30/29'),
         'P2 battery sense (SRP/SRN)': ('Port 2 battery sense pair', 'R527 to U503 pins 14/13'), 'P2 input sense (ACP/ACN)': ('Port 2 input sense pair', 'R524 to U503 pins 30/29'),
         'Gauge shunt (SRP/SRN)': ('Gauge shunt pair', 'RS101 to U101 pins 8/6')}
def pr(o): return dict(area=o['area'], lp=o['len_plus'], lm=o['len_minus'], plus=[[round(x, 2), round(y, 2)] for x, y in o['plus']], minus=[[round(x, 2), round(y, 2)] for x, y in o['minus']],
                       lay=', '.join(f"{k.replace('.C','')} {v:.0f} mm" for k, v in o['layers'].items()))
D['pairs'] = [dict(name=PNAME[a['name']][0], sub=PNAME[a['name']][1], b=pr(a), n=pr(b)) for a, b in zip(sp[B], sp[N])]

# ---- via currents ----
via = {t: J(f'k/via_{t}.json') for t in (B, N)}
VSUB = {'PACK_P': 'protection FET to sense resistor', 'BAT_SNS_P': 'sense resistor to pack-leg FET', 'GND': 'shunt to VBUS-leg FET source', 'VBUS': 'connector to TPS25751',
        'AC_SNS_N': 'sense resistor to VBUS-leg FET', 'CELL_P': 'fuse to protection FET', 'FET_MID': 'between the protection FETs', 'PPHV': 'TPS25751 to sense resistor'}
def vrow(o):
    t = o['top'][0] if o['top'] else None
    return dict(i=t['i'] if t else 0.0, at=f"x {t['x']:.1f}, y {t['y']:.1f}, {t['seg']}" if t and t['i'] > 0.05 else 'no via in the path', o1=o['over1'], o2=o['over2'], n=o['n_vias'], car=o['carrying'])
D['via'] = []
for k in via[B]:
    a, c = via[B][k], via[N][k]
    if max([v['i'] for v in a['top']] + [v['i'] for v in c['top']] + [0]) < 0.05: continue
    w = k.split(' '); port = int(w[0][1]) if w[0] in ('P1', 'P2') else 0; net = w[1] if port else w[0]
    D['via'].append(dict(name=(f'Port {port} ' if port else '') + net, sub=f"{VSUB[net]}, {a['I']:.0f} A", b=vrow(a), n=vrow(c)))
def uniq(t, lim): return len({(v['x'], v['y']) for o in via[t].values() for v in o['top'] if v['i'] >= lim})
D['via_sum'] = {t: dict(max=max(v['i'] for o in via[t].values() for v in o['top']), over2=uniq(t, 2.0), over3=uniq(t, 3.0)) for t in (B, N)}
# ---- renders and work log ----
for t in (B, N):
    for s in ('top', 'bottom'): D['img'][f'render_{KT[t]}_{s}'] = 'data:image/jpeg;base64,' + base64.b64encode(open(os.path.join(HERE, f'img/render_{t}_{s}.jpg'), 'rb').read()).decode()
D['cost'] = J('worklog.json')
D['passes'] = J('passes.json'); D['tools'] = J('tools.json')
exec(open(os.path.join(HERE, 'page_fix.py')).read())            # D['fix'], M (three boards)

json.dump({k: v for k, v in D.items() if k != 'img'}, open(os.path.join(HERE, 'page_data.json'), 'w'), indent=1)
exec(open(os.path.join(HERE, 'page_text.py')).read())          # defines TEXT and SCORE from D
D['text'] = TEXT; D['score'] = SCORE
html = open(os.path.join(HERE, 'page_tpl.html')).read().replace('__DATA__', json.dumps(D, separators=(',', ':')).replace('</', '<\\/'))
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'detailed-comparison.html')
open(out, 'w').write(html); print(out, len(html) // 1024, 'KB')
