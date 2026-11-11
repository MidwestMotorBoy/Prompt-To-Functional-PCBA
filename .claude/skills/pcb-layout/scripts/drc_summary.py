"""Run KiCad DRC with schematic parity and summarise it by violation type.

    python drc_summary.py board.kicad_pcb [--baseline previous.rpt] [--out report.rpt] [--kicad-cli PATH]

kicad-cli rewrites <project>.kicad_pro when it runs; this script restores the file byte-for-byte afterwards, so the
project's rules and settings survive. Prints counts per violation type, the unconnected and parity totals, and, with
--baseline, the change per type against an earlier report (useful after each routing stage).
Works with any python (no pcbnew needed).
"""
import collections
import os
import re
import shutil
import subprocess
import sys
import tempfile

args = sys.argv[1:]


def opt(name, default=None):
    if name in args:
        i = args.index(name)
        v = args[i + 1]
        del args[i:i + 2]
        return v
    return default


baseline = opt("--baseline")
out = opt("--out")
cli = opt("--kicad-cli")
if cli is None:
    cli = shutil.which("kicad-cli") or r"C:/Program Files/KiCad/10.0/bin/kicad-cli.exe"
board = os.path.abspath(args[0])
pro = os.path.splitext(board)[0] + ".kicad_pro"
out = out or os.path.join(tempfile.mkdtemp(), "drc.rpt")

saved = open(pro, "rb").read() if os.path.exists(pro) else None
try:
    r = subprocess.run([cli, "pcb", "drc", "--schematic-parity", "--severity-all", "-o", out, board],
                       capture_output=True, text=True)
finally:
    if saved is not None:
        open(pro, "wb").write(saved)
print(r.stdout.strip())


def counts(path):
    c = collections.Counter()
    for line in open(path, encoding="utf-8", errors="replace"):
        m = re.match(r"\[(\w+)\]", line)
        if m:
            c[m.group(1)] += 1
    return c


now = counts(out)
old = counts(baseline) if baseline else None
print(f"\nreport: {out}")
print(f"{'type':32} {'count':>6}" + (f" {'change':>7}" if old else ""))
for k in sorted(set(now) | set(old or {}), key=lambda k: -now.get(k, 0)):
    line = f"{k:32} {now.get(k, 0):6d}"
    if old is not None:
        dlt = now.get(k, 0) - old.get(k, 0)
        line += f" {dlt:+7d}" if dlt else f" {'':>7}"
    print(line)
