import json
with open('training_data/stream.jsonl') as f:
    lines = [l.strip() for l in f if l.strip()]
for line in lines[-20:]:
    r = json.loads(line)
    m = r.get('metadata', {})
    if m.get('type') == 'task_completion':
        print(f"TASK: {m.get('task_id')} | est={m.get('est_seconds')}s | actual={m.get('actual_seconds')}s | passed={m.get('passed_test')}")
    elif 'step' in m:
        fb = 'FALLBACK' if m.get('used_fallback') else 'OK'
        print(f"Step {m['step']} {m['step_name']}/{m['substep']} | {fb}")
