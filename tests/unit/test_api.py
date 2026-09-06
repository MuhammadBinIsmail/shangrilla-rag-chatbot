from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.api.dependencies import get_db, get_embedder, get_llm, get_session_store
from app.api.main import app
from tests.unit.test_conversation import FakeSessionStore


def _make_client(fake_store: FakeSessionStore) -> TestClient:
    app.dependency_overrides[get_db] = lambda: MagicMock()
    app.dependency_overrides[get_session_store] = lambda: fake_store
    app.dependency_overrides[get_embedder] = lambda: MagicMock()
    app.dependency_overrides[get_llm] = lambda: MagicMock()
    client = TestClient(app)
    return client


def teardown_function():
    app.dependency_overrides.clear()


def test_health_endpoint():
    client = _make_client(FakeSessionStore())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_modules_endpoint_lists_all_seven():
    client = _make_client(FakeSessionStore())
    response = client.get("/modules")
    assert response.status_code == 200
    assert set(response.json()) == {"CO", "FI", "MM", "PP", "QM", "TM", "WM"}


def test_chat_rejects_unknown_module():
    client = _make_client(FakeSessionStore())
    response = client.post(
        "/chat", json={"session_id": "s1", "message": "hi", "module": "NOTREAL"}
    )
    assert response.status_code == 400


def test_chat_returns_answer_and_sources():
    with patch("app.retrieval.conversation.answer_query") as mock_answer_query:
        mock_answer_query.return_value = MagicMock(
            text="the answer",
            sources=[
                MagicMock(
                    wricef_id="CO-CE-001",
                    doc_type="TSD",
                    source_filename="x.pdf",
                    section_title="1. Purpose",
                    distance=0.2,
                )
            ],
        )
        client = _make_client(FakeSessionStore())
        response = client.post(
            "/chat", json={"session_id": "s1", "message": "hi", "module": "CO"}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["text"] == "the answer"
        assert body["sources"][0]["wricef_id"] == "CO-CE-001"
        assert body["needs_module_selection"] is False


def test_chat_without_module_asks_for_one():
    client = _make_client(FakeSessionStore())
    response = client.post("/chat", json={"session_id": "s1", "message": "hi"})

    assert response.status_code == 200
    assert response.json()["needs_module_selection"] is True


def test_history_endpoint_returns_persisted_messages():
    with patch("app.retrieval.conversation.answer_query") as mock_answer_query:
        mock_answer_query.return_value = MagicMock(text="an answer", sources=[])
        store = FakeSessionStore()
        client = _make_client(store)

        client.post("/chat", json={"session_id": "s1", "message": "my question", "module": "CO"})
        response = client.get("/sessions/s1/history")

        assert response.status_code == 200
        history = response.json()
        assert len(history) == 2
        assert history[0] == {"role": "user", "content": "my question"}
        assert history[1] == {"role": "assistant", "content": "an answer"}


def test_two_sessions_isolated_through_the_api():
    """Same critical guarantee as test_conversation.py, now proven
    through the actual HTTP layer, not just the underlying function."""
    with patch("app.retrieval.conversation.answer_query") as mock_answer_query:
        store = FakeSessionStore()
        client = _make_client(store)

        mock_answer_query.return_value = MagicMock(text="answer A", sources=[])
        client.post("/chat", json={"session_id": "session-A", "message": "about CO-CE-001", "module": "CO"})

        mock_answer_query.return_value = MagicMock(text="answer B", sources=[])
        client.post("/chat", json={"session_id": "session-B", "message": "about FI-AA-024", "module": "FI"})

        history_a = client.get("/sessions/session-A/history").json()
        history_b = client.get("/sessions/session-B/history").json()

        assert "CO-CE-001" in history_a[0]["content"]
        assert "FI-AA-024" not in str(history_a)
        assert "FI-AA-024" in history_b[0]["content"]
        assert "CO-CE-001" not in str(history_b)
