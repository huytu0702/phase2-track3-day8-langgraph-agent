let selectedScenarioId = null;
let lastThreadId = 'ui-demo';
let selectedCheckpointId = null;

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  const payload = await response.json();
  if (!payload.success) throw new Error(payload.error || 'Request failed');
  return payload.data;
}

function renderTimeline(state) {
  const timeline = document.querySelector('#timeline');
  timeline.innerHTML = '';
  for (const event of state.events || []) {
    const item = document.createElement('li');
    item.textContent = `${event.node}: ${event.message}`;
    timeline.appendChild(item);
  }
}

function renderHitl(data) {
  const status = document.querySelector('#hitlStatus');
  const payload = document.querySelector('#approvalPayload');
  if (data.interrupted) {
    status.textContent = `Waiting for human approval on thread ${lastThreadId}.`;
    payload.textContent = JSON.stringify({
      proposed_action: data.state.proposed_action,
      risk_level: data.state.risk_level,
      scenario_id: data.state.scenario_id,
    }, null, 2);
    return;
  }
  const approval = data.state && data.state.approval;
  status.textContent = approval ? `Approval recorded: ${approval.approved}` : 'No pending approval.';
  payload.textContent = approval ? JSON.stringify(approval, null, 2) : '';
}

function renderResult(data) {
  document.querySelector('#metric').textContent = JSON.stringify(data.metric || data, null, 2);
  if (data.state) renderTimeline(data.state);
  renderHitl(data);
}

function formatNodes(state) {
  return (state.events || []).map((event) => event.node).join(' -> ');
}

function renderThreadCompare({ sourceThreadId, forkThreadId, checkpointId, sourceState, forkState }) {
  const container = document.querySelector('#threadCompare');
  container.innerHTML = '';
  const source = document.createElement('div');
  source.className = 'compare-card';
  source.innerHTML = `<h3>Original thread</h3>
    <p><strong>${sourceThreadId}</strong></p>
    <p>Checkpoint used: <code>${checkpointId}</code></p>
    <p>Status: waiting before approval</p>
    <pre>${formatNodes(sourceState)}</pre>`;

  const fork = document.createElement('div');
  fork.className = 'compare-card';
  fork.innerHTML = `<h3>Forked thread</h3>
    <p><strong>${forkThreadId}</strong></p>
    <p>Decision: Reject</p>
    <p>Status: resumed and finalized</p>
    <pre>${formatNodes(forkState)}</pre>`;

  container.appendChild(source);
  container.appendChild(fork);
}

function renderHistory(history) {
  const status = document.querySelector('#historyStatus');
  const container = document.querySelector('#history');
  container.innerHTML = '';
  selectedCheckpointId = null;
  if (!history.length) {
    status.textContent = `No checkpoints found for thread ${lastThreadId}.`;
    return;
  }
  status.textContent = `Loaded ${history.length} checkpoints for thread ${lastThreadId}. Select one with next_nodes containing approval for time travel.`;
  for (const checkpoint of history) {
    const row = document.createElement('label');
    row.className = 'checkpoint';
    const input = document.createElement('input');
    input.type = 'radio';
    input.name = 'checkpoint';
    input.value = checkpoint.checkpoint_id;
    input.addEventListener('change', () => { selectedCheckpointId = checkpoint.checkpoint_id; });
    const summary = document.createElement('span');
    summary.textContent = `${checkpoint.checkpoint_id} | last=${checkpoint.last_node || 'start'} | next=${checkpoint.next_nodes.join(',') || 'done'} | events=${checkpoint.event_count}`;
    row.appendChild(input);
    row.appendChild(summary);
    container.appendChild(row);
  }
}

async function loadHistory() {
  const data = await api(`/api/history?thread_id=${encodeURIComponent(lastThreadId)}`);
  renderHistory(data.history);
}

function selectApprovalCheckpoint(history) {
  const checkpoint = history.find((item) => item.next_nodes.includes('approval'));
  if (!checkpoint) return false;
  selectedCheckpointId = checkpoint.checkpoint_id;
  const input = document.querySelector(`input[name="checkpoint"][value="${checkpoint.checkpoint_id}"]`);
  if (input) input.checked = true;
  return true;
}

async function forkSelectedCheckpoint() {
  const status = document.querySelector('#historyStatus');
  if (!selectedCheckpointId) {
    status.textContent = 'Please load history and select a checkpoint first. Choose the row with next=approval.';
    return;
  }
  const forkThreadId = document.querySelector('#forkThreadId').value || `${lastThreadId}-fork-${Date.now()}`;
  try {
    const data = await api('/api/time-travel', {
      method: 'POST',
      body: JSON.stringify({
        source_thread_id: lastThreadId,
        checkpoint_id: selectedCheckpointId,
        new_thread_id: forkThreadId,
        approval: { approved: false, reviewer: 'ui', comment: document.querySelector('#comment').value },
      }),
    });
    lastThreadId = forkThreadId;
    document.querySelector('#threadId').value = forkThreadId;
    renderResult({ state: data.state, metric: data });
    await loadHistory();
  } catch (error) {
    status.textContent = `Time travel failed: ${error.message}`;
  }
}

async function runTimeTravelDemo() {
  const status = document.querySelector('#historyStatus');
  const scenarioId = 'S24_risky_send_email';
  const sourceThreadId = `demo-time-travel-${Date.now()}`;
  const forkThreadId = `${sourceThreadId}-reject`;
  status.textContent = 'Running demo: risky scenario -> checkpoint history -> fork reject...';
  selectedScenarioId = scenarioId;
  lastThreadId = sourceThreadId;
  document.querySelector('#threadId').value = sourceThreadId;
  document.querySelector('#forkThreadId').value = forkThreadId;
  const scenarioInput = document.querySelector(`input[value="${scenarioId}"]`);
  if (scenarioInput) scenarioInput.checked = true;

  const runData = await api('/api/run-scenario', {
    method: 'POST',
    body: JSON.stringify({ scenario_id: scenarioId, thread_id: sourceThreadId }),
  });
  renderResult(runData);

  const historyData = await api(`/api/history?thread_id=${encodeURIComponent(sourceThreadId)}`);
  renderHistory(historyData.history);
  if (!selectApprovalCheckpoint(historyData.history)) {
    status.textContent = 'Demo failed: no checkpoint with next=approval was found.';
    return;
  }

  const forkData = await api('/api/time-travel', {
    method: 'POST',
    body: JSON.stringify({
      source_thread_id: sourceThreadId,
      checkpoint_id: selectedCheckpointId,
      new_thread_id: forkThreadId,
      approval: { approved: false, reviewer: 'ui-demo', comment: 'auto demo reject' },
    }),
  });
  lastThreadId = forkThreadId;
  document.querySelector('#threadId').value = forkThreadId;
  renderResult({ state: forkData.state, metric: forkData });
  renderThreadCompare({
    sourceThreadId,
    forkThreadId,
    checkpointId: selectedCheckpointId,
    sourceState: runData.state,
    forkState: forkData.state,
  });
  status.textContent = `Demo done: forked ${sourceThreadId} at checkpoint ${selectedCheckpointId} into ${forkThreadId} with Reject.`;
}

async function loadScenarios() {
  const data = await api('/api/scenarios');
  const container = document.querySelector('#scenarios');
  container.innerHTML = '';
  for (const scenario of data.scenarios) {
    const row = document.createElement('label');
    row.className = 'scenario';
    row.innerHTML = `<input type="radio" name="scenario" value="${scenario.id}">
      <strong>${scenario.id}</strong>
      <span>${scenario.query}</span>
      <span class="badge">${scenario.expected_route}</span>`;
    row.querySelector('input').addEventListener('change', () => { selectedScenarioId = scenario.id; });
    container.appendChild(row);
  }
}

document.querySelector('#runSelected').addEventListener('click', async () => {
  if (!selectedScenarioId) return;
  lastThreadId = document.querySelector('#threadId').value || `ui-${selectedScenarioId}-${Date.now()}`;
  const data = await api('/api/run-scenario', {
    method: 'POST',
    body: JSON.stringify({ scenario_id: selectedScenarioId, thread_id: lastThreadId }),
  });
  renderResult(data);
});

document.querySelector('#runAll').addEventListener('click', async () => {
  renderResult(await api('/api/run-all', { method: 'POST', body: JSON.stringify({}) }));
});

document.querySelector('#demoTimeTravel').addEventListener('click', async () => {
  await runTimeTravelDemo();
});

document.querySelector('#loadHistory').addEventListener('click', async () => {
  await loadHistory();
});

document.querySelector('#forkReject').addEventListener('click', async () => {
  await forkSelectedCheckpoint();
});

for (const [id, approved] of [['#approve', true], ['#reject', false]]) {
  document.querySelector(id).addEventListener('click', async () => {
    const data = await api('/api/resume', {
      method: 'POST',
      body: JSON.stringify({
        thread_id: lastThreadId,
        approval: { approved, reviewer: 'ui', comment: document.querySelector('#comment').value },
      }),
    });
    renderResult({ state: data.state, metric: data.metric || data.state });
  });
}

loadScenarios().catch((error) => { document.querySelector('#metric').textContent = error.message; });
