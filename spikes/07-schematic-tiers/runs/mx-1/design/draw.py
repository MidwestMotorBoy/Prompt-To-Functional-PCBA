"""Draws KiCad schematic sheets from netlist.json. The netlist is the truth; these sheets are a view of it.

Each block becomes one sheet. An IC is drawn with the small parts that belong to its pins laid out as lanes (a wire
running out from each pin, with decoupling, pull-ups and series parts along it); parts without an IC are drawn as
small circuits of their own; every group sits in a titled frame, and the frames are packed on a page sized to them.
Nothing here decides connectivity: make.sh exports KiCad's own netlist of the result and compares it with the code's.

usage: draw.py <build dir> <out dir> <project name>
"""
import json, os, sys
from sch import uid, q, VERSION
from layout import Block


def main(build, out, project):
    d = json.load(open(f"{build}/netlist.json"))
    cons = json.load(open(f"{build}/constraints.json"))
    comps, nets, nc = d["comps"], d["nets"], d.get("nc", [])
    order = sorted(comps, key=lambda r: comps[r].get("order", 0))
    os.makedirs(out, exist_ok=True)
    root_uuid = uid("root", project)
    blocks = []
    for r in order:
        b = comps[r]["block"]
        if b not in blocks: blocks.append(b)
    root = [f'(kicad_sch (version {VERSION}) (generator "p2p_draw") (generator_version "10.0") (uuid {q(root_uuid)}) (paper "A4") '
            f'(title_block (title {q(project)}) (comment 1 "Generated from code. Do not edit: change the source and rebuild.")) (lib_symbols)']
    for i, b in enumerate(blocks):
        fn = b.lower().replace(" ", "_") + ".kicad_sch"
        B = Block(b, comps, nets, nc, cons, order, i, project, root_uuid)
        s, paper = B.draw_sheet()
        s.write(f"{out}/{fn}", paper)
        from sch import lint
        probs = lint(s)
        print(f"{b}: {paper[0]}x{paper[1]} mm, {len(probs)} lint findings")
        for p in probs[:int(os.environ.get('LINT_MAX', '12'))]: print("   ", p)
        x, y = 21.59 + (i % 3) * 88.9, 30.48 + (i // 3) * 55.88
        BW, BH = 81.28, 26.67
        # inside the box: the page and the circuits drawn on that sheet, one line each
        lines = [f"Page {i + 2}"] + [l for t in getattr(B, "drawn_titles", []) for l in B.wrap("- " + t, BW - 5)]
        for k, ln in enumerate(lines):
            tx, ty = x + 3.0, y + 6.0 + 2.54 * k
            root.append(f'(text {q(ln)} (exclude_from_sim no) (at {tx} {ty} 0) (effects (font (size 1.27 1.27)) (justify left bottom)) '
                        f'(uuid {q(uid(project, "roottext", i, k))}))')
        root.append(
            f'(sheet (at {x} {y}) (size {BW} {BH}) (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no) (stroke (width 0.1524) (type solid)) '
            f'(fill (color 0 0 0 0)) (uuid {q(s.uuid)}) '
            f'(property "Sheetname" {q(b)} (at {x} {y - 0.7} 0) (effects (font (size 1.27 1.27)) (justify left bottom))) '
            f'(property "Sheetfile" {q(fn)} (at {x} {y + BH + 0.6} 0) (effects (font (size 1.27 1.27)) (justify left top))) '
            f'(instances (project {q(project)} (path {q("/" + root_uuid)} (page {q(i + 2)})))))')
    root.append('(sheet_instances (path "/" (page "1"))) (embedded_fonts no))')
    open(f"{out}/{project}.kicad_sch", "w").write("\n".join(root) + "\n")
    print("wrote", len(blocks), "sheets to", out)

if __name__ == "__main__":
    main(*sys.argv[1:4])
