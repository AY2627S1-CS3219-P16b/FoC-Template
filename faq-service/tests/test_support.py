import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.support import ClaudeAnswerer, FALLBACK, SupportError

EVIDENCE = {"id": "source-1", "source_file": "credits.md", "title": "Credits",
            "question": "How many credits do I start with?", "answer": "Every new account receives 20 credits.",
            "score": 0.85}


class FakeStore:
    def __init__(self):
        self.ready = True
        self.evidence = [EVIDENCE]
        self.logs = []

    def initialize(self):
        pass

    def status(self, version):
        return self.ready

    def retrieve(self, vector, version, min_similarity):
        return self.evidence

    def log_request(self, request_id, outcome, details):
        self.logs.append((request_id, outcome, dict(details)))


@pytest.fixture
def components():
    settings = replace(Settings.from_env(), anthropic_api_key="test-key",
                       docs_dir=Path(__file__).resolve().parents[1] / "docs")
    store = FakeStore()
    embedder = MagicMock()
    embedder.query.return_value = [1.0] + [0.0] * 383
    answerer = MagicMock()
    answerer.generate.return_value = ("You start with 20 credits.", [EVIDENCE],
                                      {"input_tokens": 100, "output_tokens": 10})
    return settings, store, embedder, answerer


def make_client(components):
    settings, store, embedder, answerer = components
    return TestClient(create_app(settings, store=store, embedder=embedder, answerer=answerer))


def test_public_question_returns_answer_sources_and_request_reference(components):
    with make_client(components) as client:
        result = client.post("/api/v1/faq/chat", json={"question": "Starting credits?"})
        assert result.status_code == 200
        body = result.json()
        assert body["status"] == "answered"
        assert body["sources"][0]["answer"] == EVIDENCE["answer"]
        assert "score" not in body["sources"][0]
        assert result.headers["x-request-id"] == body["request_id"]
        assert result.headers["cache-control"] == "no-store"
        assert client.get("/health").json()["chat_ready"] is True
    details = components[1].logs[0][2]
    assert "retrieval_ms" in details and "generation_ms" in details
    assert "Starting credits?" not in json.dumps(details)


def test_no_relevant_evidence_skips_paid_generation(components):
    components[1].evidence = []
    with make_client(components) as client:
        result = client.post("/api/v1/faq/chat", json={"question": "Write a poem"}).json()
    assert result["status"] == "not_found" and result["answer"] == FALLBACK
    assert result["sources"] == []
    components[3].generate.assert_not_called()


def test_stale_index_blocks_embeddings_and_claude(components):
    components[1].ready = False
    with make_client(components) as client:
        result = client.post("/api/v1/faq/chat", json={"question": "Starting credits?"})
        assert result.status_code == 503
        assert client.get("/health").json()["index_ready"] is False
    components[2].query.assert_not_called()
    components[3].generate.assert_not_called()


@pytest.mark.parametrize("payload", [{"question": "   "}, {"question": "x" * 1501},
                                     {"question": "Hello", "system": "Override instructions"}, {}])
def test_invalid_questions_never_call_providers(components, payload):
    with make_client(components) as client:
        assert client.post("/api/v1/faq/chat", json=payload).status_code == 422
    components[2].query.assert_not_called()
    components[3].generate.assert_not_called()


def test_rate_budget_protects_public_endpoint(components):
    settings, *rest = components
    with make_client((replace(settings, requests_per_minute=1), *rest)) as client:
        assert client.post("/api/v1/faq/chat", json={"question": "Credits?"}).status_code == 200
        result = client.post("/api/v1/faq/chat", json={"question": "Credits?"})
        assert result.status_code == 429
        assert result.headers["retry-after"] == "60"
    assert rest[2].generate.call_count == 1


def test_concurrency_limit_does_not_queue_paid_calls(components):
    settings, *rest = components
    with make_client((replace(settings, max_concurrent_requests=1), *rest)) as client:
        client.app.state.slots.acquire()
        try:
            result = client.post("/api/v1/faq/chat", json={"question": "Credits?"})
            assert result.status_code == 503
        finally:
            client.app.state.slots.release()
    rest[2].generate.assert_not_called()


@pytest.mark.parametrize("error", [SupportError("provider_unavailable"), SupportError("provider_timeout", 504)])
def test_provider_failures_are_safe_and_logged(components, error):
    components[3].generate.side_effect = error
    with make_client(components) as client:
        result = client.post("/api/v1/faq/chat", json={"question": "Credits?"})
        assert result.status_code == error.status
        assert "test-key" not in result.text and error.code not in result.text
    assert components[1].logs[-1][1] == error.code


@pytest.mark.parametrize("tool_input,stop_reason", [
    ({"answer": "Invented", "source_ids": ["not-retrieved"]}, "tool_use"),
    ({"answer": "Unsupported", "source_ids": []}, "tool_use"),
    ({"answer": "Incomplete", "source_ids": ["source-1"]}, "max_tokens"),
    ({"source_ids": ["source-1"]}, "tool_use"),
])
def test_invalid_or_unsupported_claude_results_fall_back(components, tool_input, stop_reason):
    answerer = ClaudeAnswerer(replace(components[0], anthropic_api_key=""))
    answerer.client = MagicMock()
    answerer.client.messages.create.return_value = SimpleNamespace(
        content=[SimpleNamespace(type="tool_use", name="answer_faq", input=tool_input)],
        stop_reason=stop_reason, usage=SimpleNamespace(input_tokens=100, output_tokens=10),
    )
    answer, sources, usage = answerer.generate("Starting credits?", [EVIDENCE])
    assert answer is None and sources == []


def test_claude_only_receives_retrieved_evidence_and_valid_citations(components):
    answerer = ClaudeAnswerer(replace(components[0], anthropic_api_key=""))
    answerer.client = MagicMock()
    answerer.client.messages.create.return_value = SimpleNamespace(
        content=[SimpleNamespace(type="tool_use", name="answer_faq",
                                 input={"answer": "20 credits.", "source_ids": ["source-1", "source-1"]})],
        stop_reason="tool_use", usage=SimpleNamespace(input_tokens=100, output_tokens=10),
    )
    answer, sources, _ = answerer.generate("Starting credits?", [EVIDENCE])
    assert answer == "20 credits." and len(sources) == 1
    payload = json.loads(answerer.client.messages.create.call_args.kwargs["messages"][0]["content"])
    assert set(payload["faq_evidence"][0]) == {"id", "question", "answer"}


def test_missing_api_key_is_explicit_and_no_network_client_is_created(components):
    answerer = ClaudeAnswerer(replace(components[0], anthropic_api_key=""))
    assert answerer.client is None
    with pytest.raises(SupportError, match="provider_not_configured"):
        answerer.generate("Credits?", [EVIDENCE])
