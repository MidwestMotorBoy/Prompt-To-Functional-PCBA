"""loose.py <run dir> [more run dirs]: power pads that the planned copper does not reach although their terminal
counts as joined. dc.json marks a terminal joined when ANY of its pads reaches the source, and lists the others under
pads_not_joined; score.json's power_open does not show them. A chip with two pad groups on one net (the PD
controllers: VBUS pad 23 is the PPHV switch output, pad 32 the PP5V switch output) can so lose a whole power path
to a 0.2 mm router track. Prints one line per such terminal, with its current; exit 1 when any is found."""
import sys, json, os
bad = 0
for run in sys.argv[1:]:
    here = 0
    d = json.load(open(os.path.join(run, "dc.json"))); nets = d.get("nets", d)
    for n, v in nets.items():
        if not isinstance(v, dict): continue
        for t in v.get("terminals", []):
            if t.get("pads_not_joined"):
                bad += 1; here += 1
                print(f"{run}: {n} at {t['ref']}: pads not joined {t['pads_not_joined']} ({t.get('current_a')} A terminal, joined by its other pads at {t.get('R_mohm')} mohm)")
    if not here: print(f"{run}: every pad of every joined power terminal is on planned copper")
sys.exit(1 if bad else 0)
