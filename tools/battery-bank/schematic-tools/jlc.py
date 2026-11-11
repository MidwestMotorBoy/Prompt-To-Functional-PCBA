"""JLC parts keyword search (the same JLC API that DevBoard/tools/jlc_stock.py uses for its BOM stock check).

usage: python -I jlc.py KEYWORD [KEYWORD ...]     prints up to 8 hits per keyword: code, library, stock, price, MPN,
                                                  package, description
"""
import json
import subprocess
import sys

URL = "https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList"


def search(keyword, n=8):
    r = subprocess.run(["curl", "-s", "-m", "40", "-X", "POST", URL, "-H", "Content-Type: application/json", "-d",
                        json.dumps({"keyword": keyword, "currentPage": 1, "pageSize": n})],
                       capture_output=True, text=True).stdout
    try:
        lst = json.loads(r)["data"]["componentPageInfo"]["list"] or []
    except (ValueError, KeyError, TypeError):
        return None
    out = []
    for x in lst:
        lib = x["componentLibraryType"]
        lib = "basic" if lib == "base" else ("preferred" if x.get("preferredComponentFlag") else "extended")
        p = x.get("componentPrices") or []
        out.append({"code": x["componentCode"], "lib": lib, "stock": x["stockCount"],
                    "price": p[0]["productPrice"] if p else None, "mpn": x["componentModelEn"],
                    "pkg": x.get("componentSpecificationEn"), "desc": (x.get("describe") or "")[:110]})
    return out


if __name__ == "__main__":
    for kw in sys.argv[1:]:
        res = search(kw)
        print("==", kw, "(API error)" if res is None else "")
        for h in res or []:
            print("  %-10s %-9s %8s $%-7s %-28s %-10s %s" % (h["code"], h["lib"], h["stock"], h["price"], h["mpn"][:28],
                                                           (h["pkg"] or "")[:10], h["desc"]))
