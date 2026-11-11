"""strip_signals.py <dump.json of the board> <in.kicad_pcb> <out.kicad_pcb>
Make the routing test board by editing the board file as text: keep power copper (nets with at least 50 mm2 of zone
fill in the dump from spike 3's dump_board.py, and GND), Kelvin sense pairs, gate drives, switch nodes and bootstrap
nets; delete every track, via and teardrop of the other nets. Writes <out>.nets.txt with the nets left to route."""
import json, re, sys, collections
KEEP = re.compile(r"(SRP|SRN|ACP|ACN)(_F)?$|SNS_[PN]$|/SW[12]$|SW_5V$|SW_3V3$|BTST[12]$|BST_5V$|(HI|LO)DRV[12]$|/[HL]G[12]$")
d = json.load(open(sys.argv[1])); zc = collections.Counter()
for k, v in d["zones"].items(): zc[k.split("|", 1)[1]] += len(v)
power = {n for n, c in zc.items() if c >= 200} | {"GND"}            # 200 cells of 0.25 mm2
keep = lambda n: n in power or bool(KEEP.search(n))
out, block, stat = [], None, collections.Counter(); glen = 0.0
for line in open(sys.argv[2], encoding="utf-8"):
    if block is None and line.rstrip("\n") in ("\t(segment", "\t(via", "\t(arc", "\t(zone"): block = [line]; continue
    if block is None: out.append(line); continue
    block.append(line)
    if line.rstrip("\n") == "\t)":
        text = "".join(block); n = re.search(r'\(net "([^"]*)"\)', text); n = n.group(1) if n else ""; kind = block[0].strip()[1:]
        if keep(n) or (kind == "zone" and "(teardrop" not in text): out.append(text); stat["kept " + kind] += 1
        else:
            stat["removed " + kind] += 1
            if kind == "segment":
                a = [float(x) for x in re.search(r"\(start ([-\d.]+) ([-\d.]+)\)", text).groups()]; b = [float(x) for x in re.search(r"\(end ([-\d.]+) ([-\d.]+)\)", text).groups()]
                glen += ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
        block = None
open(sys.argv[3], "w", encoding="utf-8").write("".join(out))
nets = {p["net"] for p in d["pads"] if p["net"]}; todo = sorted(n for n in nets if not keep(n))
open(sys.argv[3] + ".nets.txt", "w").write("\n".join(todo))
print(dict(stat), f"{glen:.0f} mm of signal track removed; {len(todo)} nets to route; {len(power)} power nets")
