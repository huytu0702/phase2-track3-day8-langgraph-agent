import pytest

from langgraph_agent_lab.llm import build_openai_client


def test_build_openai_client_requires_api_key_when_enabled(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        build_openai_client(enabled=True)


def test_build_openai_client_can_be_disabled(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    assert build_openai_client(enabled=False) is None
