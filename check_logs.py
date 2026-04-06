import json
with open('training_data/stream.jsonl') as f:
    lines = [l.strip() for l in f if l.strip()]
for line in lines[-15:]:
    r = json.loads(line)
    m = r['metadata']
    fb = 'FALLBACK' if m['used_fallback'] else 'OK'
    out = r.get('output', '')[:200]
    print(f"Step {m['step']} {m['step_name']}/{m['substep']} | {fb} | {m['latency_ms']}ms | budget={m['budget_tokens']}")
    if m['used_fallback'] or not out.strip():
        print(f"  OUTPUT: '{out}'")
    print()
