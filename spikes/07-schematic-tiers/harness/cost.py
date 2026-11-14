"""cost.py <agent jsonl>... : tokens, dollars, wall time per transcript (dedupe by message id)."""
import json, sys
from datetime import datetime
P = {"claude-fable-5-2": (8, 40, .20), "claude-opus-5-5": (4, 20, .20), "claude-sonnet-5-5": (2, 10, .10)}
def run(f):
    seen, t = {}, []
    for l in open(f):
        d = json.loads(l)
        if d.get("timestamp"): t.append(d["timestamp"])
        m = d.get("message")
        if isinstance(m, dict) and m.get("usage") and m.get("id"):
            seen[m["id"]] = (m.get("model"), m["usage"])
    tot = dict(inp=0, cw5=0, cw1h=0, cr=0, out=0, usd=0.0); models = set()
    for model, u in seen.values():
        if model not in P: continue
        models.add(model); i, o, cr = P[model]
        cc = u.get("cache_creation") or {}
        c5, c1 = cc.get("ephemeral_5m_input_tokens", 0), cc.get("ephemeral_1h_input_tokens", 0)
        if not cc: c5 = u.get("cache_creation_input_tokens", 0)
        tot["inp"] += u["input_tokens"]; tot["cw5"] += c5; tot["cw1h"] += c1
        tot["cr"] += u.get("cache_read_input_tokens", 0); tot["out"] += u["output_tokens"]
        tot["usd"] += (u["input_tokens"] * i + c5 * i * 1.25 + c1 * i * 2 + u.get("cache_read_input_tokens", 0) * cr + u["output_tokens"] * o) / 1e6
    ts = sorted(datetime.fromisoformat(x.replace("Z", "+00:00")) for x in t)
    tot["min"] = (ts[-1] - ts[0]).total_seconds() / 60 if ts else 0
    tot["calls"] = len(seen); tot["model"] = ",".join(models)
    return tot
if __name__ == "__main__":
    for f in sys.argv[1:]:
        r = run(f); print(f.split("/")[-1][:24], json.dumps({k: (round(v, 2) if isinstance(v, float) else v) for k, v in r.items()}))
