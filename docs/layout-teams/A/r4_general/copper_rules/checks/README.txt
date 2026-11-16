Every *.sh / *.py file in this folder runs after scoring as `<script> <outdir>` (score_rules.sh step 7).
Print lines `CHECK {"name": value}`; they are merged into score.json["checks"]. Keep checks cheap (no router, no
hot-loop solve) or they slow every screen. A check for one experiment goes on the command line instead:
score_rules.sh ... --check=path/to/check.py
