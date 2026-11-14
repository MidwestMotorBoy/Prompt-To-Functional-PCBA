"""fill.py <in.kicad_pcb> <out.kicad_pcb>      (KiCad's python: needs pcbnew)
Refills every zone and saves, keeping the project file beside the output as it was (pcbnew's Save rewrites it)."""
import sys, os, shutil, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pro = sys.argv[2][:-10] + ".kicad_pro"; keep = open(pro, "rb").read() if os.path.exists(pro) else None
b.Save(sys.argv[2])
if keep is not None: open(pro, "wb").write(keep)
print("filled", len(list(b.Zones())), "zones ->", sys.argv[2])
