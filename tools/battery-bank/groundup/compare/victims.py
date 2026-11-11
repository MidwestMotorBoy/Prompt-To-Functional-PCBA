"""Net classes for the coupling study and an estimate of each victim node's own capacitance."""
import re, collections
from board import FP, SEG, REF
def last(n): return n.split('/')[-1]
RULES = [
 ('Current sense', r'^(SRP_F|SRN_F|ACP_F|ACN_F|SRP|SRN)$'),
 ('Charger analog', r'^(Net-\(U[45]03-(FB|FBG|ICHG|ACOV|ACUV)\)|ILIM|FSW|TS)$'),
 ('Regulator feedback', r'^(Net-\(U[45]0[46]-FB\)|SS_5V)$'),
 ('Gauge analog', r'^(Net-\(U101-(VC[1-4]|PBI|BAT|PACK)\)|TS[1-4]|Net-\(U102-V[1-4]\))$'),
 ('I2C / SMBus', r'^(SCL|SDA|I2CC_SCL|I2CC_SDA|Net-\(U101-SMB[CD]\))$'),
 ('USB CC', r'^(CC1|CC2|C_CC1|C_CC2)$'),
 ('Control / debug', r'^(CHG_INT|IRQ_N|CE_N|EN_5V[12]|CHG_INH|DRV9_OFF|BTP_INT|WAKE|NRST|SWCLK|SWDIO|UART_TX|DPDN_DCP|SBU_FLT)$'),
 ('RF', r'^(RFIO|ANT_IN)$'),
]
def category(net):
    for c, rx in RULES:
        if re.match(rx, last(net)): return c
    return None
def capval(v):
    m = re.match(r'^\s*([\d.]+)\s*([pnuµ])', v or '')
    return float(m.group(1)) * {'p': 1e-12, 'n': 1e-9, 'u': 1e-6, 'µ': 1e-6}[m.group(2)] if m else 0.0
def node_caps():
    """per net: sum of capacitor values on it, IC/connector pin count, track length (mm)"""
    c = collections.defaultdict(float); pins = collections.defaultdict(int); ln = collections.defaultdict(float)
    for fp in FP:
        r = fp['ref'] or ''
        for p in fp['pads']:
            if not p['net']: continue
            if r.startswith('C') and r[1:2].isdigit(): c[p['net']] += capval(fp['val'])
            elif r[:1] in 'UQJ': pins[p['net']] += 1
    for s in SEG:
        if s['net']: ln[s['net']] += ((s['x2']-s['x1'])**2 + (s['y2']-s['y1'])**2) ** 0.5
    return c, pins, ln
def label(net):
    n = last(net); p = ''
    if '/USB Port 1/' in net: p = 'P1 '
    if '/USB Port 2/' in net: p = 'P2 '
    m = re.match(r'Net-\((U\d+)-(.+)\)', n)
    if m:
        u = m.group(1); p = {'U403': 'P1 ', 'U503': 'P2 ', 'U404': 'P1 5V ', 'U504': 'P2 5V ', 'U406': 'P1 9V ', 'U506': 'P2 9V ', 'U101': 'Gauge ', 'U102': '2nd OVP '}.get(u, u + ' ')
        n = m.group(2)
    return p + n
