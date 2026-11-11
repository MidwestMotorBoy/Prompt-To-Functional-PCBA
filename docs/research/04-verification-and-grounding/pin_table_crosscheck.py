import sys, re, json, time
import pdfplumber
pdf_path, sch_path, sym = sys.argv[1], sys.argv[2], sys.argv[3]
# 1. symbol pins from the schematic's embedded lib_symbols
txt = open(sch_path, encoding='utf-8').read()
i = txt.index('(symbol "%s"' % sym)
depth = 0; j = i
while True:
    c = txt[j]
    if c == '(': depth += 1
    elif c == ')':
        depth -= 1
        if depth == 0: break
    j += 1
blk = txt[i:j+1]
sym_pins = {}
for m in re.finditer(r'\(pin (\w+) \w+.*?\(name "([^"]*)".*?\(number "([^"]*)"', blk, re.S):
    sym_pins[m.group(3)] = (m.group(2), m.group(1))
print('symbol pins', len(sym_pins))
# 2. datasheet pin table: find pages whose tables have a header mentioning LQFP48
t0 = time.time()
ds = {}; pages = []
with pdfplumber.open(pdf_path) as pdf:
    print('pages', len(pdf.pages))
    for pn, page in enumerate(pdf.pages, 1):
        text = page.extract_text() or ''
        if 'pin definitions' not in text.lower(): continue
        for tb in page.extract_tables():
            if not tb or len(tb[0]) < 6: continue
            hdr = ' '.join(str(c) for r in tb[:3] for c in r if c)
            hh = hdr.replace('\n','').replace(' ','')
            if 'LQFP48' not in hh and 'LQFP48'[::-1] not in hh: continue
            # column index of LQFP48
            col = None
            for r in tb[:3]:
                for k, c in enumerate(r):
                    if c and c.replace('\n','').replace(' ','') in ('LQFP48', 'LQFP48'[::-1]): col = k
            # pin-name column: first column after the package columns holding names
            for r in tb[2:] if col is not None else []:
                num = (r[col] or '').strip()
                if not re.fullmatch(r'\d+', num): continue
                name = r[col+1]; typ = r[col+2]
                ds[num] = (name or '').replace('\n', ''); pages.append(pn)
print('datasheet LQFP48 pins', len(ds), 'pages', sorted(set(pages)), 'sec %.1f' % (time.time()-t0))
def norm(s): return re.sub(r'[^A-Z0-9]', '', re.split(r'[/(-]', s.upper())[0])
bad = []
for n in sorted(set(sym_pins) | set(ds), key=lambda x: int(x) if x.isdigit() else 999):
    a = sym_pins.get(n, ('<none>',))[0]; b = ds.get(n, '<none>')
    if norm(a) != norm(b): bad.append((n, a, b))
print('disagreements', len(bad))
for x in bad: print('  pin %s  symbol=%s  datasheet=%s' % x)
json.dump({'symbol': sym_pins, 'datasheet': ds}, open(sys.argv[4], 'w'), indent=1)
