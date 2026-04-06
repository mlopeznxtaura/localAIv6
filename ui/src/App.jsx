import { useState, useEffect, useRef } from 'react';

const API = '';  // same origin — Express serves both

const STATUS_COLOR = {
  pending:  '#555',
  running:  '#facc15',
  complete: '#4ade80',
  failed:   '#f87171'
};

const STATUS_ICON = {
  pending:  '○',
  running:  '◉',
  complete: '✓',
  failed:   '✗'
};

export default function App() {
  const [intent, setIntent]           = useState('');
  const [aggressiveness, setAgg]       = useState(20);
  const [phase, setPhase]             = useState('idle'); // idle | building | ready | scheduled | done
  const [sessionId, setSessionId]     = useState('');
  const [tasks, setTasks]         = useState([]);
  const [training, setTraining]   = useState({ total: 0, clean: 0, completions: 0 });
  const [output, setOutput]       = useState({ ready: false, size_kb: 0 });
  const [log, setLog]             = useState('');
  const [steps, setSteps]         = useState([]);
  const [error, setError]         = useState('');
  const pollRef                   = useRef(null);

  // Parse step progress from log
  useEffect(() => {
    const stepRegex = /STEP (\d)\/6 — (.+)/g;
    const found = [];
    let match;
    while ((match = stepRegex.exec(log)) !== null) {
      found.push({ num: parseInt(match[1]), label: match[2] });
    }
    if (found.length > 0) {
      setSteps(found);
    }
  }, [log]);

  // Poll tasks + training + output every 2s when scheduled
  useEffect(() => {
    if (phase === 'scheduled' || phase === 'done') {
      pollRef.current = setInterval(async () => {
        const [tr, tg, op] = await Promise.all([
          fetch(`${API}/api/tasks`).then(r => r.json()).catch(() => ({ tasks: [] })),
          fetch(`${API}/api/training`).then(r => r.json()).catch(() => ({})),
          fetch(`${API}/api/output`).then(r => r.json()).catch(() => ({}))
        ]);
        setTasks(tr.tasks || []);
        setTraining(tg);
        setOutput(op);
        if (op.ready) setPhase('done');
      }, 2000);
    }
    return () => clearInterval(pollRef.current);
  }, [phase]);

  const handleBuild = async () => {
    if (!intent.trim()) return;
    setPhase('building');
    setError('');
    setLog('');
    setSteps([]);
    try {
      const res = await fetch(`${API}/api/build`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ intent, aggressiveness })
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || 'Build failed');
        setPhase('idle');
        return;
      }
      setSessionId(data.session_id);
      setLog(data.log || '');
      // Fetch tasks immediately after pipeline completes
      const tr = await fetch(`${API}/api/tasks`).then(r => r.json()).catch(() => ({ tasks: [] }));
      setTasks(tr.tasks || []);
      setPhase('ready');
    } catch (e) {
      setError(String(e));
      setPhase('idle');
    }
  };

  const handleTrigger = async () => {
    try {
      const res = await fetch(`${API}/api/trigger`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId })
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || 'Trigger failed');
        return;
      }
      setPhase('scheduled');
    } catch (e) {
      setError(String(e));
    }
  };

  const handleAccelerate = async (taskId) => {
    await fetch(`${API}/api/accelerate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task_id: taskId })
    });
  };

  const reset = () => {
    setPhase('idle');
    setIntent('');
    setTasks([]);
    setLog('');
    setError('');
    setOutput({ ready: false, size_kb: 0 });
  };

  const counts = {
    complete: tasks.filter(t => t.status === 'complete').length,
    running:  tasks.filter(t => t.status === 'running').length,
    pending:  tasks.filter(t => t.status === 'pending').length,
    failed:   tasks.filter(t => t.status === 'failed').length,
  };

  return (
    <div style={styles.app}>
      <div style={styles.header}>
        <div style={styles.wordmark}>local-ai-v6</div>
        <div style={styles.subtitle}>Stateless Generation + Deterministic Learning</div>
      </div>

      {phase === 'idle' && (
        <div style={styles.composer}>
          <textarea
            style={styles.textarea}
            value={intent}
            onChange={e => setIntent(e.target.value)}
            placeholder="Describe what you want to build..."
            rows={5}
            onKeyDown={e => { if (e.key === 'Enter' && e.metaKey) handleBuild(); }}
          />
          {error && <div style={styles.error}>{error}</div>}
          <div style={styles.sliderRow}>
            <label style={styles.sliderLabel}>
              Prompt compression
              <span style={styles.sliderValue}>
                {aggressiveness === 0 ? 'Off — preserve exactly' :
                 aggressiveness <= 15 ? `${aggressiveness}% — light` :
                 aggressiveness <= 30 ? `${aggressiveness}% — moderate` :
                 aggressiveness <= 40 ? `${aggressiveness}% — aggressive` :
                 `${aggressiveness}% — maximum`}
              </span>
            </label>
            <input
              type="range" min={0} max={50} step={5}
              value={aggressiveness}
              onChange={e => setAgg(Number(e.target.value))}
              style={styles.slider}
            />
            <div style={styles.sliderTicks}>
              <span>0% off</span><span>25% moderate</span><span>50% max</span>
            </div>
          </div>
          <div style={styles.row}>
            <button style={styles.buildBtn} onClick={handleBuild} disabled={!intent.trim()}>
              Build
            </button>
            <span style={styles.hint}>⌘↵  ·  Fully offline  ·  Self-scheduling</span>
          </div>
        </div>
      )}

      {phase === 'building' && (
        <div style={styles.logBox}>
          <div style={styles.muted}>Running pipeline steps 0–6...</div>
          {steps.length > 0 && (
            <div style={styles.stepList}>
              {steps.map((s, i) => (
                <div key={s.num} style={{
                  ...styles.stepItem,
                  opacity: i === steps.length - 1 ? 1 : 0.5
                }}>
                  <span style={styles.stepNum}>{s.num}</span>
                  <span>{s.label}</span>
                  {i === steps.length - 1 && <span style={styles.stepActive}>running...</span>}
                </div>
              ))}
            </div>
          )}
          <pre style={styles.log}>{log}</pre>
        </div>
      )}

      {phase === 'ready' && (
        <div style={styles.readyBox}>
          <div style={styles.muted}>Pipeline complete. {tasks.length} task(s) generated.</div>
          <div style={styles.row}>
            <button style={styles.triggerBtn} onClick={handleTrigger}>
              ⚡ Trigger 1st Cron
            </button>
            <span style={styles.hint}>Starts root tasks — rest self-schedule</span>
          </div>
        </div>
      )}

      {(phase === 'scheduled' || phase === 'done') && (
        <>
          {/* Summary bar */}
          <div style={styles.summaryBar}>
            <span style={{ color: '#4ade80' }}>✓ {counts.complete}</span>
            <span style={{ color: '#facc15', marginLeft: 16 }}>◉ {counts.running}</span>
            <span style={{ color: '#555', marginLeft: 16 }}>○ {counts.pending}</span>
            <span style={{ color: '#f87171', marginLeft: 16 }}>✗ {counts.failed}</span>
            <span style={{ color: '#555', marginLeft: 24, fontSize: 12 }}>
              Training: {training.clean} clean / {training.total} records
            </span>
            {output.ready && (
              <a href={`${API}/api/download`} style={styles.downloadBtn}>
                ↓ output.zip ({output.size_kb}KB)
              </a>
            )}
          </div>

          {/* Task list */}
          <div style={styles.taskList}>
            {tasks.map(t => (
              <div key={t.id} style={styles.taskRow}>
                <span style={{ color: STATUS_COLOR[t.status] || '#555', width: 16 }}>
                  {STATUS_ICON[t.status] || '○'}
                </span>
                <span style={styles.taskId}>{t.id}</span>
                <span style={{ ...styles.taskStatus, color: STATUS_COLOR[t.status] || '#555' }}>
                  {t.status}
                </span>
                <span style={styles.taskTitle}>{t.title || ''}</span>
                <span style={styles.taskTiming}>
                  {t.actual_seconds != null
                    ? `${t.actual_seconds.toFixed(1)}s / est ${t.est_seconds}s`
                    : `est ${t.est_seconds}s`}
                </span>
                {t.status !== 'complete' && t.status !== 'running' && (
                  <button style={styles.accelBtn} onClick={() => handleAccelerate(t.id)}>
                    ⚡
                  </button>
                )}
              </div>
            ))}
          </div>

          <div style={styles.resetRow}>
            <button style={styles.resetBtn} onClick={reset}>Build something else</button>
          </div>
        </>
      )}
    </div>
  );
}

const styles = {
  app: {
    background: '#0c0c0c', color: '#e8e8e8', minHeight: '100vh',
    fontFamily: '-apple-system, "Inter", sans-serif', padding: '32px 24px',
    maxWidth: 800, margin: '0 auto'
  },
  header: { marginBottom: 32 },
  wordmark: {
    fontSize: 12, fontWeight: 600, letterSpacing: '0.18em',
    textTransform: 'uppercase', color: '#555'
  },
  subtitle: { fontSize: 13, color: '#444', marginTop: 4 },
  composer: { display: 'flex', flexDirection: 'column', gap: 16 },
  textarea: {
    width: '100%', background: '#141414', border: '1px solid #222',
    borderRadius: 10, color: '#e8e8e8', fontSize: 15, lineHeight: 1.6,
    padding: 16, resize: 'vertical', outline: 'none', fontFamily: 'inherit'
  },
  row: { display: 'flex', alignItems: 'center', gap: 16 },
  buildBtn: {
    background: '#e8e8e8', color: '#0c0c0c', border: 'none',
    borderRadius: 8, fontSize: 14, fontWeight: 600,
    padding: '10px 24px', cursor: 'pointer'
  },
  hint: { fontSize: 12, color: '#555' },
  error: { color: '#f87171', fontSize: 13 },
  sliderRow: { display: 'flex', flexDirection: 'column', gap: 6 },
  sliderLabel: {
    display: 'flex', justifyContent: 'space-between',
    fontSize: 12, color: '#555'
  },
  sliderValue: { color: '#aaa', fontVariantNumeric: 'tabular-nums' },
  slider: { width: '100%', accentColor: '#e8e8e8', cursor: 'pointer' },
  sliderTicks: {
    display: 'flex', justifyContent: 'space-between',
    fontSize: 10, color: '#444'
  },
  logBox: { background: '#141414', borderRadius: 8, padding: 16 },
  readyBox: { background: '#141414', borderRadius: 8, padding: 16, display: 'flex', flexDirection: 'column', gap: 12 },
  stepList: { display: 'flex', flexDirection: 'column', gap: 4, marginTop: 12, marginBottom: 8 },
  stepItem: { display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: '#aaa' },
  stepNum: { background: '#222', borderRadius: 4, padding: '2px 8px', fontSize: 11, fontFamily: 'monospace', color: '#e8e8e8' },
  stepActive: { color: '#facc15', fontSize: 11, marginLeft: 'auto' },
  triggerBtn: {
    background: '#facc15', color: '#0c0c0c', border: 'none',
    borderRadius: 8, fontSize: 14, fontWeight: 600,
    padding: '10px 24px', cursor: 'pointer'
  },
  log: { fontSize: 11, color: '#555', whiteSpace: 'pre-wrap', marginTop: 8, maxHeight: 200, overflow: 'auto' },
  muted: { fontSize: 13, color: '#555' },
  summaryBar: {
    display: 'flex', alignItems: 'center', flexWrap: 'wrap',
    gap: 4, padding: '12px 0', borderBottom: '1px solid #222', marginBottom: 8
  },
  downloadBtn: {
    marginLeft: 'auto', background: '#4ade80', color: '#0c0c0c',
    borderRadius: 6, padding: '4px 12px', fontSize: 12, fontWeight: 600,
    textDecoration: 'none'
  },
  taskList: { display: 'flex', flexDirection: 'column', gap: 2 },
  taskRow: {
    display: 'flex', alignItems: 'center', gap: 10,
    padding: '6px 0', borderBottom: '1px solid #1a1a1a', fontSize: 13
  },
  taskId: { color: '#555', width: 48, flexShrink: 0, fontFamily: 'monospace' },
  taskStatus: { width: 80, flexShrink: 0, fontSize: 11 },
  taskTitle: { flex: 1, color: '#aaa', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' },
  taskTiming: { color: '#444', fontSize: 11, width: 120, textAlign: 'right', flexShrink: 0 },
  accelBtn: {
    background: 'transparent', border: '1px solid #333', borderRadius: 4,
    color: '#facc15', cursor: 'pointer', padding: '2px 6px', fontSize: 11
  },
  resetRow: { marginTop: 24 },
  resetBtn: {
    background: 'transparent', color: '#555', border: '1px solid #222',
    borderRadius: 8, fontSize: 13, padding: '8px 20px', cursor: 'pointer'
  }
};
