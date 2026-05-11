# LangGraph Agent Lab

LangGraph support-agent lab with routing, retry, HITL approval, checkpoint persistence, and UI demo.

## Final Report
- [Lab Report Final](./reports/lab_report_final.md)

## Run UI
From project root:

```bash
python -m langgraph_agent_lab.cli serve-ui --config configs/lab.yaml
```

Open UI at: `http://127.0.0.1:8765`

## UI Results

### 1) Home screen
![UI Home](./docs/screenshots/ui-home.png)

### 2) After running one scenario
![UI Run Scenario](./docs/screenshots/ui-run-scenario.png)

### 3) Metrics / batch run state
![UI Metrics](./docs/screenshots/ui-metrics.png)

### 4) Crash Recovery & Time Travel demo
![UI Crash Recovery Time Travel Demo](./docs/screenshots/ui-crash-recovery-time-travel-demo.png)

## Quick Verify
```bash
ls -la reports/lab_report_final.md
ls -la docs/screenshots
```
