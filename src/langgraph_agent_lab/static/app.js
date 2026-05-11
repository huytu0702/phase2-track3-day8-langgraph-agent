let selectedScenarioId = null;
let lastThreadId = 'ui-demo';

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
