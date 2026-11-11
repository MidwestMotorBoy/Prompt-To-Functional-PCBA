"""Write coloured polygon meshes as STEP AP214 files, in pure Python (no OpenCascade: its DLLs are blocked here).

Each colour becomes one SHELL_BASED_SURFACE_MODEL of planar ADVANCED_FACEs (edges shared within the shell), each face
with a STYLED_ITEM colour, which KiCad's 3D viewer and its STEP export read like any other model.

Frames follow KiCad footprints: origin = footprint origin, +X = footprint +x, +Y = footprint -y, +Z up from the board.
"""
import math


class Mesh:
    """Polygons grouped by colour: {(r, g, b): [[(x, y, z), ...], ...]}."""

    def __init__(self):
        self.parts = {}

    def add(self, rgb, poly):
        self.parts.setdefault(tuple(round(c, 3) for c in rgb), []).append([tuple(map(float, p)) for p in poly])

    def box(self, rgb, x0, x1, y0, y1, z0, z1):
        x0, x1 = sorted((x0, x1))
        y0, y1 = sorted((y0, y1))
        z0, z1 = sorted((z0, z1))
        c = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
            self.add(rgb, [c[i] for i in f])

    def cylinder(self, rgb, x, y, r, z0, z1, n=16):
        ring = [(x + r * math.cos(2 * math.pi * k / n), y + r * math.sin(2 * math.pi * k / n)) for k in range(n)]
        self.add(rgb, [(px, py, z0) for px, py in reversed(ring)])
        self.add(rgb, [(px, py, z1) for px, py in ring])
        for k in range(n):
            (ax, ay), (bx, by) = ring[k], ring[(k + 1) % n]
            self.add(rgb, [(ax, ay, z0), (bx, by, z0), (bx, by, z1), (ax, ay, z1)])

    def frustum(self, rgb, x, y, r0, r1, z0, z1, n=16):
        """A cylinder whose radius runs from r0 at z0 to r1 at z1 (a solder fillet, a cone with r1 = 0)."""
        a = [(math.cos(2 * math.pi * k / n), math.sin(2 * math.pi * k / n)) for k in range(n)]
        self.add(rgb, [(x + r0 * c, y + r0 * s, z0) for c, s in reversed(a)])
        if r1 > 0:
            self.add(rgb, [(x + r1 * c, y + r1 * s, z1) for c, s in a])
        for k in range(n):
            (ac, as_), (bc, bs) = a[k], a[(k + 1) % n]
            self.add(rgb, [(x + r0 * ac, y + r0 * as_, z0), (x + r0 * bc, y + r0 * bs, z0),
                           (x + r1 * bc, y + r1 * bs, z1), (x + r1 * ac, y + r1 * as_, z1)])

    def tube(self, rgb, x, y, r_out, r_in, z0, z1, n=24):
        """A ring (sleeve, washer) from quads: outer and inner walls, annular top and bottom."""
        a = [(math.cos(2 * math.pi * k / n), math.sin(2 * math.pi * k / n)) for k in range(n)]
        for k in range(n):
            (ac, as_), (bc, bs) = a[k], a[(k + 1) % n]
            oa, ob = (x + r_out * ac, y + r_out * as_), (x + r_out * bc, y + r_out * bs)
            ia, ib = (x + r_in * ac, y + r_in * as_), (x + r_in * bc, y + r_in * bs)
            self.add(rgb, [oa + (z0,), ob + (z0,), ob + (z1,), oa + (z1,)])    # outer wall, normal outward
            self.add(rgb, [ib + (z0,), ia + (z0,), ia + (z1,), ib + (z1,)])    # bore, normal toward the axis
            self.add(rgb, [oa + (z1,), ob + (z1,), ib + (z1,), ia + (z1,)])    # top
            self.add(rgb, [ia + (z0,), ib + (z0,), ob + (z0,), oa + (z0,)])    # bottom

    def merge(self, other, rot_z=0.0, dx=0.0, dy=0.0, dz=0.0):
        a = math.radians(rot_z)
        ca, sa = math.cos(a), math.sin(a)
        for rgb, polys in other.parts.items():
            for p in polys:
                self.add(rgb, [(ca * x - sa * y + dx, sa * x + ca * y + dy, z + dz) for x, y, z in p])


def read_obj(path):
    """EasyEDA OBJ (mm, Z up, materials with Kd colours) -> Mesh."""
    m, v, kd, cur = Mesh(), [], {}, None
    for ln in open(path, encoding="utf-8", errors="replace"):
        p = ln.split()
        if not p:
            continue
        if p[0] in ("newmtl", "usemtl"):
            cur = p[1]
        elif p[0] == "Kd":
            kd[cur] = tuple(float(x) for x in p[1:4])
        elif p[0] == "v":
            v.append(tuple(float(x) for x in p[1:4]))
        elif p[0] == "f":
            m.add(kd.get(cur, (0.5, 0.5, 0.5)), [v[int(x.split("/")[0]) - 1] for x in p[1:]])
    return m


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _unit(a):
    n = math.sqrt(a[0] ** 2 + a[1] ** 2 + a[2] ** 2)
    return (a[0] / n, a[1] / n, a[2] / n) if n > 1e-12 else None


def _normal(poly):
    nx = ny = nz = 0.0
    for i, a in enumerate(poly):
        b = poly[(i + 1) % len(poly)]
        nx += (a[1] - b[1]) * (a[2] + b[2])
        ny += (a[2] - b[2]) * (a[0] + b[0])
        nz += (a[0] - b[0]) * (a[1] + b[1])
    return _unit((nx, ny, nz))


def _planar(poly, n):
    d0 = sum(n[k] * poly[0][k] for k in range(3))
    return all(abs(sum(n[k] * p[k] for k in range(3)) - d0) < 1e-6 for p in poly)


def _faces(polys):
    """Clean polygons: drop repeated points, split non-planar ones into a fan, skip degenerate ones."""
    out = []
    for p in polys:
        q = [p[i] for i in range(len(p)) if p[i] != p[i - 1]]
        if len(q) < 3:
            continue
        n = _normal(q)
        if n is None:
            continue
        if len(q) > 3 and not _planar(q, n):
            for i in range(1, len(q) - 1):
                t = [q[0], q[i], q[i + 1]]
                if _normal(t) is not None:
                    out.append(t)
            continue
        out.append(q)
    return out


def write_step(path, name, mesh):
    lines, ids = [], [0]

    def e(text):
        ids[0] += 1
        lines.append("#%d=%s;" % (ids[0], text))
        return ids[0]

    def f(x):
        s = ("%.6f" % x).rstrip("0")
        return s + "0" if s.endswith(".") else s

    def pt(p):
        return e("CARTESIAN_POINT('',(%s,%s,%s))" % (f(p[0]), f(p[1]), f(p[2])))

    def dr(d):
        return e("DIRECTION('',(%s,%s,%s))" % (f(d[0]), f(d[1]), f(d[2])))

    ac = e("APPLICATION_CONTEXT('core data for automotive mechanical design processes')")
    e("APPLICATION_PROTOCOL_DEFINITION('international standard','automotive_design',2000,#%d)" % ac)
    pc = e("PRODUCT_CONTEXT('',#%d,'mechanical')" % ac)
    pr = e("PRODUCT('%s','%s','',(#%d))" % (name, name, pc))
    e("PRODUCT_RELATED_PRODUCT_CATEGORY('part',$,(#%d))" % pr)
    pdf = e("PRODUCT_DEFINITION_FORMATION('','',#%d)" % pr)
    pdc = e("PRODUCT_DEFINITION_CONTEXT('part definition',#%d,'design')" % ac)
    pd = e("PRODUCT_DEFINITION('design','',#%d,#%d)" % (pdf, pdc))
    pds = e("PRODUCT_DEFINITION_SHAPE('','',#%d)" % pd)
    lu = e("( LENGTH_UNIT() NAMED_UNIT(*) SI_UNIT(.MILLI.,.METRE.) )")
    au = e("( NAMED_UNIT(*) PLANE_ANGLE_UNIT() SI_UNIT($,.RADIAN.) )")
    su = e("( NAMED_UNIT(*) SI_UNIT($,.STERADIAN.) SOLID_ANGLE_UNIT() )")
    un = e("UNCERTAINTY_MEASURE_WITH_UNIT(LENGTH_MEASURE(1.E-07),#%d,'distance_accuracy_value','confusion accuracy')" % lu)
    ctx = e("( GEOMETRIC_REPRESENTATION_CONTEXT(3) GLOBAL_UNCERTAINTY_ASSIGNED_CONTEXT((#%d)) "
            "GLOBAL_UNIT_ASSIGNED_CONTEXT((#%d,#%d,#%d)) REPRESENTATION_CONTEXT('Context #1','3D Context with UNIT and "
            "UNCERTAINTY') )" % (un, lu, au, su))
    origin = e("AXIS2_PLACEMENT_3D('',#%d,#%d,#%d)" % (pt((0, 0, 0)), dr((0, 0, 1)), dr((1, 0, 0))))
    models, styled = [], []
    for rgb, polys in mesh.parts.items():
        faces = _faces(polys)
        if not faces:
            continue
        vid, vpt, edges, fids = {}, {}, {}, []

        def vert(p):
            k = tuple(round(c, 6) for c in p)
            if k not in vid:
                vid[k] = e("VERTEX_POINT('',#%d)" % pt(k))
                vpt[vid[k]] = k
            return vid[k]

        def edge(a, b):
            """An edge is shared by at most two faces, run in opposite directions (manifold); meshes that put three
            faces on one edge or repeat a direction get their own copy."""
            if edges.get((b, a)) and edges[(b, a)][1] == 1:
                edges[(b, a)][1] = 2
                return edges[(b, a)][0], False
            pa, pb = vpt[a], vpt[b]
            d = _sub(pb, pa)
            ln = math.sqrt(sum(c * c for c in d))
            vec = e("VECTOR('',#%d,%s)" % (dr(_unit(d)), f(ln)))
            line = e("LINE('',#%d,#%d)" % (pt(pa), vec))
            ec = e("EDGE_CURVE('',#%d,#%d,#%d,.T.)" % (a, b, line))
            if (a, b) not in edges:
                edges[(a, b)] = [ec, 1]
            return ec, True

        for poly in faces:
            vs = [vert(p) for p in poly]
            if len(set(vs)) < 3:
                continue
            oes = []
            for i in range(len(vs)):
                a, b = vs[i], vs[(i + 1) % len(vs)]
                if a == b:
                    continue
                ec, fwd = edge(a, b)
                oes.append(e("ORIENTED_EDGE('',*,*,#%d,%s)" % (ec, ".T." if fwd else ".F.")))
            loop = e("EDGE_LOOP('',(%s))" % ",".join("#%d" % o for o in oes))
            bound = e("FACE_OUTER_BOUND('',#%d,.T.)" % loop)
            n = _normal(poly)
            ref = _unit(_sub(poly[1], poly[0]))
            ref = _unit(_sub(ref, tuple(n[k] * sum(ref[j] * n[j] for j in range(3)) for k in range(3))))
            plane = e("PLANE('',#%d)" % e("AXIS2_PLACEMENT_3D('',#%d,#%d,#%d)" % (pt(poly[0]), dr(n), dr(ref))))
            fids.append(e("ADVANCED_FACE('',(#%d),#%d,.T.)" % (bound, plane)))
        shell = e("OPEN_SHELL('',(%s))" % ",".join("#%d" % i for i in fids))
        model = e("SHELL_BASED_SURFACE_MODEL('',(#%d))" % shell)
        models.append(model)
        col = e("COLOUR_RGB('',%s,%s,%s)" % tuple(f(c) for c in rgb))
        fac = e("FILL_AREA_STYLE_COLOUR('',#%d)" % col)
        fas = e("FILL_AREA_STYLE('',(#%d))" % fac)
        ssf = e("SURFACE_STYLE_FILL_AREA(#%d)" % fas)
        sss = e("SURFACE_SIDE_STYLE('',(#%d))" % ssf)
        ssu = e("SURFACE_STYLE_USAGE(.BOTH.,#%d)" % sss)
        psa = e("PRESENTATION_STYLE_ASSIGNMENT((#%d))" % ssu)
        # colour every face: KiCad drops shell-level colours once a model has several shells of triangles
        styled += [e("STYLED_ITEM('color',(#%d),#%d)" % (psa, fid)) for fid in fids]
    rep = e("MANIFOLD_SURFACE_SHAPE_REPRESENTATION('%s',(#%d,%s),#%d)"
            % (name, origin, ",".join("#%d" % m for m in models), ctx))
    e("SHAPE_DEFINITION_REPRESENTATION(#%d,#%d)" % (pds, rep))
    e("MECHANICAL_DESIGN_GEOMETRIC_PRESENTATION_REPRESENTATION('',(%s),#%d)" % (",".join("#%d" % s for s in styled), ctx))
    head = ["ISO-10303-21;", "HEADER;", "FILE_DESCRIPTION(('%s'),'2;1');" % name,
            "FILE_NAME('%s','2026-10-22T00:00:00',(''),(''),'step_mesh.py','step_mesh.py','');" % name,
            "FILE_SCHEMA(('AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }'));", "ENDSEC;", "DATA;"]
    with open(path, "w", encoding="ascii", newline="\n") as fh:
        fh.write("\n".join(head + lines + ["ENDSEC;", "END-ISO-10303-21;", ""]))
    return sum(len(_faces(p)) for p in mesh.parts.values())
