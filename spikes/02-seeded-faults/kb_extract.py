"""Read a datasheet's pin table without an LLM. Every fact keeps its page and the line it came from.

usage: kb_extract.py <datasheet.pdf> <part name> <out.json> [--pins N]
Finds pages headed "Pin Functions" / "Pin Description(s)" / "Pin Configuration", then rows that hold a pin-number
list and a pin name in the first columns, in either order. Needs pdftotext (poppler).
"""
import hashlib, json, re, subprocess, sys

HEAD = re.compile(r"Pin (Functions|Descriptions?|Configuration|Assignments?)|Terminal Functions|PIN (FUNCTIONS|DESCRIPTION)", re.I)
NUM = r"(?:[A-H]?\d{1,3}|[A-H]\d{1,2})"
NUMS = rf"{NUM}(?:\s?[,–-]\s?{NUM})*"
NAME = r"[A-Z][A-Za-z0-9_/+#\-.]*(?:\s?\([A-Za-z0-9_/+\-. ]+\))?"
TYPE = r"(?:Power|PWR|GND|Ground|I/O|IO|I|O|P|G|A|AI|AO|DI|DO|Analog|Digital|Input|Output|Supply|S|—|-|NC|OD)"
ROW_A = re.compile(rf"^\s*(?P<nums>{NUMS})\s{{2,}}(?P<name>{NAME})\s{{2,}}(?P<type>{TYPE})?(?:\s{{2,}}|\s*$)(?P<desc>.*)$")
ROW_B = re.compile(rf"^\s*(?P<name>{NAME})\s{{2,}}(?P<nums>{NUMS})\s{{2,}}(?P<type>{TYPE})?(?:\s{{2,}}|\s*$)(?P<desc>.*)$")

def expand(nums):
    out = []
    for part in re.split(r"\s?,\s?", nums):
        m = re.match(rf"^(\d+)\s?[–-]\s?(\d+)$", part)
        if m: out += [str(i) for i in range(int(m.group(1)), int(m.group(2)) + 1)]
        else: out.append(part.strip())
    return out

def main(pdf, part, out, npins=None):
    sha = hashlib.sha256(open(pdf, "rb").read()).hexdigest()
    n = int(re.search(r"Pages:\s+(\d+)", subprocess.run(["pdfinfo", pdf], capture_output=True, text=True).stdout).group(1))
    pins, pages = {}, []
    for pg in range(1, min(n, 40) + 1):
        txt = subprocess.run(["pdftotext", "-layout", "-f", str(pg), "-l", str(pg), pdf, "-"], capture_output=True, text=True).stdout
        if not HEAD.search(txt): continue
        got = 0
        for line in txt.splitlines():
            m = ROW_A.match(line) or ROW_B.match(line)
            if not m or m.group("name") in ("NO", "NO.", "NAME", "PIN", "TYPE", "Table", "Figure", "Product", "Copyright"): continue
            if len(m.group("name")) > 24: continue
            for num in expand(m.group("nums")):
                if num in pins: continue
                pins[num] = {"name": m.group("name").strip(), "type": (m.group("type") or "").strip(), "page": pg, "quote": " ".join(line.split())}
                got += 1
        if got: pages.append(pg)
    kb = {"part": part, "datasheet": pdf.split("/")[-1], "sha256": sha, "pin_pages": pages, "pins": dict(sorted(pins.items(), key=lambda kv: (len(kv[0]), kv[0]))),
          "source": "deterministic table read", "expected_pins": npins, "complete": (len(pins) == npins) if npins else None}
    json.dump(kb, open(out, "w"), indent=1)
    print(f"{part}: {len(pins)} pins" + (f" of {npins}" if npins else "") + f" from pages {pages}")

if __name__ == "__main__":
    a = sys.argv[1:]; n = int(a[a.index("--pins") + 1]) if "--pins" in a else None
    main(a[0], a[1], a[2], n)
