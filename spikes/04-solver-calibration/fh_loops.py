"""fh_loops.py: three test loops for an outside check of the loop solver against FastHenry2.
Each loop is rectangles on F.Cu and In1.Cu, ideal shorts and one port, so both solvers see the same copper.
  python3 fh_loops.py write <dir>      # writes <dir>/<loop>_<cell>.inp for FastHenry and <dir>/<loop>.kicad_pcb
  python3 fh_loops.py peec <dir>       # runs the loop solver on the same boards at several cell sizes
  python3 fh_loops.py compare <dir>    # reads <dir>/results.txt written on the FastHenry side
Loops (mm):
  plates  two 18 x 10 plates, top over inner 1, shorted at the far end              (about 0.5 nH)
  small   a 1 x 3 strip over a 5 x 7 plane, shorted at the far end                  (pads the size of a cell)
  via     a 2 x 6 strip on top and one on inner 1, joined by two real vias          (tests the via model)
A pad is an equipotential patch; port = between pad P+ and pad P-; short = pads S+ and S- tied together."""
import os, sys, math
Z = {'F.Cu': 0.035, 'In1.Cu': 0.27875}; T = {'F.Cu': 0.07, 'In1.Cu': 0.0175}
# rect = (layer, net, x0, y0, x1, y1); pad = (name, layer, net, x0, y0, x1, y1); via = (x, y, drill, net)
LOOPS = {
 'plates': dict(rects=[('F.Cu', 'A', 0, 0, 18.6, 10), ('In1.Cu', 'B', 0, 0, 18.6, 10)],
                pads=[('P+', 'F.Cu', 'A', 0, 0, 0.3, 10), ('P-', 'In1.Cu', 'B', 0, 0, 0.3, 10),
                      ('S+', 'F.Cu', 'A', 18.3, 0, 18.6, 10), ('S-', 'In1.Cu', 'B', 18.3, 0, 18.6, 10)], vias=[],
                cells=(0.6, 0.3)),
 'small': dict(rects=[('F.Cu', 'A', 1, 3, 4.6, 4), ('In1.Cu', 'B', 0, 0, 5.6, 7)],
               pads=[('P+', 'F.Cu', 'A', 1, 3, 1.3, 4), ('P-', 'In1.Cu', 'B', 1, 3, 1.3, 4),
                     ('S+', 'F.Cu', 'A', 4.3, 3, 4.6, 4), ('S-', 'In1.Cu', 'B', 4.3, 3, 4.6, 4)], vias=[],
               cells=(0.2, 0.1)),
 'via': dict(rects=[('F.Cu', 'A', 0, 0, 6.6, 2), ('In1.Cu', 'A', 0, 0, 6.6, 2)],
             pads=[('P+', 'F.Cu', 'A', 0, 0, 0.3, 2), ('P-', 'In1.Cu', 'A', 0, 0, 0.3, 2)],
             vias=[(6.1, 0.5, 0.3, 'A'), (6.1, 1.5, 0.3, 'A')], cells=(0.2, 0.1)),
}

def inp(name, h):
    d = LOOPS[name]; o = [f"* {name}, cell {h} mm. Loop inductance = Im(Z)/(2 pi f) of the one port.", ".units mm", ".default sigma=5.8e4"]
    eq = {}; k = 0
    for i, (L, net, x0, y0, x1, y1) in enumerate(d['rects']):
        n1, n2 = round((x1 - x0) / h), round((y1 - y0) / h); z = -Z[L]
        o.append(f"G{i} x1={x0} y1={y0} z1={z} x2={x1} y2={y0} z2={z} x3={x1} y3={y1} z3={z} thick={T[L]} seg1={n1} seg2={n2}")
        for pn, pL, pnet, a0, b0, a1, b1 in d['pads']:
            if pL != L or pnet != net or not (x0 <= a0 and a1 <= x1 and y0 <= b0 and b1 <= y1): continue
            for ix in range(n1 + 1):
                for iy in range(n2 + 1):
                    x, y = x0 + ix * h, y0 + iy * h
                    if a0 - 1e-6 <= x <= a1 + 1e-6 and b0 - 1e-6 <= y <= b1 + 1e-6:
                        k += 1; o.append(f"+ n{k} ({x:.4f},{y:.4f},{z})"); eq.setdefault(pn, []).append(f"n{k}")
        for vi, (vx, vy, dr, vnet) in enumerate(d['vias']):
            if vnet == net: o.append(f"+ nv{vi}_{i} ({vx:.4f},{vy:.4f},{z})")
    for vi, (vx, vy, dr, vnet) in enumerate(d['vias']):
        s = dr * math.sqrt(math.pi) / 2                      # square bar with the same area as the drilled hole
        o.append(f"Ev{vi} nv{vi}_0 nv{vi}_1 w={s:.4f} h={s:.4f}")
    for pn, ns in eq.items():
        for j in range(0, len(ns) - 1, 8): o.append(".equiv " + " ".join(ns[j:j + 9]))
    if 'S+' in eq: o.append(f".equiv {eq['S+'][0]} {eq['S-'][0]}")
    o += [f".external {eq['P+'][0]} {eq['P-'][0]}", ".freq fmin=1e8 fmax=1e8 ndec=1", ".end"]
    return "\n".join(o) + "\n"

def pcb(name):
    d = LOOPS[name]; o = ['(kicad_pcb (version 20240108) (generator "fh_loops")']
    for i, (L, net, x0, y0, x1, y1) in enumerate(d['rects']):
        pts = " ".join(f"(xy {x} {y})" for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)))
        o.append(f'(zone (net "{net}") (layer "{L}") (name "r{i}") (polygon (pts {pts})) (filled_polygon (layer "{L}") (pts {pts})))')
    for pn, L, net, x0, y0, x1, y1 in d['pads']:
        o.append(f'(footprint "T:pad" (layer "F.Cu") (at {(x0 + x1) / 2} {(y0 + y1) / 2}) (property "Reference" "{pn}") (property "Value" "pad")'
                 f' (pad "1" smd rect (at 0 0) (size {x1 - x0} {y1 - y0}) (layers "{L}") (net "{net}")))')
    for x, y, dr, net in d['vias']:
        o.append(f'(via (at {x} {y}) (size {dr + 0.25}) (drill {dr}) (layers "F.Cu" "In1.Cu") (net "{net}"))')
    return "\n".join(o) + "\n)\n"

def peec(dirn, name, h, centre):
    import subprocess
    code = (f"import sys; sys.path[:0]=[{repr(TOOLS + 'groundup/compare')},{repr(TOOLS + 'review-tools')}]\n"
            f"from peec import Model\nd={repr(LOOPS[name])}\n"
            "xs=[r[2] for r in d['rects']]+[r[4] for r in d['rects']]; ys=[r[3] for r in d['rects']]+[r[5] for r in d['rects']]\n"
            f"m=Model((min(xs)-1,max(xs)+1,min(ys)-1,max(ys)+1),sorted(set(r[1] for r in d['rects'])),h={h},layers=['F.Cu','In1.Cu'],centre={centre})\n"
            "m.build({p[0]:[(p[0],['1'])] for p in d['pads']}); m.K()\n"
            "print(m.solve(('P+','P-'),[('S+','S-',1e16)] if 'S+' in m.gid else [])*1e9)\n")
    r = subprocess.run([sys.executable, "-c", code], env=dict(os.environ, PCB=f"{dirn}/{name}.kicad_pcb"), capture_output=True, text=True)
    return float(r.stdout.split()[-1]) if r.returncode == 0 else r.stderr[-400:]

TOOLS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../tools/battery-bank/")
if __name__ == "__main__":
    cmd, dirn = sys.argv[1], sys.argv[2]; os.makedirs(dirn, exist_ok=True)
    if cmd == "write":
        for name, d in LOOPS.items():
            open(f"{dirn}/{name}.kicad_pcb", "w").write(pcb(name))
            for h in d['cells']: open(f"{dirn}/{name}_{h}.inp", "w").write(inp(name, h))
        print("wrote", sorted(os.listdir(dirn)))
    elif cmd == "peec":
        print("| loop | cell, mm | old rasteriser, nH | new rasteriser, nH |\n|---|---|---|---|")
        for name in LOOPS:
            for h in ((0.5, 0.25) if name == 'plates' else (0.3, 0.2, 0.15, 0.1)):
                a, b = peec(dirn, name, h, False), peec(dirn, name, h, True)
                print(f"| {name} | {h} | {a if isinstance(a, str) else round(a, 4)} | {b if isinstance(b, str) else round(b, 4)} |", flush=True)
