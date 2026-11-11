"""Download a part's datasheet PDF through its JLC part page (the signed link expires after 30 minutes).

usage: python -I jlc_datasheet.py LCSC_CODE OUT.pdf
"""
import html
import json
import re
import subprocess
import sys

API = "https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList"
code, out = sys.argv[1], sys.argv[2]
r = subprocess.run(["curl", "-s", "-m", "40", "-X", "POST", API, "-H", "Content-Type: application/json", "-d",
                    json.dumps({"keyword": code, "currentPage": 1, "pageSize": 5})], capture_output=True, text=True).stdout
suffix = next(x["urlSuffix"] for x in json.loads(r)["data"]["componentPageInfo"]["list"] if x["componentCode"] == code)
page = subprocess.run(["curl", "-s", "-L", "-m", "60", "-A", "Mozilla/5.0", "https://jlcpcb.com/partdetail/" + suffix],
                      capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
urls = [html.unescape(u) for u in re.findall(r'https://[^"\\]*smtDataManualFile[^"\\]*x-oss-signature=[0-9a-f]+', page)]
if not urls:
    sys.exit("no datasheet link on the part page")
subprocess.run(["curl", "-s", "-L", "-m", "120", "-o", out, urls[0]], check=True)
print("saved", out)
