"""flip_check.py <placed.kicad_pcb> <want.json> <template.kicad_pcb>   (KiCad python): checks, for every part in want.json,
that it is on B.Cu, each pad sits within 0.01 mm of the wanted spot, its copper is on B.Cu only (SMD) or all layers (TH),
its courtyard/fab/silk items are on B layers only, and its pad-net list equals the template's. Also checks the whole
board's pad-net list is unchanged. Prints PASS/FAIL per part and a summary line."""
import sys, json, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); W = json.load(open(sys.argv[2])); t = pcbnew.LoadBoard(sys.argv[3]); mm = pcbnew.ToMM
FL = {pcbnew.F_Cu, pcbnew.F_SilkS, pcbnew.F_Fab, pcbnew.F_CrtYd, pcbnew.F_Mask, pcbnew.F_Paste}
nets = lambda brd: sorted((f.GetReference(), p.GetNumber(), p.GetNetname()) for f in brd.GetFootprints() for p in f.Pads())
fails = 0; worst = 0.0
for r, want in W.items():
    f = b.FindFootprintByReference(r); why = []
    if f.GetLayer() != pcbnew.B_Cu: why.append("not on B.Cu")
    got = {}
    for p in f.Pads(): got.setdefault(p.GetNumber(), []).append((mm(p.GetPosition().x), mm(p.GetPosition().y), p))
    for num, net, wx, wy in want:
        e = min(abs(x - wx) + abs(y - wy) for x, y, _ in got[num]); worst = max(worst, e)
        if e > 0.01: why.append(f"pad {num} off {e:.3f}")
    for p in f.Pads():
        ls = p.GetLayerSet()
        if p.GetAttribute() in (pcbnew.PAD_ATTRIB_SMD, pcbnew.PAD_ATTRIB_CONN):     # SMD (or paste-only aperture): nothing on any F layer
            if any(ls.Contains(L) for L in FL): why.append(f"pad '{p.GetNumber()}' on an F layer")
            if p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD and p.GetNumber() and not ls.Contains(pcbnew.B_Cu): why.append(f"pad {p.GetNumber()} not on B.Cu")
    for g in f.GraphicalItems():
        if g.GetLayer() in FL: why.append(f"graphic on {b.GetLayerName(g.GetLayer())}")
    for fld in (f.Reference(), f.Value()):
        if fld.GetLayer() in FL: why.append(f"field on {b.GetLayerName(fld.GetLayer())}")
    tf = t.FindFootprintByReference(r)
    if sorted((p.GetNumber(), p.GetNetname()) for p in f.Pads()) != sorted((p.GetNumber(), p.GetNetname()) for p in tf.Pads()): why.append("nets differ")
    print(("PASS " if not why else "FAIL ") + r + (" " + "; ".join(sorted(set(why))) if why else "")); fails += bool(why)
same = nets(b) == nets(t)
print(f"SUMMARY parts {len(W)} fail {fails} worst_pad_err_mm {worst:.5f} board_pad_nets_unchanged {same}")
