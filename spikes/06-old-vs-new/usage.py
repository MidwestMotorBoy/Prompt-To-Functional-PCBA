"""usage.py <agent transcript.jsonl>: tokens, tool calls and wall time of one agent run."""
import json, sys, datetime
tin = tout = cr = cw = tools = turns = 0; ts = []; seen = set()
for l in open(sys.argv[1]):
    try: e = json.loads(l)
    except Exception: continue
    if e.get("timestamp"): ts.append(e["timestamp"])
    m = e.get("message") or {}
    if e.get("type") == "assistant" and m.get("usage"):
        tools += sum(1 for c in m.get("content", []) if isinstance(c, dict) and c.get("type") == "tool_use")
        if m.get("id") in seen: continue
        seen.add(m.get("id")); u = m["usage"]; turns += 1
        tin += u.get("input_tokens", 0); tout += u.get("output_tokens", 0); cr += u.get("cache_read_input_tokens", 0); cw += u.get("cache_creation_input_tokens", 0)
t = [datetime.datetime.fromisoformat(x.replace("Z", "+00:00")) for x in ts]
print(json.dumps(dict(model_calls=turns, tool_calls=tools, input=tin, cache_write=cw, cache_read=cr, output=tout, minutes=round((max(t) - min(t)).total_seconds() / 60, 1))))
