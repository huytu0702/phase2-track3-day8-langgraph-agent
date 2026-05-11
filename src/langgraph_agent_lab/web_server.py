from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .runner import resume_thread, run_scenario_by_id, run_scenarios
from .scenarios import load_scenarios

PACKAGE_DIR = Path(__file__).parent


def create_api_response(
    payload: dict[str, Any], status: int = 200
) -> tuple[int, dict[str, str], bytes]:
    body = json.dumps({"success": status < 400, "data": payload}, ensure_ascii=False).encode(
        "utf-8"
    )
    return status, {"Content-Type": "application/json; charset=utf-8"}, body


def create_error_response(message: str, status: int = 400) -> tuple[int, dict[str, str], bytes]:
    body = json.dumps({"success": False, "error": message}, ensure_ascii=False).encode("utf-8")
    return status, {"Content-Type": "application/json; charset=utf-8"}, body


def parse_json_body(body: bytes) -> dict[str, Any]:
    try:
        parsed = json.loads(body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return {"success": False, "error": "Invalid JSON body"}
    if not isinstance(parsed, dict):
        return {"success": False, "error": "JSON body must be an object"}
    return {"success": True, "data": parsed}


class LabRequestHandler(BaseHTTPRequestHandler):
    scenarios_path = Path("data/sample/scenarios.jsonl")
    checkpointer_kind = "memory"
    database_url: str | None = None
    latest_metrics: dict[str, Any] | None = None

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self.write_file(PACKAGE_DIR / "templates" / "index.html", "text/html; charset=utf-8")
            return
        if parsed.path == "/static/styles.css":
            self.write_file(PACKAGE_DIR / "static" / "styles.css", "text/css; charset=utf-8")
            return
        if parsed.path == "/static/app.js":
            self.write_file(
                PACKAGE_DIR / "static" / "app.js", "application/javascript; charset=utf-8"
            )
            return
        if parsed.path == "/api/scenarios":
            scenarios = [
                scenario.model_dump(mode="json") for scenario in load_scenarios(self.scenarios_path)
            ]
            self.write_response(*create_api_response({"scenarios": scenarios}))
            return
        if parsed.path == "/api/metrics":
            self.write_response(
                *create_api_response(self.latest_metrics or {"scenario_metrics": []})
            )
            return
        if parsed.path == "/api/state":
            query = parse_qs(parsed.query)
            self.write_response(
                *create_api_response({"thread_id": query.get("thread_id", [""])[0]})
            )
            return
        self.write_response(*create_error_response("Not found", 404))

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        payload = self.read_json_payload()
        if not payload["success"]:
            self.write_response(*create_error_response(payload["error"], 400))
            return
        data = payload["data"]

        try:
            if parsed.path == "/api/run-scenario":
                result = run_scenario_by_id(
                    str(data["scenario_id"]),
                    scenarios_path=self.scenarios_path,
                    checkpointer_kind=self.checkpointer_kind,
                    database_url=self.database_url,
                    thread_id=data.get("thread_id"),
                )
                self.write_response(
                    *create_api_response(
                        {
                            "state": result.state,
                            "metric": result.metric.model_dump(),
                            "interrupted": result.interrupted,
                        }
                    )
                )
                return
            if parsed.path == "/api/resume":
                state = resume_thread(
                    thread_id=str(data["thread_id"]),
                    approval=data.get("approval", {}),
                    checkpointer_kind=self.checkpointer_kind,
                    database_url=self.database_url,
                )
                self.write_response(*create_api_response({"state": state}))
                return
            if parsed.path == "/api/run-all":
                report = run_scenarios(
                    scenarios_path=self.scenarios_path,
                    checkpointer_kind=self.checkpointer_kind,
                    database_url=self.database_url,
                    include_hitl=False,
                )
                self.latest_metrics = report.model_dump()
                self.write_response(*create_api_response(self.latest_metrics))
                return
        except Exception as exc:
            self.write_response(*create_error_response(str(exc), 500))
            return

        self.write_response(*create_error_response("Not found", 404))

    def read_json_payload(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        return parse_json_body(self.rfile.read(length))

    def write_file(self, path: Path, content_type: str) -> None:
        if not path.exists():
            self.write_response(*create_error_response("Asset not found", 404))
            return
        self.write_response(200, {"Content-Type": content_type}, path.read_bytes())

    def write_response(self, status: int, headers: dict[str, str], body: bytes) -> None:
        self.send_response(status)
        for name, value in headers.items():
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve(
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    scenarios_path: Path = Path("data/sample/scenarios.jsonl"),
    checkpointer_kind: str = "memory",
    database_url: str | None = None,
) -> None:
    os.environ["LANGGRAPH_INTERRUPT"] = "true"
    LabRequestHandler.scenarios_path = scenarios_path
    LabRequestHandler.checkpointer_kind = checkpointer_kind
    LabRequestHandler.database_url = database_url
    server = ThreadingHTTPServer((host, port), LabRequestHandler)
    server.serve_forever()
