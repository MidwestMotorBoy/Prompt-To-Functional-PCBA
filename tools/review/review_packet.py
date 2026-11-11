"""review_packet.py <build dir> <limits dir> <limitsmap.json> <design dir> [out.md]
Stage 5, design review: writes one file that gives a reviewer what the intent gate cannot judge for itself.
The gate proves what is declared; the packet shows what is NOT covered, and how thin each margin is, so the
reviewer spends its reading on those places. Needs SYMBOL_DIRS like the build.
Sections: coverage gaps, thinnest margins, set points, waivers, then the questions a reviewer must answer."""
import sys, os, json, re, glob

def main(build, limdir, mapf, design, outf=None):
    sys.path.insert(0, design); import symlib
    d = json.load(open(f"{build}/netlist.json")); cons = json.load(open(f"{build}/constraints.json"))
    limits = {os.path.basename(f)[:-5]: json.load(open(f)) for f in glob.glob(f"{limdir}/*.json")}
    kbmap = json.load(open(mapf))
    vmax = {n: v["max_v"] for n, v in cons["nets"].items() if "max_v" in v}
    vnorm = {n: v.get("normal_v", v["max_v"]) for n, v in cons["nets"].items() if "max_v" in v}
    nets_of = {}
    for n, nodes in d["nets"].items():
        for r, p in nodes: nets_of.setdefault(r, {})[p] = n
    o = ["# Design review packet", "",
         f"{len(d['comps'])} parts, {len(d['nets'])} nets. Everything below is generated from the build; nothing here is a judgement.", ""]
    # 1 coverage gaps
    o += ["## 1. What the gate did not check", ""]
    nolim = {}
    for r, c in sorted(d["comps"].items()):
        if c["lib"].split(":")[0] in ("Device", "power") or c["lib"] in ("Connector:TestPoint", "Connector_Generic:Conn_01x01", "Mechanical:MountingHole"): continue
        if kbmap.get(c["lib"]) not in limits: nolim.setdefault(c["lib"], []).append(r)
    o += ["Parts with no limits file (their pins were not checked against anything):", ""]
    o += [f"- `{lib}`: {', '.join(rs)}" for lib, rs in nolim.items()] or ["- none"]
    waiv = {p: L["waiver"] for p, L in limits.items() if "waiver" in L}
    o += ["", "Limits files that are waivers (declared not to need limits, or open):", ""] + ([f"- {p}: {w}" for p, w in sorted(waiv.items())] or ["- none"])
    nov = sorted(n for n in d["nets"] if n not in vmax)
    o += ["", f"Nets with no declared voltage ({len(nov)}); ratings on them are unchecked:", "", ", ".join(f"`{n}`" for n in nov) or "none"]
    unl = []
    for r, c in sorted(d["comps"].items()):
        L = limits.get(kbmap.get(c["lib"]))
        if not L or not L.get("abs_max"): continue
        have = {p for k in ("abs_max",) for a in L.get(k, []) for p in a["pins"]}
        miss = [pin["name"] for pin in symlib.pins(*c["lib"].split(":"))
                if re.sub(r"[~{}]", "", pin["name"]) not in have and nets_of.get(r, {}).get(pin["num"]) and vmax.get(nets_of[r][pin["num"]], 0) > 0]
        if miss: unl.append(f"- {r} ({kbmap[c['lib']]}): {', '.join(sorted(set(miss)))}")
    o += ["", "Connected IC pins with no absolute-maximum row in their limits file:", ""] + (unl or ["- none"])
    # 2 margins
    rows = []
    for r, c in d["comps"].items():
        L = limits.get(kbmap.get(c["lib"]))
        if not L: continue
        for kind, key, src in (("abs max", "abs_max", vmax), ("recommended", "rec_max", vnorm), ("tested", "tested_max", vmax)):
            lim = {p: a for a in L.get(key, []) for p in a["pins"]}
            for pin in symlib.pins(*c["lib"].split(":")):
                a = lim.get(re.sub(r"[~{}]", "", pin["name"])); n = nets_of.get(r, {}).get(pin["num"])
                if a and n in src and a["max_v"] > 0 and src[n] > 0:
                    rows.append((1 - src[n] / a["max_v"], f"| {r}.{pin['name']} | {n} | {src[n]:g} | {a['max_v']:g} | {kind} | p.{a['page']} | {100 * (1 - src[n] / a['max_v']):.0f} % |"))
    rows.sort()
    o += ["", "## 2. Thinnest voltage margins (20 lowest)", "", "| Pin | Net | Net voltage, V | Limit, V | Kind | Source | Margin |", "|---|---|---|---|---|---|---|"]
    seen = set()
    for m, line in rows:
        if line not in seen: seen.add(line); o.append(line)
        if len(seen) >= 20: break
    caps = []
    across = cons.get("across", {})
    for r, c in d["comps"].items():
        m = re.search(r"(\d+(?:\.\d+)?)\s*V\b", c["value"])
        if not (c["lib"].startswith("Device:C") and m): continue
        on = nets_of.get(r, {}); v = across.get(r, max((vmax[n] for n in on.values() if n in vmax), default=0))
        if v > 0: caps.append((1 - v / float(m.group(1)), f"| {r} | {c['value']} | {v:g} | {100 * (1 - v / float(m.group(1))):.0f} % |"))
    caps.sort()
    o += ["", "Capacitors with the least voltage headroom (10 lowest; ceramic capacitance also falls with DC bias):", "", "| Part | Value | Sees, V | Headroom |", "|---|---|---|---|"] + [l for _, l in caps[:10]]
    # 3 set points
    o += ["", "## 3. Set points the design declares", "", "| Name | Formula | Parts and constants | Target | Tolerance |", "|---|---|---|---|---|"]
    for k, e in sorted(cons.get("expect", {}).items()):
        bind = ", ".join(f"{a}={b} ({d['comps'][b]['value']})" if b in d["comps"] else f"{a}={b}" for a, b in e["bind"].items())
        o.append(f"| {k} | `{e['expr']}` | {bind} | {e['target']} {e.get('unit', '')} | {e['tol']} |")
    o += ["", "A set point that is not in this table is not checked by anything."]
    # 4 waived findings
    o += ["", "## 4. Gate findings waived in the design code", ""]
    wv = cons.get("waive", {}); wv = dict(wv) if not isinstance(wv, dict) else wv
    o += [f"- `{k}`: {v}" for k, v in wv.items()] or ["- none"]
    # 5 questions
    o += ["", "## 5. Questions the reviewer answers, with a datasheet page for each answer", "",
          "Answer each for every IC and protection part, starting with the parts in sections 1 and 2.", "",
          "1. Does any table other than absolute maximum and recommended conditions limit a pin here? Look for tested tolerance, hot-plug, short-circuit, surge and ESD rows, and for footnotes under the tables.",
          "2. Does a fault put more on a pin than the declared net voltage: a neighbouring pin shorted in a connector, a clamp's let-through voltage, an inductive kick, a reversed or hot-plugged input?",
          "3. For each set point in section 3: is the formula the datasheet's, with every internal resistance and offset, and does the worst case over part tolerance stay inside what the load can take?",
          "4. Which behaviour is set by firmware or a configuration memory and not by parts? What does the circuit do with that memory blank or wrong?",
          "5. When one set point moves, which others move with it because they share a divider or a pin?",
          "6. Is every part still sensible in its normal running state, not only safe at the maximum: capacitor bias, regulator dropout, minimum load, start-up order, enable pins and their defaults?",
          "7. Is anything that the application notes require missing: a capacitor value range, a pull resistor, a required diode, a layout-critical part?",
          "8. Does each declared net voltage in the code match what the circuit can really produce?", "",
          "Write findings to `findings.json` (see `review_check.py`). A finding without a datasheet page and quote is an opinion and is rejected by the check."]
    text = "\n".join(o) + "\n"
    open(outf or f"{build}/review_packet.md", "w").write(text); return text

if __name__ == "__main__":
    t = main(*sys.argv[1:]); print(f"wrote review packet, {len(t.splitlines())} lines")
