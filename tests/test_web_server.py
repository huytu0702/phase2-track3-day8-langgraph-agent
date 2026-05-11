from langgraph_agent_lab.web_server import create_api_response, parse_json_body


def test_create_api_response_wraps_success_payload() -> None:
    status, headers, body = create_api_response({"ok": True})

    assert status == 200
    assert headers["Content-Type"] == "application/json; charset=utf-8"
    assert b'"success": true' in body


def test_parse_json_body_rejects_invalid_json() -> None:
    result = parse_json_body(b"not-json")

    assert result["success"] is False
    assert "Invalid JSON" in result["error"]
