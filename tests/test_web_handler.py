from pathlib import Path

from langgraph_agent_lab.web_server import LabRequestHandler


def test_handler_write_file_returns_404_for_missing_asset(monkeypatch) -> None:
    calls = []
    handler = object.__new__(LabRequestHandler)
    monkeypatch.setattr(handler, "write_response", lambda *args: calls.append(args))

    handler.write_file(Path("missing.file"), "text/plain")

    assert calls[0][0] == 404


def test_handler_read_json_payload_reads_content_length(monkeypatch) -> None:
    handler = object.__new__(LabRequestHandler)
    handler.headers = {"Content-Length": "12"}
    handler.rfile = type("Reader", (), {"read": lambda self, length: b'{"ok": true}'})()

    result = handler.read_json_payload()

    assert result["success"] is True
    assert result["data"] == {"ok": True}
