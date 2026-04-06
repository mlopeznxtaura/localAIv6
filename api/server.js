/**
 * local-ai-v6 — api/server.js
 * Single port (3000). Serves built React static files + API.
 * Dev: React on 3001 (npm start in ui/), API on 3000.
 * Prod: npm run build in ui/, Express serves ui/build/ on 3000.
 */
const express = require('express');
const { exec, spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const { v4: uuidv4 } = require('uuid');

const app = express();
app.use(express.json());

// Serve built React app in production
const UI_BUILD = path.join(__dirname, '..', 'ui', 'build');
if (fs.existsSync(UI_BUILD)) {
  app.use(express.static(UI_BUILD));
}

const PIPELINE_DIR = path.join(__dirname, '..', 'pipeline');
const PROJECT_ROOT = path.join(__dirname, '..');

// POST /api/build — run pipeline steps 0-6 (no triggers)
app.post('/api/build', (req, res) => {
  const { intent, aggressiveness = 20 } = req.body;
  if (!intent) return res.status(400).json({ error: 'Missing intent' });

  const sessionId = uuidv4().replace(/-/g, '').substring(0, 16);
  const cronFactor = process.env.CRON_FACTOR || '10';
  const agg = Math.max(0, Math.min(50, parseInt(aggressiveness, 10) || 20));

  const cmd = [
    `cd ${PIPELINE_DIR}`,
    `echo ${JSON.stringify(intent)} > user_prompt.txt`,
    `LAV6_SESSION_ID=${sessionId} CRON_FACTOR=${cronFactor} COMPRESSION_AGGRESSIVENESS=${agg} python3 run.py --no-trigger`
  ].join(' && ');

  exec(cmd, { timeout: 600000 }, (err, stdout, stderr) => {
    if (err) {
      return res.status(500).json({ error: stderr || err.message, stdout });
    }
    res.json({ session_id: sessionId, log: stdout });
  });
});

// POST /api/trigger — fire `at` for root tasks (manual first trigger)
app.post('/api/trigger', (req, res) => {
  const { session_id } = req.body;
  const tasksFile = path.join(PIPELINE_DIR, 'tasks.json');
  const scheduleFile = path.join(PIPELINE_DIR, 'cron_schedule.json');

  if (!fs.existsSync(tasksFile) || !fs.existsSync(scheduleFile)) {
    return res.status(400).json({ error: 'No tasks or schedule found — run pipeline first' });
  }

  const tasks = JSON.parse(fs.readFileSync(tasksFile, 'utf8'));
  const schedule = JSON.parse(fs.readFileSync(scheduleFile, 'utf8'));
  const cronFactor = process.env.CRON_FACTOR || '10';
  const aggressiveness = process.env.COMPRESSION_AGGRESSIVENESS || '20';
  const sessionId = session_id || process.env.LAV6_SESSION_ID || 'manual';

  const roots = schedule.filter(s => !s.depends_on || s.depends_on.length === 0);
  const results = [];

  for (const entry of roots) {
    const delay = entry.delay_seconds || 30;
    const taskId = entry.id;
    const envStr = `LAV6_SESSION_ID=${sessionId} CRON_FACTOR=${cronFactor} COMPRESSION_AGGRESSIVENESS=${aggressiveness}`;
    const cmd = `cd ${PIPELINE_DIR} && ${envStr} python3 build_one.py ${taskId}`;

    try {
      const proc = require('child_process').spawnSync('at', [`now + ${delay} seconds`], {
        input: cmd + '\n',
        encoding: 'utf8'
      });
      results.push({ task_id: taskId, scheduled: true, delay });
    } catch (e) {
      results.push({ task_id: taskId, scheduled: false, error: e.message });
    }
  }

  res.json({ triggered: results.length, results });
});

// GET /api/tasks — current task status
app.get('/api/tasks', (req, res) => {
  const f = path.join(PIPELINE_DIR, 'tasks.json');
  try {
    const tasks = JSON.parse(fs.readFileSync(f, 'utf8'));
    res.json({ tasks });
  } catch (e) {
    res.json({ tasks: [] });
  }
});

// GET /api/schedule — cron schedule
app.get('/api/schedule', (req, res) => {
  const f = path.join(PIPELINE_DIR, 'cron_schedule.json');
  try {
    res.json(JSON.parse(fs.readFileSync(f, 'utf8')));
  } catch (e) {
    res.json([]);
  }
});

// POST /api/accelerate — skip delay for a task
app.post('/api/accelerate', (req, res) => {
  const { task_id } = req.body;
  if (!task_id) return res.status(400).json({ error: 'Missing task_id' });
  exec(
    `cd ${PROJECT_ROOT} && python3 scripts/accelerate.py ${task_id}`,
    (err, stdout, stderr) => {
      if (err) return res.status(500).json({ error: stderr });
      res.json({ ok: true, log: stdout });
    }
  );
});

// GET /api/training — training data stats
app.get('/api/training', (req, res) => {
  const f = path.join(PROJECT_ROOT, 'training_data', 'stream.jsonl');
  try {
    const lines = fs.readFileSync(f, 'utf8').trim().split('\n').filter(Boolean);
    const clean = lines.filter(l => l.includes('"used_fallback": false')).length;
    const completions = lines.filter(l => l.includes('"task_completion"')).length;
    res.json({ total: lines.length, clean, completions });
  } catch (e) {
    res.json({ total: 0, clean: 0, completions: 0 });
  }
});

// GET /api/output — check if output.zip exists
app.get('/api/output', (req, res) => {
  const zip = path.join(PROJECT_ROOT, 'output.zip');
  const exists = fs.existsSync(zip);
  res.json({
    ready: exists,
    path: exists ? zip : null,
    size_kb: exists ? Math.round(fs.statSync(zip).size / 1024) : 0
  });
});

// Serve output.zip for download
app.get('/api/download', (req, res) => {
  const zip = path.join(PROJECT_ROOT, 'output.zip');
  if (!fs.existsSync(zip)) return res.status(404).json({ error: 'output.zip not ready' });
  res.download(zip, 'output.zip');
});

// Catch-all: serve React app (prod only)
app.get('*', (req, res) => {
  const index = path.join(UI_BUILD, 'index.html');
  if (fs.existsSync(index)) {
    res.sendFile(index);
  } else {
    res.json({ status: 'local-ai-v6 API running', ui: 'run npm start in ui/ for dev UI' });
  }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`[local-ai-v6] API + UI on http://localhost:${PORT}`);
  console.log(`[local-ai-v6] Dev UI: cd ui && npm start`);
});
