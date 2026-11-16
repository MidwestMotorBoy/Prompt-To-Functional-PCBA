"""handroute_soft.py <same arguments as handroute.py> --soft=<net>[,<net>...]
(team B, phase 2 round 4, worker B) tools/handroute.py with more pour nets that new copper may cross: the exact check
treats the FILLED copper of the named nets as it treats GND / PACK_P / 3V3 (pinlib.SOFTNETS): the refill carves round
the new track or via, so a fill is not a fault. Hot-loop pours stay closed whatever their net (--keep closes the plan
board's hot pours as before). Use it for a quiet power pour that is not a hot-loop pour, e.g. a signal via in the Port 2
PPHV F.Cu pour; KiCad's DRC after the refill (printed by handroute.py) is the arbiter of the pour clearance (0.25 mm
HighCurrent to small signals). handroute.py itself is unchanged; this only widens pinlib.SOFTNETS for one run.
It also runs handroute.py with one fix applied to its text at load time: "remove" / "lift" items are matched in KiCad by
the STANDARD layer name (BOARD.GetStandardLayerName). The Monolith board's inner layers carry user names
("In3.Cu (signal H + 5V)"), so handroute.py's GetLayerName match missed every In2 / In3 removal ("removed 19 of 32
items", nothing written); and the layer table of the writer is built from the pcbnew layer constants (in
kicad/kicad:10.0 b.GetEnabledLayers().CuStack() fails: "'SwigPyObject' object has no attribute 'CuStack'"). The writer's output is not filtered with "grep -v swig": KiCad's swig leak messages go to stdout and the "written"
marker landed inside one of them ("VECTOR2<written"), so the filter dropped it and handroute.py stopped (exit 1)
although the board had been saved. Use this tool for any hand file that removes inner-layer tracks, with or without --soft."""
import sys, os
T = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, T)
import pinlib
soft = [a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--soft=")]
extra = tuple(n for s in soft for n in s.split(",") if n)
pinlib.SOFTNETS = tuple(pinlib.SOFTNETS) + extra
print("handroute_soft: pours of %s may be crossed (refill carves round), hot-loop pours stay closed" % (list(extra),))
sys.argv = [os.path.join(T, "handroute.py")] + [a for a in sys.argv[1:] if not a.startswith("--soft=")]
src = open(os.path.join(T, "handroute.py")).read()
old = 'b.GetLayerName(t.GetLayer()), round(MM(s_.x), 4)'
if src.count(old) != 1: raise SystemExit("handroute_soft: handroute.py changed, the layer-name fix no longer applies")
src = src.replace(old, 'pcbnew.BOARD.GetStandardLayerName(t.GetLayer()), round(MM(s_.x), 4)')
old2 = 'lid = {pcbnew.BOARD.GetStandardLayerName(l): l for l in b.GetEnabledLayers().CuStack()}'
if src.count(old2) == 1:
    src = src.replace(old2, 'lid = {"F.Cu": pcbnew.F_Cu, "In1.Cu": pcbnew.In1_Cu, "In2.Cu": pcbnew.In2_Cu, "In3.Cu": pcbnew.In3_Cu, "In4.Cu": pcbnew.In4_Cu, "B.Cu": pcbnew.B_Cu}')
old3 = 'python3 hw.py 2>&1 | grep -v swig'
if src.count(old3) == 1:
    src = src.replace(old3, 'python3 hw.py 2>&1')
exec(compile(src, os.path.join(T, "handroute.py"), "exec"), {"__name__": "__main__", "__file__": os.path.join(T, "handroute.py")})
