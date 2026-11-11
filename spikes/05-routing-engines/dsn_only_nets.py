"""dsn_only_nets.py <in.dsn> <nets.txt> <out.dsn> [soft,nets] [clearance_um,via_um]: leave only the listed nets for the autorouter.
KiCad's DSN export puts every net in one class and hands poured power nets to the router as open connections
(Freerouting does not treat a pad inside an outer-layer pour as connected). This empties the pin list of every net
that is not listed, and gives each existing track, via and pour of those nets a private one-item net marked protected,
so the kept copper and pads stay as obstacles and the router has nothing to connect or rip up on them.
Pours of the nets to route (teardrops) are dropped, and so are pours of the soft nets on signal layers: KiCad refills
those around new tracks, which is how the hand-routed board carries signals through them.
KiCad 10 exported 0.2 mm clearance and a 0.6 mm via although the board's rules are 0.15 mm and 0.45 mm; the last
argument writes the real values back in."""
import re, sys
t = open(sys.argv[1]).read(); todo = set(open(sys.argv[2]).read().split("\n")); n = [0, 0, 0, 0]
def fix(m):
    name = m.group(1).strip('"')
    if name in todo: n[0] += 1; return m.group(0)
    n[1] += 1; return f"(net {m.group(1)}\n    )"
head, wiring = t.split("\n  (wiring", 1)
head = re.sub(r'\(net ("[^"]*"|\S+)\s*\(pins[^)]*\)\s*\)', fix, head)
soft = set(sys.argv[4].split(",")) if len(sys.argv) > 4 else set()
power = set(re.findall(r'\(layer ("[^"]*"|\S+)\s*\(type power\)', head))
def plane(m):
    net = m.group(1).strip('"')
    if net in todo or (net in soft and m.group(2) not in power): n[3] += 1; return ""
    n[2] += 1; new.append(f"KEPT{n[2]}"); return m.group(0).replace("(plane " + m.group(1), f"(plane KEPT{n[2]}", 1)
new = []
head = re.sub(r'\(plane ("[^"]*"|\S+) \(polygon ("[^"]*"|\S+) [^()]*\)\s*\)', plane, head)
def priv(m):
    if m.group(1).strip('"') in todo: return m.group(0)
    n[2] += 1; new.append(f"KEPT{n[2]}"); return f"(net KEPT{n[2]})(type protect)"
wiring = re.sub(r'\(net ("[^"]*"|[^\s)]+)\)\(type route\)', priv, wiring)
decl = "".join(f"    (net {k}\n    )\n" for k in new)
head = head.replace("\n    (class ", "\n" + decl + "    (class ", 1)
head = head.replace("(class kicad_default ", "(class kicad_default " + " ".join(new) + " ", 1)
if len(sys.argv) > 5:
    cl, via = sys.argv[5].split(",")
    head = re.sub(r"\(clearance 200\)", f"(clearance {cl})", head)
    def ps(m): return re.sub(r'(\(circle (?:"[^"]*"|\S+) )600', r"\g<1>" + via, m.group(0))
    head = re.sub(r'\(padstack "Via\[0-5\]_600:300_um".*?\(attach off\)', ps, head, flags=re.S)
open(sys.argv[3], "w").write(head + "\n  (wiring" + wiring)
print("nets kept for routing", n[0], "nets emptied", n[1], "kept tracks, vias and pours made private", n[2], "pours dropped", n[3])
