"""eapply.py <base.kicad_pcb> <routes.json> <out.kicad_pcb>      (KiCad's python: needs pcbnew)
Adds routed copper to a board, refills every zone and saves. routes.json: {"routes": [{"net": name, "items":
[["T", layer index, ax, ay, bx, by, width] | ["V", -1, x, y, size, drill]]}]} (layer index into the copper stack)."""
import sys, os, json, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); J = json.load(open(sys.argv[2])); FM = pcbnew.FromMM
cu = list(b.GetEnabledLayers().CuStack())
nt = nv = 0
seen = set()
for r in J["routes"]:
    code = b.GetNetcodeFromNetname(r["net"])
    if code < 0: raise SystemExit("no net " + r["net"])
    for it in r["items"]:
        if it[0] == "T":
            if abs(it[2] - it[4]) < 1e-6 and abs(it[3] - it[5]) < 1e-6: continue
            t = pcbnew.PCB_TRACK(b); t.SetStart(pcbnew.VECTOR2I(FM(it[2]), FM(it[3]))); t.SetEnd(pcbnew.VECTOR2I(FM(it[4]), FM(it[5])))
            t.SetWidth(FM(it[6])); t.SetLayer(cu[it[1]]); t.SetNetCode(code); b.Add(t); nt += 1
        else:
            k = (round(it[2], 3), round(it[3], 3))
            if k in seen: continue
            seen.add(k)
            v = pcbnew.PCB_VIA(b); v.SetPosition(pcbnew.VECTOR2I(FM(it[2]), FM(it[3]))); v.SetDrill(FM(it[5])); v.SetNetCode(code)
            v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            try: v.SetWidth(pcbnew.F_Cu, FM(it[4]))
            except TypeError: v.SetWidth(FM(it[4]))
            b.Add(v); nv += 1
import math
for v in J.get("voids", []):            # rule areas: no pour within r of a Kelvin tap via, on every copper layer
    z = pcbnew.ZONE(b); z.SetIsRuleArea(True)
    for f in ("SetDoNotAllowZoneFills", "SetDoNotAllowCopperPour"):
        if hasattr(z, f): getattr(z, f)(True); break
    z.SetDoNotAllowTracks(False); z.SetDoNotAllowVias(False); z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False)
    ls = pcbnew.LSET()
    for l in cu: ls.AddLayer(l)
    z.SetLayerSet(ls); z.SetZoneName("tap_void")
    o = z.Outline(); o.NewOutline()
    for k in range(16): o.Append(FM(v["x"] + v["r"] * math.cos(k * math.pi / 8)), FM(v["y"] + v["r"] * math.sin(k * math.pi / 8)))
    b.Add(z)
b.BuildConnectivity()
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pro = sys.argv[3][:-10] + ".kicad_pro"; keep = open(pro, "rb").read() if os.path.exists(pro) else None
b.Save(sys.argv[3])
if keep is not None: open(pro, "wb").write(keep)
print("%s: %d tracks, %d vias, %d tap voids added, zones refilled" % (sys.argv[3], nt, nv, len(J.get("voids", []))))
