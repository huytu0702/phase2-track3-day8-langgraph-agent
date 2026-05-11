# Implementation Plan — Scenario-Driven Fault-Tolerance Lab

## 1. Mục tiêu đã điều chỉnh

Bài lab không chỉ là xây một support-ticket agent. Mục tiêu chính là xây **khung kiểm thử scenario thực tế** để đánh giá khả năng chịu lỗi của một LangGraph workflow:

- Chạy nhiều scenario input khác nhau từ `data/sample/scenarios.jsonl`.
- Kiểm tra route thực tế so với route kỳ vọng.
- Kiểm tra retry loop, dead-letter, human-in-the-loop, checkpoint/resume.
- Ghi lại node timeline, state transitions, tool/LLM evidence và metrics.
- Có UI HTML/CSS/JS thuần để chạy scenario, xem luồng, xem lỗi, approve/reject và resume.

Nói ngắn gọn: đây là **scenario runner + resilience test harness** cho LangGraph agent.

## 2. Ràng buộc đã xác nhận

- UI dùng HTML/CSS/JS thuần.
- Không dùng FastAPI.
- Có thể dùng Python standard library HTTP server để bridge browser với graph Python.
- Dùng SQLite checkpoint, không dùng PostgreSQL.
- `.env` đã tồn tại ở project root và chứa OpenAI config.
- Dùng OpenAI thật tại những node cần LLM.
- Human approval phải là thật qua UI/CLI resume, không auto-approve.
- Không hard-code theo scenario ID hoặc exact query.
- Cài dependency vào `.venv`.
- Scenario lỗi phải reproducible để test được retry/dead-letter ổn định.

## 3. Điểm quan trọng: controlled fault injection không phải mock

Để test khả năng chịu lỗi, không thể phụ thuộc vào lỗi ngẫu nhiên từ OpenAI hoặc tool bên ngoài. Vì vậy test harness cần **controlled fault injection** dựa trên metadata scenario:

- `should_retry: true` kích hoạt failure mode có kiểm soát.
- `max_attempts` giới hạn retry.
- scenario có tag `dead_letter` phải đi đến dead-letter khi retry exhausted.
- lỗi được tạo ra bởi harness như một phần của bài test resilience, không phải fake answer.

Nguyên tắc:

- Không fake kết quả thành công.
- Không mock approval.
- Không hard-code theo scenario ID.
- Fault injection chỉ dùng để tạo lỗi có chủ đích nhằm kiểm tra retry/recovery/dead-letter.
- Tool/LLM evidence vẫn phải được ghi vào state và metrics.

## 4. Scenario taxonomy

Bộ scenario là trung tâm của lab. Mỗi scenario kiểm tra một năng lực riêng.

| Nhóm | Mục tiêu kiểm thử | Ví dụ |
|---|---|---|
| `simple` | Happy path không cần tool | reset password, policy FAQ |
| `tool` | Cần gọi tool hoặc tra cứu dữ liệu | order status, invoice, tracking |
| `missing_info` | Input mơ hồ, thiếu thông tin | “Can you fix it?”, “Help me with this” |
| `risky` | Cần human approval | refund, delete, cancel, revoke, send email |
| `error` | Lỗi có thể retry | timeout, unavailable, rate limit, transient failure |
| `dead_letter` | Retry exhausted | unrecoverable system failure |
| priority conflicts | Kiểm tra route priority | refund + order status phải route risky |
| checkpoint/resume | Kiểm tra interruption và resume | risky approval, crash/resume |

Route priority đề xuất:

```text
risky > tool > missing_info > error > simple
```

Riêng scenario resilience có `should_retry` hoặc tag error/dead_letter phải kích hoạt failure path sau khi đã chọn route phù hợp.

## 5. Kiến trúc đích

```text
JSONL scenarios
  -> scenario loader
  -> scenario runner
      -> initial_state(scenario)
      -> LangGraph compiled graph
          -> intake
          -> classify
          -> route
          -> tool / approval / retry / dead_letter / answer
          -> finalize
      -> SQLite checkpoint
      -> state history
      -> metrics
  -> report
  -> HTML/CSS/JS UI
```

Graph target:

```text
START
  -> intake
  -> classify
      simple       -> answer -> finalize -> END
      tool         -> tool -> evaluate -> answer/retry -> finalize/END
      missing_info -> clarify -> finalize -> END
      risky        -> risky_action -> approval_interrupt -> tool/clarify -> evaluate -> answer -> finalize
      error        -> retry -> tool -> evaluate -> retry/dead_letter/answer
      exhausted    -> dead_letter -> finalize -> END
```

## 6. Data model và scenario contract

Current fields:

```json
{
  "id": "S01_simple",
  "query": "How do I reset my password?",
  "expected_route": "simple",
  "requires_approval": false,
  "should_retry": false,
  "max_attempts": 3,
  "tags": ["simple"]
}
```

Cần đảm bảo `Scenario` model hỗ trợ:

- `id`: unique.
- `query`: input thực tế.
- `expected_route`: `simple | tool | missing_info | risky | error`.
- `requires_approval`: risky route có cần HITL hay không.
- `should_retry`: scenario có fault injection/retry không.
- `max_attempts`: giới hạn retry.
- `tags`: phân loại scenario.

Có thể bổ sung sau nếu cần:

- `expected_terminal_node`: `finalize | dead_letter`.
- `expected_interrupt`: boolean.
- `fault_mode`: `none | transient | permanent | timeout | rate_limit`.
- `expected_resume`: boolean.

Nếu bổ sung field mới, phải giữ backward-compatible với JSONL hiện tại.

## 7. File/module dự kiến

### Existing files to update

- `data/sample/scenarios.jsonl`
  - mở rộng bộ scenario edge cases.
- `pyproject.toml`
  - thêm SQLite checkpoint, OpenAI, dotenv nếu cần.
- `configs/lab.yaml`
  - dùng SQLite.
  - thêm OpenAI config.
  - thêm scenario runner/fault injection config.
- `src/langgraph_agent_lab/state.py`
  - thêm state fields cho scenario metadata, fault injection, checkpoint/resume, approval.
- `src/langgraph_agent_lab/scenarios.py`
  - validate scenario IDs unique.
  - support extra fields nếu cần.
- `src/langgraph_agent_lab/nodes.py`
  - node behavior theo scenario-driven test harness.
- `src/langgraph_agent_lab/routing.py`
  - route priority và bounded retry.
- `src/langgraph_agent_lab/graph.py`
  - compile graph với SQLite checkpointer.
- `src/langgraph_agent_lab/persistence.py`
  - SQLite checkpoint thật.
- `src/langgraph_agent_lab/metrics.py`
  - fault-tolerance metrics.
- `src/langgraph_agent_lab/cli.py`
  - run scenario, run all, resume, state, history, serve UI.
- `src/langgraph_agent_lab/report.py`
  - report scenario coverage và failure analysis.

### New files to add

- `src/langgraph_agent_lab/llm.py`
  - OpenAI adapter thật.
- `src/langgraph_agent_lab/tools.py`
  - local tools thật trong phạm vi lab.
- `src/langgraph_agent_lab/faults.py`
  - controlled fault injection dựa trên scenario metadata.
- `src/langgraph_agent_lab/runner.py`
  - scenario runner dùng chung cho CLI/UI.
- `src/langgraph_agent_lab/web_server.py`
  - stdlib HTTP server.
- `src/langgraph_agent_lab/templates/index.html`
  - UI chính.
- `src/langgraph_agent_lab/static/styles.css`
  - giao diện.
- `src/langgraph_agent_lab/static/app.js`
  - frontend logic.
- `tests/test_scenario_suite.py`
  - validate scenario suite.
- `tests/test_fault_tolerance.py`
  - retry/dead-letter/checkpoint tests.
- `tests/test_persistence_sqlite.py`
  - SQLite checkpoint/resume.

## 8. Dependency plan

Cài vào `.venv`:

```bash
python -m venv .venv
.venv/Scripts/python -m pip install --upgrade pip
.venv/Scripts/python -m pip install -e ".[dev,sqlite]"
.venv/Scripts/python -m pip install openai python-dotenv
```

Không cài FastAPI/Uvicorn.

## 9. Cấu hình đề xuất

`configs/lab.yaml`:

```yaml
scenarios_path: data/sample/scenarios.jsonl
checkpointer: sqlite
database_url: outputs/checkpoints.sqlite
report_path: reports/lab_report.md

llm:
  provider: openai
  enabled: true
  model: gpt-4.1-mini
  timeout_seconds: 30
  max_retries: 2
  nodes:
    classify: true
    evaluate: true
    answer: true

fault_injection:
  enabled: true
  source: scenario_metadata
  deterministic: true

approval:
  mode: interrupt
  require_human: true

web:
  host: 127.0.0.1
  port: 8765
```

`.env` expected values:

```text
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4.1-mini
```

Không log secret, không hiển thị secret trong UI, không ghi secret vào metrics/report.

## 10. Phase triển khai

### Phase 1 — Setup `.venv` và dependency

Mục tiêu:
- Cài dependencies vào `.venv`.
- Xác nhận import LangGraph, SQLite checkpointer, OpenAI.

Verify:

```bash
.venv/Scripts/python -m pytest
.venv/Scripts/python -c "from langgraph.checkpoint.sqlite import SqliteSaver; print(SqliteSaver)"
.venv/Scripts/python -c "from openai import OpenAI; print(OpenAI)"
```

### Phase 2 — Scenario suite validation

Mục tiêu:
- JSONL có đủ scenario thực tế và edge cases.
- Scenario IDs unique.
- Route values hợp lệ.
- Coverage đủ các nhóm route/failure.

Việc làm:
1. Mở rộng `data/sample/scenarios.jsonl` thêm 30 scenario.
2. Thêm validation test:
   - mỗi line là JSON hợp lệ.
   - ID không trùng.
   - có đủ route categories.
   - có ít nhất một retry và một dead-letter.
   - risky scenario phải `requires_approval=true`.
3. Không hard-code exact answer.

Verify:

```bash
.venv/Scripts/python -m pytest tests/test_scenario_suite.py
```

### Phase 3 — SQLite checkpoint/resume thật

Mục tiêu:
- State được checkpoint vào SQLite.
- Có thể restart process và resume bằng `thread_id`.

Việc làm:
1. Sửa `persistence.py` để dùng `SqliteSaver` với `sqlite3.connect`.
2. Bật WAL mode.
3. Config mặc định dùng `outputs/checkpoints.sqlite`.
4. Test state history và resume.

Verify:

```bash
.venv/Scripts/python -m pytest tests/test_persistence_sqlite.py
```

### Phase 4 — Graph nodes theo scenario-driven harness

Mục tiêu:
- Node logic xử lý scenario thực tế, không hard-code ID.
- Fault injection deterministic theo metadata.

Việc làm:
1. `intake_node`: normalize query và attach scenario metadata.
2. `classify_node`: route theo policy + optional OpenAI structured classification.
3. `tool_node`: gọi local tool thật trong phạm vi lab.
4. `faults.py`: inject lỗi nếu scenario yêu cầu retry.
5. `evaluate_node`: đánh giá tool result hoặc lỗi.
6. `retry_or_fallback_node`: tăng attempt, ghi error event.
7. `dead_letter_node`: ghi terminal failure.
8. `answer_node`: answer dựa trên state/evidence.
9. `finalize_node`: ghi audit event.

Verify:

```bash
.venv/Scripts/python -m pytest tests/test_graph_smoke.py tests/test_routing.py tests/test_fault_tolerance.py
```

### Phase 5 — Real HITL interrupt/resume

Mục tiêu:
- Risky scenario dừng thật tại approval.
- User phải approve/reject bằng CLI hoặc UI.
- Không auto approve.

Việc làm:
1. `approval_node` dùng `langgraph.types.interrupt()`.
2. CLI `resume` nhận approval payload.
3. UI hiển thị approval card khi graph interrupted.
4. Metrics ghi interrupt/approval observed.

Verify:

```bash
.venv/Scripts/python -m langgraph_agent_lab.cli run-scenario --id S04_risky --thread-id hitl-demo
.venv/Scripts/python -m langgraph_agent_lab.cli resume --thread-id hitl-demo --approve true --comment "approved for demo"
```

### Phase 6 — OpenAI integration thật

Mục tiêu:
- OpenAI dùng cho classify/evaluate/answer theo config.
- Output structured, parseable.
- Nếu OpenAI lỗi, error đi vào state và retry/dead-letter policy.

Việc làm:
1. Tạo `llm.py`.
2. Load `.env`.
3. Validate `OPENAI_API_KEY` khi `llm.enabled=true`.
4. Prompt trả JSON cho classify/evaluate.
5. Unit tests không gọi OpenAI; manual/integration test opt-in gọi thật.

Verify:

```bash
.venv/Scripts/python -m langgraph_agent_lab.cli run-scenario --id S01_simple --thread-id openai-demo
```

### Phase 7 — Scenario runner CLI

Mục tiêu:
- Có CLI dùng chung cho grading và demo.

Commands đề xuất:

```text
run-scenario --id S01_simple --thread-id ...
run-scenarios --config configs/lab.yaml --output outputs/metrics.json
resume --thread-id ... --approve true|false --comment ...
show-state --thread-id ...
history --thread-id ...
serve-ui --config configs/lab.yaml
```

Runner behavior:

- Load scenario.
- Build initial state.
- Invoke graph với `thread_id`.
- Nếu interrupted, trả trạng thái `requires_human_input`.
- Nếu complete, ghi metrics.
- Không crash toàn batch nếu một scenario fail; ghi failure metric.

### Phase 8 — UI HTML/CSS/JS scenario dashboard

Mục tiêu:
- UI phục vụ test harness, không chỉ chat UI.

UI sections:

1. Scenario catalog
   - list toàn bộ scenario.
   - filter theo route/tag.
   - badge `retry`, `hitl`, `dead_letter`, `edge`.

2. Runner controls
   - Run selected scenario.
   - Run all non-HITL scenarios.
   - custom query.
   - thread_id.

3. Expected vs actual
   - expected route.
   - actual route.
   - pass/fail.

4. Flow timeline
   - node events.
   - retry attempts.
   - tool/LLM evidence.
   - dead-letter marker.

5. HITL panel
   - proposed action.
   - risk evidence.
   - Approve/Reject buttons.
   - comment.

6. Checkpoint panel
   - thread id.
   - current state.
   - state history.
   - resume status.

7. Metrics dashboard
   - success rate.
   - route coverage.
   - retry count.
   - interrupts.
   - dead-letter count.

Backend stdlib endpoints:

```text
GET  /                         -> index.html
GET  /static/styles.css         -> CSS
GET  /static/app.js             -> JS
GET  /api/scenarios             -> scenario catalog
POST /api/run-scenario          -> run by id
POST /api/run-custom            -> run custom query
POST /api/resume                -> resume interrupted thread
GET  /api/state?thread_id=...   -> current checkpoint state
GET  /api/history?thread_id=... -> checkpoint history/events
GET  /api/metrics               -> latest metrics
```

Verify:

```bash
.venv/Scripts/python -m langgraph_agent_lab.cli serve-ui --config configs/lab.yaml
```

Open:

```text
http://127.0.0.1:8765
```

### Phase 9 — Metrics/report

Mục tiêu:
- Metrics phản ánh khả năng chịu lỗi, không chỉ “có answer”.

Metrics cần có:

- `scenario_id`
- `expected_route`
- `actual_route`
- `success`
- `nodes_visited`
- `retry_count`
- `max_attempts`
- `interrupt_count`
- `approval_required`
- `approval_observed`
- `dead_letter_observed`
- `checkpoint_thread_id`
- `resume_success`
- `latency_ms`
- `errors`

Report cần có:

- Scenario coverage table.
- Route confusion summary.
- Retry/dead-letter analysis.
- HITL analysis.
- Checkpoint/resume evidence.
- Known failure modes.
- UI demo guide.

Verify:

```bash
.venv/Scripts/python -m langgraph_agent_lab.cli run-scenarios --config configs/lab.yaml --output outputs/metrics.json
.venv/Scripts/python -m langgraph_agent_lab.cli validate-metrics --metrics outputs/metrics.json
```

### Phase 10 — Final verification and review

Commands:

```bash
.venv/Scripts/python -m pytest --cov=src --cov-report=term-missing
.venv/Scripts/python -m ruff check src tests
.venv/Scripts/python -m mypy src
```

Review bắt buộc sau code changes:

- Python/code review.
- Security review vì có `.env`, HTTP server, SQLite, OpenAI, file system access.

## 11. Success criteria

Hoàn thành khi:

- `scenarios.jsonl` có bộ scenario đa dạng, gồm ít nhất 37 scenario total.
- Scenario validation pass.
- Graph chạy đủ route categories.
- Retry/dead-letter deterministic và reproducible.
- HITL risky scenario thật sự interrupt và cần resume.
- SQLite checkpoint chứng minh resume được.
- OpenAI được gọi thật khi config bật.
- UI chạy scenario, hiển thị expected/actual, timeline, retry, HITL, checkpoint, metrics.
- `outputs/metrics.json` hợp lệ.
- `reports/lab_report.md` đầy đủ.
- Tests/lint/typecheck pass hoặc mọi exception được ghi rõ.

## 12. Rủi ro và xử lý

### Rủi ro: “Không mock” xung đột với fault injection

Cách xử lý: fault injection là mục tiêu của test harness, không phải mock answer. Nó tạo failure có chủ đích để kiểm tra resilience.

### Rủi ro: OpenAI gây flaky/cost

Cách xử lý: unit tests không gọi OpenAI. Runtime demo gọi OpenAI thật khi config bật. Lỗi API được ghi vào state và xử lý theo retry/dead-letter.

### Rủi ro: destructive risky actions

Cách xử lý: không gọi dịch vụ thật để refund/delete/email. Trong lab, risky action dừng ở human approval và audit evidence. Nếu cần destructive execution thật, phải có sandbox service riêng.

### Rủi ro: UI thuần nhưng cần Python interaction

Cách xử lý: dùng Python standard library HTTP server làm bridge. Không dùng web framework.

### Rủi ro: Hidden scenarios

Cách xử lý: classification theo policy/state/LLM structured output, không match scenario ID hoặc exact query.

## 13. Lệnh demo cuối

```bash
.venv/Scripts/python -m pytest
.venv/Scripts/python -m ruff check src tests
.venv/Scripts/python -m mypy src
.venv/Scripts/python -m langgraph_agent_lab.cli run-scenarios --config configs/lab.yaml --output outputs/metrics.json
.venv/Scripts/python -m langgraph_agent_lab.cli validate-metrics --metrics outputs/metrics.json
.venv/Scripts/python -m langgraph_agent_lab.cli serve-ui --config configs/lab.yaml
```

Open browser:

```text
http://127.0.0.1:8765
```
