from unittest.mock import MagicMock

import httpx
import openai

from src.rag.llm_client import create_json_completion

_MSGS = [{"role": "user", "content": "hi"}]


def _client_returning(response):
    client = MagicMock()
    client.chat.completions.create.return_value = response
    return client


def test_structured_true_passes_response_format():
    resp = MagicMock()
    client = _client_returning(resp)
    out = create_json_completion(client, "m", _MSGS, 30, structured=True)
    assert out is resp
    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs["response_format"] == {"type": "json_object"}


def test_structured_false_omits_response_format():
    resp = MagicMock()
    client = _client_returning(resp)
    create_json_completion(client, "m", _MSGS, 30, structured=False)
    kwargs = client.chat.completions.create.call_args.kwargs
    assert "response_format" not in kwargs


def test_retries_without_response_format_on_bad_request():
    resp_ok = MagicMock()
    req = httpx.Request("POST", "http://x")
    http_resp = httpx.Response(400, request=req)
    bad = openai.BadRequestError(
        "response_format unsupported", response=http_resp, body=None
    )

    client = MagicMock()
    client.chat.completions.create.side_effect = [bad, resp_ok]

    out = create_json_completion(client, "m", _MSGS, 30, structured=True)
    assert out is resp_ok
    assert client.chat.completions.create.call_count == 2
    # second (successful) call must NOT carry response_format
    second_kwargs = client.chat.completions.create.call_args_list[1].kwargs
    assert "response_format" not in second_kwargs


import src.rag.llm_client as llm_client


def _reset_clients():
    llm_client._clients.clear()


def test_json_and_prose_share_one_client_when_prose_lane_is_off(monkeypatch):
    _reset_clients()
    monkeypatch.setattr(llm_client.settings, "prose_provider", None)
    assert llm_client.get_client("prose") is llm_client.get_client("json")


def test_prose_lane_gets_its_own_client(monkeypatch):
    _reset_clients()
    monkeypatch.setattr(llm_client.settings, "prose_provider", "ollama")
    prose = llm_client.get_client("prose")
    json_lane = llm_client.get_client("json")
    assert prose is not json_lane
    assert str(prose.base_url).rstrip("/") == "http://localhost:11434/v1"


def test_clients_are_cached_per_provider(monkeypatch):
    _reset_clients()
    monkeypatch.setattr(llm_client.settings, "prose_provider", "ollama")
    assert llm_client.get_client("prose") is llm_client.get_client("prose")


def test_default_role_is_json(monkeypatch):
    _reset_clients()
    monkeypatch.setattr(llm_client.settings, "prose_provider", "ollama")
    assert llm_client.get_client() is llm_client.get_client("json")
