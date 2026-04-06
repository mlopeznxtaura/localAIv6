import json
with open('pipeline/tasks.json') as f:
    tasks = json.load(f)
for t in tasks:
    t['status'] = 'pending'
    t.pop('actual_seconds', None)
with open('pipeline/tasks.json', 'w') as f:
    json.dump(tasks, f, indent=2)
print('Tasks reset to pending')
