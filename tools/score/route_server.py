"""route_server.py: run full trial routes for the layout teams on a big machine (Logan's PC), through git.

  python route_server.py --repo <clone> --kicad-python <python.exe> --kicad-cli <kicad-cli> --pylib <dir> [--jobs 12] [--minutes 60]

Teams queue a board by committing it to their branch (layout-team-A, -B, -C) as
    docs/layout-teams/<team>/route_queue/<name>.kicad_pcb   (+ <name>.kicad_pro and <name>.kicad_dru beside it; the
                                                            template's are used when missing)
The server polls every 2 minutes, routes every queued board it has not routed yet (same name and same file content =
same job), and pushes a result to branch route-results as
    <team>/<name>-<sha8>.json   {"routed", "failed", "edges", "minutes", "status", "tail"}
    <team>/<name>-<sha8>.log    the router log without progress lines
Read results with: git fetch origin route-results && git show origin/route-results:<team>/<name>-<sha8>.json
The router is tools/score/router.py with --softnets=GND,PACK_P,3V3, the same as score_board.sh.
"""
import argparse, json, os, re, subprocess, sys, time, shutil
from concurrent.futures import ThreadPoolExecutor

ap = argparse.ArgumentParser()
ap.add_argument("--repo", required=True); ap.add_argument("--kicad-python", required=True); ap.add_argument("--kicad-cli", required=True)
ap.add_argument("--pylib", required=True); ap.add_argument("--jobs", type=int, default=12); ap.add_argument("--minutes", type=int, default=60)
ap.add_argument("--work", default=None); ap.add_argument("--once", action="store_true")
A = ap.parse_args()
REPO = os.path.abspath(A.repo); WORK = os.path.abspath(A.work or os.path.join(REPO, "..", "route_work")); RES = os.path.join(WORK, "results")
TEAMS = ["A", "B", "C"]
os.makedirs(WORK, exist_ok=True)
LAUNCH = os.path.join(WORK, "launch.py")
open(LAUNCH, "w").write("import sys, runpy\nsys.path.insert(0, %r)\nscript = sys.argv[1]; sys.argv = sys.argv[1:]\nrunpy.run_path(script, run_name='__main__')\n" % os.path.abspath(A.pylib))

def git(*a, cwd=REPO, check=True):
    r = subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True)
    if check and r.returncode: raise RuntimeError("git %s: %s" % (" ".join(a), r.stderr.strip()))
    return r.stdout

def results_tree():
    if not os.path.isdir(os.path.join(RES, ".git")):
        if git("ls-remote", "--heads", "origin", "route-results").strip():
            git("clone", "--branch", "route-results", "--single-branch", git("remote", "get-url", "origin").strip(), RES, cwd=WORK)
        else:
            os.makedirs(RES, exist_ok=True); git("init", "-b", "route-results", cwd=RES)
            git("remote", "add", "origin", git("remote", "get-url", "origin").strip(), cwd=RES)
            open(os.path.join(RES, "README.md"), "w").write("Trial-route results from tools/score/route_server.py. One json and one log per queued board.\n")
            git("add", "-A", cwd=RES); git("commit", "-m", "route-results: start", cwd=RES); git("push", "-u", "origin", "route-results", cwd=RES)

def queued():
    jobs = []
    for t in TEAMS:
        br = "layout-team-" + t
        if not git("ls-remote", "--heads", "origin", br).strip(): continue
        git("fetch", "-q", "origin", br)
        for line in git("ls-tree", "-r", "origin/" + br, "docs/layout-teams/%s/route_queue/" % t).splitlines():
            meta, path = line.split("\t", 1)
            if not path.endswith(".kicad_pcb"): continue
            sha = meta.split()[2]; name = os.path.basename(path)[:-10]
            out = os.path.join(RES, t, "%s-%s.json" % (name, sha[:8]))
            if not os.path.exists(out): jobs.append((t, br, path, name, sha, out))
    return jobs

def run(job):
    t, br, path, name, sha, out = job
    d = os.path.join(WORK, "jobs", "%s_%s_%s" % (t, name, sha[:8])); os.makedirs(d, exist_ok=True)
    for ext in ("kicad_pcb", "kicad_pro", "kicad_dru"):
        src = path[:-10] + "." + ext
        r = subprocess.run(["git", "show", "origin/%s:%s" % (br, src)], cwd=REPO, capture_output=True)
        data = r.stdout if r.returncode == 0 else open(os.path.join(REPO, "tools", "score", "template", "board." + ext), "rb").read()
        open(os.path.join(d, "b." + ext), "wb").write(data)
    shutil.copy(os.path.join(REPO, "tools", "score", "router.py"), d)
    t0 = time.time()
    subprocess.run([A.kicad_cli, "pcb", "drc", "--severity-all", "--format", "json", "-o", "drc.json", "b.kicad_pcb"], cwd=d, capture_output=True)
    status = "done"
    with open(os.path.join(d, "route.log"), "w") as lf:
        try:
            subprocess.run([A.kicad_python, "-u", LAUNCH, "router.py", "b.kicad_pcb", "drc.json", "routed.kicad_pcb", "--softnets=GND,PACK_P,3V3"],
                           cwd=d, stdout=lf, stderr=subprocess.STDOUT, timeout=A.minutes * 60)
        except subprocess.TimeoutExpired: status = "timed out at %d min" % A.minutes
    log = open(os.path.join(d, "route.log"), errors="replace").read()
    m = re.search(r"^routed (\d+) edges, (\d+) failed", log, re.M); e = re.search(r"edges to route: (\d+)", log)
    p = re.findall(r"routed (\d+), failing (\d+)", log)
    routed, failed = (int(m.group(1)), int(m.group(2))) if m else ((int(p[-1][0]), int(p[-1][1])) if p else (None, None))
    if not m and status == "done": status = "router error"
    res = dict(team=t, board=path, sha=sha, routed=routed, failed=failed, edges=int(e.group(1)) if e else None,
               minutes=round((time.time() - t0) / 60, 1), status=status, tail=[l for l in log.splitlines() if "progress" not in l][-5:])
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(res, open(out, "w"), indent=1)
    open(out[:-5] + ".log", "w").write("\n".join(l for l in log.splitlines() if "progress" not in l))
    return res

def publish(msg):
    git("add", "-A", cwd=RES)
    if not git("status", "--porcelain", cwd=RES).strip(): return
    git("commit", "-q", "-m", msg, cwd=RES)
    for i in range(4):
        if subprocess.run(["git", "pull", "-q", "--rebase", "origin", "route-results"], cwd=RES).returncode == 0 and \
           subprocess.run(["git", "push", "-q", "origin", "route-results"], cwd=RES).returncode == 0: return
        time.sleep(5 * (i + 1))
    print("push failed; will retry next round", flush=True)

results_tree(); running = {}
pool = ThreadPoolExecutor(A.jobs)
while True:
    try:
        for job in queued():
            key = job[5]
            if key not in running: running[key] = pool.submit(run, job); print(time.strftime("%H:%M"), "start", job[0], job[3], job[4][:8], flush=True)
        for key, f in list(running.items()):
            if f.done():
                r = f.result() if not f.exception() else {"status": "crash: %s" % f.exception()}
                if f.exception(): os.makedirs(os.path.dirname(key), exist_ok=True); json.dump(r, open(key, "w"))
                print(time.strftime("%H:%M"), "finished", key, r.get("routed"), r.get("failed"), r.get("status"), flush=True)
                publish("route %s: %s" % (os.path.basename(key), r.get("status"))); del running[key]
    except Exception as ex:
        print("error:", ex, flush=True)
    if A.once and not running: break
    time.sleep(120)
