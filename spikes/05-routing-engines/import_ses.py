"""import_ses.py <board.kicad_pcb> <in.ses> <out.kicad_pcb>: bring a Freerouting session back into the board.
Run under KiCad's python. Nets named KEPTn (made by dsn_only_nets.py for copper that was already on the board) are
dropped from the session first. KiCad's import throws away every track already on the board, so the import is done
on a scratch copy and only the new tracks and vias are copied (as text) into the real board; then zones are refilled."""
import re, sys, pcbnew
t = open(sys.argv[2]).read(); out, depth, skip, i, n = [], 0, None, 0, 0
for m in re.finditer(r'\(net (KEPT\d+)\b', t):                   # cut each "(net KEPTn ... )" block by bracket matching
    j = m.start(); d = 0; k = j
    while True:
        c = t[k]
        if c == '"': k = t.index('"', k + 1)
        elif c == "(": d += 1
        elif c == ")":
            d -= 1
            if d == 0: break
        k += 1
    out.append(t[i:j]); i = k + 1; n += 1
out.append(t[i:]); tmp = sys.argv[2] + ".filtered"; open(tmp, "w").write("".join(out))
b = pcbnew.LoadBoard(sys.argv[1]); ok = pcbnew.ImportSpecctraSES(b, tmp); pcbnew.SaveBoard(sys.argv[3] + ".scratch", b)
routed = {x.strip('"') for x in re.findall(r'\(net ("[^"]*"|[^\s()]+)', "".join(out))}
new, block = [], None
for line in open(sys.argv[3] + ".scratch", encoding="utf-8"):
    if block is None and line.rstrip("\n") in ("\t(segment", "\t(via", "\t(arc"): block = [line]; continue
    if block is not None:
        block.append(line)
        if line.rstrip("\n") == "\t)":
            m = re.search(r'\(net "([^"]*)"\)', "".join(block))
            if m and m.group(1) in routed: new.append("".join(block))
            block = None
src = open(sys.argv[1], encoding="utf-8").read().rstrip(); assert src.endswith(")")
open(sys.argv[3], "w", encoding="utf-8").write(src[:-1] + "".join(new) + ")\n")
b = pcbnew.LoadBoard(sys.argv[3]); pcbnew.ZONE_FILLER(b).Fill(b.Zones()); pcbnew.SaveBoard(sys.argv[3], b)
print("dropped", n, "kept-copper nets from the session; import ok:", ok, "; new tracks and vias:", len(new))
