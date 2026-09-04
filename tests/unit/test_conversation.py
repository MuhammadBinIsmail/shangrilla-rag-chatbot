from unittest.mock import MagicMock, patch

from app.retrieval.conversation import ask, reformulate_query


class FakeMessage:
    def __init__(self, role, content):
        self.role = role
        self.content = content


class FakeSessionRow:
    def __init__(self, session_id):
        self.session_id = session_id
        self.module = None


class FakeSessionStore:
    """No shared cross-session state possible here by construction -
    each session_id maps to its own isolated entry, same as the real
    DB-backed store has no way to conflate two sessions."""

    def __init__(self):
        self._sessions: dict[str, FakeSessionRow] = {}
        self._history: dict[str, list[FakeMessage]] = {}

    def get_or_create_session(self, session_id: str) -> FakeSessionRow:
        if session_id not in self._sessions:
            self._sessions[session_id] = FakeSessionRow(session_id)
            self._history[session_id] = []
        return self._sessions[session_id]

    def set_module(self, session_id: str, module: str) -> None:
        self._sessions[session_id].module = module

    def get_history(self, session_id: str) -> list[FakeMessage]:
        return list(self._history.get(session_id, []))

    def add_message(self, session_id: str, role: str, content: str) -> None:
        self._history.setdefault(session_id, []).append(FakeMessage(role, content))


# --- reformulate_query ---


def test_reformulate_skips_llm_call_when_no_history():
    llm = MagicMock()
    result = reformulate_query(llm, [], "What triggers the release check?")
    assert result == "What triggers the release check?"
    llm.generate.assert_not_called()


def test_reformulate_calls_llm_with_history_when_present():
    llm = MagicMock()
    llm.generate.return_value = "  What triggers the release check for CO-CE-001?  "
    history = [FakeMessage("user", "Tell me about CO-CE-001"), FakeMessage("assistant", "It's a BAdI.")]

    result = reformulate_query(llm, history, "What triggers the release check?")

    assert result == "What triggers the release check for CO-CE-001?"  # stripped
    llm.generate.assert_called_once()


# --- ask() orchestration ---


def test_ask_without_module_asks_for_one_and_does_not_retrieve():
    store = FakeSessionStore()
    with patch("app.retrieval.conversation.answer_query") as mock_answer_query:
        result = ask(store, MagicMock(), MagicMock(), MagicMock(), "session-1", "Hello")

        assert result.needs_module_selection is True
        mock_answer_query.assert_not_called()
        assert store.get_history("session-1") == []  # nothing persisted either


def test_ask_sets_module_on_first_message_and_persists_for_later_turns():
    store = FakeSessionStore()
    with patch("app.retrieval.conversation.answer_query") as mock_answer_query:
        mock_answer_query.return_value = MagicMock(text="answer", sources=[])

        ask(store, MagicMock(), MagicMock(), MagicMock(), "session-1", "q1", module="CO")
        ask(store, MagicMock(), MagicMock(), MagicMock(), "session-1", "q2")  # no module needed now

        session_row = store.get_or_create_session("session-1")
        assert session_row.module == "CO"
        assert len(mock_answer_query.call_args_list) == 2


def test_ask_persists_user_and_assistant_messages():
    store = FakeSessionStore()
    with patch("app.retrieval.conversation.answer_query") as mock_answer_query:
        mock_answer_query.return_value = MagicMock(text="the answer", sources=[])

        ask(store, MagicMock(), MagicMock(), MagicMock(), "session-1", "my question", module="CO")

        history = store.get_history("session-1")
        assert len(history) == 2
        assert history[0].role == "user" and history[0].content == "my question"
        assert history[1].role == "assistant" and history[1].content == "the answer"


def test_two_sessions_never_share_history_or_module():
    """The one requirement this milestone cannot get wrong, same
    spirit as module isolation in retrieval - two sessions must never
    see each other's state."""
    store = FakeSessionStore()

    with patch("app.retrieval.conversation.answer_query") as mock_answer_query:
        mock_answer_query.return_value = MagicMock(text="answer about CO-CE-001", sources=[])
        ask(store, MagicMock(), MagicMock(), MagicMock(), "session-A", "Tell me about CO-CE-001", module="CO")

        mock_answer_query.return_value = MagicMock(text="answer about FI-AA-024", sources=[])
        ask(store, MagicMock(), MagicMock(), MagicMock(), "session-B", "Tell me about FI-AA-024", module="FI")

    history_a = store.get_history("session-A")
    history_b = store.get_history("session-B")

    assert "CO-CE-001" in history_a[0].content
    assert "FI-AA-024" not in history_a[0].content
    assert "FI-AA-024" not in history_a[1].content

    assert "FI-AA-024" in history_b[0].content
    assert "CO-CE-001" not in history_b[0].content
    assert "CO-CE-001" not in history_b[1].content

    assert store.get_or_create_session("session-A").module == "CO"
    assert store.get_or_create_session("session-B").module == "FI"


def test_second_turn_reformulates_using_first_turns_history():
    store = FakeSessionStore()
    with patch("app.retrieval.conversation.answer_query") as mock_answer_query, patch(
        "app.retrieval.conversation.reformulate_query"
    ) as mock_reformulate:
        mock_answer_query.return_value = MagicMock(text="answer", sources=[])
        mock_reformulate.return_value = "reformulated question"

        ask(store, MagicMock(), MagicMock(), MagicMock(), "session-1", "first question", module="CO")
        ask(store, MagicMock(), MagicMock(), MagicMock(), "session-1", "follow-up question")

        # second call to reformulate_query must have received the
        # first turn's history, not an empty list
        second_call_history = mock_reformulate.call_args_list[1][0][1]
        assert len(second_call_history) == 2  # first turn's user + assistant messages
