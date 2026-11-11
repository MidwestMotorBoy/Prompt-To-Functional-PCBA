# Fix-pass section: one metric table over four boards (current, ground-up first version, after fix pass 1, after fix pass 2).
# exec'd by build_page.py after D is filled; needs J, D, B, N, th, img.
O = 'new'                                  # tag of the first version of the ground-up board
P = 'fix'                                  # tag of the board after the first fix pass (N is the board after the second)
ANA_ = ('Current sense', 'Charger analog', 'Regulator feedback', 'Gauge analog'); BUS_ = ('I2C / SMBus', 'USB CC', 'Control / debug')
def metrics(t):
    h = J(f'hot_{t}.json'); g = J(f'gate3_{t}.json'); c = J(f'coup_sum_{t}.json'); cu_ = J(f'k/cu_{t}.json')['paths']; v = J(f'k/via_{t}.json')
    s = J(f'custats_{t}.json'); kv_ = J(f'k/r05_{t}/kelvin_{t}.json'); sp_ = J(f'senspair_{t}.json')
    hk = list(h); gk = list(g); m = {}
    m['hot_ch'] = [h[k]['eff_all'] * 1e9 for k in hk[:4]]; m['hot_bk'] = [h[k]['eff_all'] * 1e9 for k in hk[4:]]
    m['gate'] = [g[k]['L'] * 1e9 for k in gk]; m['gate_hs'] = [g[k]['L'] * 1e9 for k in gk if 'HS' in k]; m['g_p2a'] = g['P2 HS gate leg A (Q501)']['L'] * 1e9
    m['pk'] = [cu_[f'P{p} PACK_P Q102 to RBAT']['R'] * 1e3 for p in (1, 2)]; m['gnd'] = [cu_[f'P{p} GND shunt to stage']['R'] * 1e3 for p in (1, 2)]
    m['acn'] = [cu_[f'P{p} AC_SNS_N RAC to leg A']['R'] * 1e3 for p in (1, 2)]
    allv = [(x['i'], x['x'], x['y']) for o in v.values() for x in o['top']]
    m['via_max'] = max(a[0] for a in allv); m['via3'] = len({(a[1], a[2]) for a in allv if a[0] >= 3.0}); m['via2'] = len({(a[1], a[2]) for a in allv if a[0] >= 2.0})
    m['fill'] = [s['fill1']['vias'], s['fill2']['vias']]; m['vias'] = s['board']['vias']; m['gnd_vias'] = s['board'].get('gnd_vias', 0)
    kk = list(kv_); m['kel'] = [kv_[k]['err_pct'] for k in kk[:4]]; m['shunt'] = [kv_[k]['err_pct'] for k in kk[4:6]]
    m['pair'] = sum(o['area'] for o in sp_); m['pairs'] = [o['area'] for o in sp_]
    m['csig'] = sum(o['to_signals_fF'] for o in c['groups'].values()) / 1e3; m['cself'] = sum(o['C_self_pF'] for o in list(c['groups'].values())[:4])
    vic = [o for o in c['victims'].values() if o['cat'] in ANA_ + BUS_]
    m['n10'] = sum(1 for o in vic if o['worst_mV'] >= 10); m['n1'] = sum(1 for o in vic if o['worst_mV'] >= 1)
    def worst(cats, skip_ts=False):
        r = [o for o in vic if o['cat'] in cats and not (skip_ts and o['label'].endswith(' TS'))]
        return max(r, key=lambda o: o['worst_mV']) if r else dict(label='none', worst_mV=0.0)
    m['w_ana'] = worst(ANA_); m['w_bus'] = worst(BUS_); m['w_i2c'] = worst(('I2C / SMBus',)); m['w_nots'] = worst(ANA_ + BUS_, skip_ts=True)
    lab = {o['label']: o['worst_mV'] for o in c['victims'].values()}; m['fb2'] = lab.get('P2 FB', 0.0); m['fb1'] = lab.get('P1 FB', 0.0); m['lab'] = lab
    if t != 'base':
        ll_ = J(f'thermal/lossload_{t}.json'); rows = [r for r in ll_ if r['board'] == t]
    else:
        ll_ = J(f'thermal/lossload_{N}.json'); rows = [r for r in ll_ if r['board'] == 'base']
    def L(key, port, soc): return next(r for r in rows if f"{r['p_usb']:.0f} W" == key and r['port'] == port and abs(r['soc'] - soc) < 1e-6 and r['mode'] == 'src')['cu_total'] * 1e3
    m['cu100'] = [L('100 W', 1, 0.5), L('100 W', 2, 0.5)]; m['cu15'] = L('15 W', 1, 0.5)
    r1 = th.get(f'{t}/dis100'); r2 = th.get(f'{t}/dis100u2'); rk = th.get(f'{t}_k38/dis100')
    m['burst'] = [r1['burst_min'], r2['burst_min']]; m['fet'] = [r1['part_max'], r2['part_max']]; m['fet_k38'] = rk['part_max'] if rk else None
    return m
M = {t: metrics(t) for t in (B, O, P, N)}; D['M'] = {t: {k: v for k, v in M[t].items() if k != 'lab'} for t in M}
def _ah(b, n, tol=0.05):
    if abs(n - b) <= tol * max(abs(b), abs(n), 1e-12): return 'l'
    return 'n' if n < b else 'b'
def _r(v, d=2): return f"{min(v):.{d}f} to {max(v):.{d}f}"
def row(label, f, key, tol=0.05, higher=False):
    a, o, n = (key(M[t]) for t in (B, O, N)); ch = _ah(a, n, tol)
    if higher and ch != 'l': ch = 'n' if ch == 'b' else 'b'
    return [label, f(M[B]), f(M[O]), f(M[P]), f(M[N]), ch]
in4 = J('img/in4.json')
FIXROWS = [
    row('Charger hot loops, four', lambda m: _r(m['hot_ch']) + ' nH', lambda m: sum(m['hot_ch']), 0.08),
    row('Small buck hot loops, three', lambda m: _r(m['hot_bk']) + ' nH', lambda m: sum(m['hot_bk']), 0.08),
    row('Gate-drive loops, sum of eight', lambda m: f"{sum(m['gate']):.0f} nH ({_r(m['gate'], 1)})", lambda m: sum(m['gate']), 0.08),
    row('Port 2 leg A high-side gate loop', lambda m: f"{m['g_p2a']:.1f} nH", lambda m: m['g_p2a'], 0.08),
    row('Coupling from all switch nodes into signals', lambda m: f"{m['csig']:.2f} pF", lambda m: m['csig'], 0.15),
    row('Signals that take over 10 mV from one edge', lambda m: str(m['n10']), lambda m: m['n10'], 0.0),
    row('Charger feedback pins, step per edge, port 1 / port 2', lambda m: ' / '.join('under 0.1' if x < 0.1 else f'{x:.1f}' if x < 10 else f'{x:.0f}' for x in (m['fb1'], m['fb2'])) + ' mV', lambda m: max(m['fb1'], m['fb2'], 1.0), 0.15),
    row('Largest step on a signal other than the two TS pins', lambda m: f"{m['w_nots']['worst_mV']:.0f} mV ({m['w_nots']['label']})", lambda m: max(m['w_nots']['worst_mV'], 10.0), 0.15),
    row('Largest step on an I2C line', lambda m: f"{m['w_i2c']['worst_mV']:.0f} mV ({m['w_i2c']['label']})", lambda m: m['w_i2c']['worst_mV'], 0.15),
    row('Highest current in one via', lambda m: f"{m['via_max']:.1f} A, {m['via3']} over 3 A", lambda m: m['via_max'], 0.08),
    row('Vias under the two gap-filler pads', lambda m: f"{m['fill'][0]} and {m['fill'][1]}", lambda m: sum(m['fill']), 0.05, higher=True),
    row('PACK_P to the stage, port 1 / port 2', lambda m: f"{m['pk'][0]:.2f} / {m['pk'][1]:.2f} mΩ", lambda m: sum(m['pk']), 0.08),
    row('Ground return, port 1 / port 2', lambda m: f"{m['gnd'][0]:.2f} / {m['gnd'][1]:.2f} mΩ", lambda m: sum(m['gnd']), 0.08),
    row('Copper loss at 100 W, half charge, port 1 / port 2', lambda m: f"{m['cu100'][0]:.0f} / {m['cu100'][1]:.0f} mW", lambda m: sum(m['cu100']), 0.05),
    row('Minutes at 100 W before the derate, port 1 / port 2', lambda m: f"{m['burst'][0]:.1f} / {m['burst'][1]:.1f}", lambda m: sum(m['burst']), 0.08, higher=True),
    row('Hottest part in a 100 W run, port 1 / port 2', lambda m: f"{m['fet'][0]:.1f} / {m['fet'][1]:.1f} °C", lambda m: sum(m['fet']) - 50, 0.08),
    row('Kelvin tap error, four charger resistors', lambda m: f"within {max(abs(x) for x in m['kel']):.2f} %", lambda m: max(abs(x) for x in m['kel']), 0.25),
    row('Kelvin tap error, gauge shunt', lambda m: f"+{m['shunt'][0]:.2f} %", lambda m: m['shunt'][0], 0.1),
    row('Area enclosed by the five sense pairs', lambda m: f"{m['pair']:.0f} mm²", lambda m: m['pair'], 0.1),
]
I4 = {B: in4['Current board']['total'], O: 0.0, P: J('img/in4_fix1.json')['Ground-up board after the fix pass']['total'], N: in4['Ground-up board after the fix pass']['total']}
FIXROWS.append(['Signal track cut into the ground planes', f"{I4[B]:.0f} mm", f"{I4[O]:.0f} mm", f"{I4[P]:.0f} mm", f"{I4[N]:.0f} mm", 'b' if I4[N] > I4[B] else 'n'])
gi = next(i for i, k in enumerate(J(f'gate3_{B}.json')) if k == 'P2 HS gate leg A (Q501)')
PICS = [('Port 2 leg A high-side gate loop', f'img/gate_{gi}_{O}.png', f'img/gate_{gi}_{N}.png'), ('Port 1 pack-leg hot loop', f'img/hot_1_{O}.png', f'img/hot_1_{N}.png'),
        ('Port 2 pack-leg hot loop', f'img/hot_3_{O}.png', f'img/hot_3_{N}.png'), ('Signals near switching copper', f'img/cmap_{O}.png', f'img/cmap_{N}.png')]
for i, (_, a, b_) in enumerate(PICS): D['img'][f'fx_{i}_old'] = img(a); D['img'][f'fx_{i}_new'] = img(b_)
D['img']['in4'] = img('img/in4.png')
D['fix'] = dict(rows=FIXROWS, pics=[p[0] for p in PICS], in4=in4)
