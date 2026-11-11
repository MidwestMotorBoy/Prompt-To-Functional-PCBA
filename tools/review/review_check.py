"""review_check.py <findings.json> <datasheet dir>
Checks the reviewer's findings file. Exit 1 if a finding has no verified evidence, or a serious finding is still open.
findings.json: [{"id": "F1", "part": "U405", "claim": "...", "severity": "blocks" | "should fix" | "note",
                 "evidence": {"pdf": "tpd4s201.pdf", "page": 6, "quote": "exact words from that page"},
                 "outcome": "open" | "fixed" | "rule" | "waived" | "not a problem", "outcome_note": "..."}]
outcome "rule" means the gap was closed by a new gate rule or limits row; the note names it. Every finding found
by review should end as "rule" where a machine can check it, so the same miss cannot happen twice."""
import sys, json, subprocess
OUT = {"open", "fixed", "rule", "waived", "not a problem"}; SEV = {"blocks", "should fix", "note"}

def main(ff, sheets):
    fs = json.load(open(ff)); bad = 0; pages = {}
    for f in fs:
        tag = f"{f.get('id', '?')} {f.get('part', '')}"
        ev = f.get("evidence") or {}
        if f.get("severity") not in SEV or f.get("outcome") not in OUT: print(f"BAD FIELD  {tag}: severity or outcome"); bad += 1; continue
        if ev.get("pdf") not in pages and ev.get("pdf"):
            t = subprocess.run(["pdftotext", "-layout", f"{sheets}/{ev['pdf']}", "-"], capture_output=True, text=True).stdout
            pages[ev["pdf"]] = [" ".join(p.split()) for p in t.split("\f")]
        pg = pages.get(ev.get("pdf"), [])
        if not (ev.get("quote") and 0 < ev.get("page", 0) <= len(pg) and " ".join(ev["quote"].split()) in pg[ev["page"] - 1]):
            print(f"NO EVIDENCE  {tag}: quote not found on p.{ev.get('page')} of {ev.get('pdf')}"); bad += 1; continue
        if f["outcome"] != "open" and not f.get("outcome_note"): print(f"NO NOTE  {tag}: outcome '{f['outcome']}' needs a note"); bad += 1; continue
        if f["outcome"] == "open" and f["severity"] != "note": print(f"OPEN  {tag} ({f['severity']}): {f['claim']}"); bad += 1; continue
        print(f"ok  {tag}: {f['outcome']}")
    print(f"{len(fs) - bad} of {len(fs)} findings settled with evidence"); return bad

if __name__ == "__main__":
    sys.exit(1 if main(*sys.argv[1:]) else 0)
