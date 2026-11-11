import sys, json, time, math, numpy as np
from peec import Model, REF, FP

ESL = {'C_0402_1005Metric': 0.30e-9, 'C_0603_1608Metric': 0.40e-9, 'C_0805_2012Metric': 0.50e-9,
       'C_1206_3216Metric': 0.60e-9, 'C_1210_3225Metric': 0.60e-9, 'CP_EIA-7343-31_Kemet-D': 1.5e-9}


def capgroups(caps, pnet, nnet):
    g = {}
    for c in caps:
        fp = REF[c]
        pp = [p['num'] for p in fp['pads'] if p['net'] == pnet]
        nn = [p['num'] for p in fp['pads'] if p['net'] == nnet]
        g[c+'+'] = [(c, pp)]; g[c+'-'] = [(c, nn)]
    return g


def hot_loop(name, box, pnet, caps, dev, dpads, spads, h=0.25, extra_nets=(), nnet='GND'):
    """dev pads dpads (on pnet) / spads (on GND) form the switch; caps between pnet and GND"""
    t0 = time.time()
    m = Model(box, [pnet, nnet]+list(extra_nets), h=h)
    groups = {'D': [(dev, dpads)], 'S': [(dev, spads)]}
    groups.update(capgroups(caps, pnet, nnet))
    m.build(groups); m.K()
    out = {'name': name, 'h': h, 'nodes': m.N, 'branches': len(m.br), 'vias': m.nvia, 'caps': {}}
    short = ('D', 'S', 1e16)
    def zo(r): return 0.35 if REF[r]['layer'] == 'B.Cu' else -0.35
    out['area'] = {}; m.curr = {}
    for c in caps:
        out['caps'][c] = m.solve((c+'+', c+'-'), [short])
        ish = (m.phi[m.gid['D']]-m.phi[m.gid['S']])*1e16
        mo, I = m.moment(m.phi, [('D', 'S', ish, zo(dev)), (c+'-', c+'+', 1.0, zo(c))])
        out['area'][c] = mo.tolist(); m.curr[c] = I
    st = [(c+'+', c+'-', 1/ESL[REF[c]['fp'].split(':')[1]]) for c in caps]
    out['eff_all'] = m.solve(('D', 'S'), st)
    # share of current per cap with all caps present
    i_c = {}
    for c in caps:
        a, b = m.gid[c+'+'], m.gid[c+'-']
        i_c[c] = (m.phi[a]-m.phi[b]) / ESL[REF[c]['fp'].split(':')[1]]
    out['share'] = i_c
    mo, I = m.moment(m.phi, [('S', 'D', 1.0, zo(dev))]+[(c+'+', c+'-', i_c[c], zo(c)) for c in caps])
    out['area']['all'] = mo.tolist(); m.curr['all'] = I
    out['t'] = time.time()-t0
    return out, m


def fmt(o):
    s = f"{o['name']}: N={o['nodes']} B={o['branches']} vias={o['vias']} ({o['t']:.0f}s)\n"
    for c, L in sorted(o['caps'].items(), key=lambda x: x[1]):
        s += f"   via {c:5s} {REF[c]['val']:10s} {REF[c]['fp'].split(':')[1][:18]:18s} board {L*1e9:6.3f} nH  +ESL {(L+ESL[REF[c]['fp'].split(':')[1]])*1e9:6.3f}  share {o['share'][c]*100:5.1f}%\n"
    s += f"   all caps in parallel (with ESL) seen from FET: {o['eff_all']*1e9:.3f} nH\n"
    for k, a in o['area'].items():
        a = np.array(a); s += f"   area {k:5s} |A|={np.linalg.norm(a):6.2f} mm2  Az(plan)={a[2]:6.2f}  Axy(vertical)={np.hypot(a[0],a[1]):6.2f}\n"
    return s


def currmap(m, I):
    """per-layer |J| map (A per cell width) from branch currents"""
    out = {}
    br = m.br; x0, _, y0, _ = m.box; h = m.h
    for li, L in enumerate(m.layers):
        jx = np.zeros((m.H, m.W)); jy = np.zeros((m.H, m.W))
        z = br[:, 5]
        for ax, J in ((0, jx), (1, jy)):
            sel = (br[:, 2] == ax) & (np.abs(z - __import__('peec').ZC[L]) < 1e-6)
            c = np.floor((br[sel, 9]-x0)/h).astype(int); r = np.floor((br[sel, 10]-y0)/h).astype(int)
            np.add.at(J, (r, c), I[sel]*0.5)
            c2 = np.floor((br[sel, 12]-x0)/h).astype(int); r2 = np.floor((br[sel, 13]-y0)/h).astype(int)
            np.add.at(J, (r2, c2), I[sel]*0.5)
        out[L] = np.hypot(jx, jy)
    return out


def gate_loop(name, box, nets, drv, U, drvpin, retpins, R, Q, qpads, h=0.3, gnd_layers=('F.Cu', 'In1.Cu')):
    t0 = time.time()
    m = Model(box, nets, h=h, top=[x for x in nets if x != 'GND'])
    if 'GND' in m.nid:
        for L in m.layers:
            if L not in gnd_layers: m.lab[L][m.lab[L] == m.nid['GND']] = 0
    groups = {'P': [(U, [drvpin])], 'N': [(U, retpins)], 'R': [(R, ['1', '2'])], 'F': [(Q, qpads)]}
    m.build(groups); m.K()
    L = m.solve(('P', 'N'), [])
    mo, I = m.moment(m.phi, [('N', 'P', 1.0, -0.3)])
    return {'name': name, 'L': L, 'area': mo.tolist(), 'nodes': m.N, 'branches': len(m.br), 't': time.time()-t0}, m, I


def autobox(refs, margin=2.0):
    xs = [p['x'] for r in refs for p in REF[r]['pads']]; ys = [p['y'] for r in refs for p in REF[r]['pads']]
    return (min(xs)-margin, max(xs)+margin, min(ys)-margin, max(ys)+margin)
