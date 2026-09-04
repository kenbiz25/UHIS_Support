import pytest
from rag.flow import BotFlow
from config.settings import settings


@pytest.fixture(autouse=True)
def _disable_conversation_memory(monkeypatch):
    # These tests use fixed session ids against the real (non-tmp) ConversationMemory
    # directory. With memory on, the first-touch menu and the "don't repeat the
    # clarify question" history check both key off accumulated real history, making
    # results depend on what earlier test runs happened to leave on disk. None of
    # that is what's under test here (composer/formatting behavior), so turn memory
    # off entirely rather than fighting each history-dependent branch individually.
    monkeypatch.setattr(settings, 'ENABLE_CONVERSATION_MEMORY', False)


class DummyWhatsApp:
    def __init__(self):
        self.sent = []
    def send_message(self, user_id, message):
        self.sent.append((user_id, message))

class DummyComposer:
    def __init__(self, answer_text, meta):
        self._ans = answer_text
        self._meta = meta
    def answer(self, query, language=None, session_id=None):
        return self._ans, self._meta


def test_botflow_high_confidence():
    wa = DummyWhatsApp()
    composer = DummyComposer("All good. Follow steps.", {"confidence": 0.9, "citations": []})
    bf = BotFlow(None, None, wa, composer=composer)
    bf.handle_message("user-1", "How to reset password?")
    assert wa.sent == [("user-1", "All good. Follow steps.")]


def test_botflow_low_confidence_appends_fallback():
    wa = DummyWhatsApp()
    composer = DummyComposer("I think this might work, not certain.", {"confidence": 0.1, "citations": []})
    bf = BotFlow(None, None, wa, composer=composer)
    bf.handle_message("user-2", "How do I change settings?")
    # fallback note from settings should be included
    assert any("I don't have quite enough information to answer" in m or "FALLBACK_MESSAGE" in m for _, m in wa.sent)


def test_botflow_low_confidence_asks_for_clarity():
    wa = DummyWhatsApp()
    composer = DummyComposer("I think this might work, not certain.", {"confidence": 0.1, "citations": []})
    bf = BotFlow(None, None, wa, composer=composer)
    bf.handle_message("user-3", "How do I change settings?")
    assert any("tell me a bit more" in m.lower() or "help you faster" in m.lower() for _, m in wa.sent)
