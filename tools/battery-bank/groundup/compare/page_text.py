# Findings text and scoreboard for the comparison page. exec'd by build_page.py with D (all numbers) in scope.
def _l(key, port, soc):
    return next(r for r in D['loss'] if r['load'].startswith(key) and r['port'] == port and abs(r['soc'] - soc) < 1e-6)
def _p(port, name):
    return next(r for r in D['paths'] if r['port'] == port and r['name'] == name)
def _t(board, case): return th[f'{board}/{case}']
def _k(i): return D['kelvin'][i]
def sg(v, d=2): return ('+' if v > 0 else '−' if v < 0 else '') + f"{abs(v):.{d}f}"
def rng(vals, d=2): return f"{min(vals):.{d}f} to {max(vals):.{d}f}"

H = D['hot']; G = D['gate']; C = D['coup_all']; SW = D['sw']
hc_b = [r['b']['eff'] for r in H[:4]]; hc_n = [r['n']['eff'] for r in H[:4]]
hb_b = [r['b']['eff'] for r in H[4:]]; hb_n = [r['n']['eff'] for r in H[4:]]
g_b = [r['b']['L'] for r in G]; g_n = [r['n']['L'] for r in G]
gw = max(G, key=lambda r: r['n']['L'] / r['b']['L'])
sw_b = sum(r['b']['cself'] for r in SW[:4]); sw_n = sum(r['n']['cself'] for r in SW[:4])
sig_b = sum(r['b']['sig'] for r in SW); sig_n = sum(r['n']['sig'] for r in SW)
def mv(r, k): return (r[k] or {}).get('mv', 0.0)
def worst(cats, k):
    rows = [r for r in C if r['cat'] in cats]
    return max(rows, key=lambda r: mv(r, k)) if rows else None
ANA = ('Current sense', 'Charger analog', 'Regulator feedback', 'Gauge analog'); BUS = ('I2C / SMBus', 'USB CC', 'Control / debug')
wa_b, wa_n = worst(ANA, 'b'), worst(ANA, 'n'); wb_b, wb_n = worst(BUS, 'b'), worst(BUS, 'n')
def nover(k, lim, cats): return sum(1 for r in C if r['cat'] in cats and mv(r, k) >= lim)
def fmv(v): return f"{v:.0f} mV" if v >= 10 else f"{v:.1f} mV" if v >= 1 else f"{v:.2f} mV"

a100, b100 = _l('100 W', 1, 0.5), _l('100 W', 2, 0.5)
a15 = _l('15 W', 1, 0.5); a100lo = _l('100 W', 1, 0.1)
kb = [abs(r['b']) for r in D['kelvin'][:4]]; kn = [abs(r['n']) for r in D['kelvin'][:4]]
pa_b = sum(r['b']['area'] for r in D['pairs']); pa_n = sum(r['n']['area'] for r in D['pairs'])
tb, tn, tk = _t('base', 'dis100'), _t(N, 'dis100'), _t(N + '_k38', 'dis100')
tb2, tn2 = _t('base', 'dis100u2'), _t(N, 'dis100u2')

def ahead(b, n, tol=0.05, lower_better=True):
    if abs(n - b) <= tol * max(abs(b), abs(n), 1e-12): return 'l'
    return ('n' if n < b else 'b') if lower_better else ('n' if n > b else 'b')

SCORE = [
    ['Charger hot loops, inductance seen by the FETs', f"{rng(hc_b)} nH", f"{rng(hc_n)} nH", ahead(sum(hc_b), sum(hc_n), 0.08)],
    ['Small buck hot loops (two 5 V, one 3.3 V)', f"{rng(hb_b)} nH", f"{rng(hb_n)} nH", ahead(sum(hb_b), sum(hb_n), 0.08)],
    ['Gate-drive loops, eight loops', f"{rng(g_b, 1)} nH", f"{rng(g_n, 1)} nH", ahead(sum(g_b), sum(g_n), 0.08)],
    ['Copper loss at 100 W, half charge, port 1 / port 2', f"{a100['b']['cu']*1e3:.0f} / {b100['b']['cu']*1e3:.0f} mW", f"{a100['n']['cu']*1e3:.0f} / {b100['n']['cu']*1e3:.0f} mW", 'l'],
    ['Copper loss at 15 W, port 1', f"{a15['b']['cu']*1e3:.0f} mW", f"{a15['n']['cu']*1e3:.0f} mW", 'n'],
    ['Minutes at 100 W before the derate, port 1', f"{tb['burst_min']:.1f} min", f"{tn['burst_min']:.1f} min", 'l'],
    ['Hottest part in a 100 W run, port 1', f"{tb['part_max']:.1f} °C", f"{tn['part_max']:.1f} °C", 'l'],
    ['Kelvin tap error, charger sense resistors', f"up to {max(kb):.2f} %", f"up to {max(kn):.2f} %", ahead(max(kb), max(kn), 0.25)],
    ['Kelvin tap error, gauge shunt', f"{sg(_k(4)['b'])} %", f"{sg(_k(4)['n'])} %", ahead(abs(_k(4)['b']), abs(_k(4)['n']), 0.1)],
    ['Area enclosed by the five sense pairs', f"{pa_b:.0f} mm²", f"{pa_n:.0f} mm²", ahead(pa_b, pa_n, 0.1)],
    ['Switch-node copper capacitance, four charger nodes', f"{sw_b:.0f} pF", f"{sw_n:.0f} pF", ahead(sw_b, sw_n, 0.08)],
    ['Largest coupled step on an analog signal', f"{fmv(mv(wa_b,'b'))} ({wa_b['label']})", f"{fmv(mv(wa_n,'n'))} ({wa_n['label']})", ahead(mv(wa_b, 'b'), mv(wa_n, 'n'), 0.15)],
    ['Largest coupled step on a bus or control signal', f"{fmv(mv(wb_b,'b'))} ({wb_b['label']})", f"{fmv(mv(wb_n,'n'))} ({wb_n['label']})", ahead(mv(wb_b, 'b'), mv(wb_n, 'n'), 0.15)],
]
exec(open(os.path.join(HERE, 'page_words.py')).read())
