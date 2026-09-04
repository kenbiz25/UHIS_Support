# tests/test_flow_bangla_integration.py
import pytest
from rag.flow import BotFlow
from config.settings import settings


@pytest.fixture(autouse=True)
def _disable_conversation_memory(monkeypatch):
    # This test uses a fixed session id ('+100') against the real (non-tmp)
    # ConversationMemory directory, so accumulated real history from other test runs
    # could make the first-touch menu intercept unpredictably. Disable memory outright
    # since persistence isn't what's under test here (language detection is).
    monkeypatch.setattr(settings, 'ENABLE_CONVERSATION_MEMORY', False)


class DummyComposer:
    def __init__(self):
        self.calls = []
    def answer(self, query, language=None, **kwargs):
        # Explicit language parameter ensures it's present when passed as kwarg
        self.calls.append({'query': query, 'language': language})
        return ('OK', {'confidence': 1.0, 'citations': [], 'intent': 'greeting'})


def test_flow_passes_bangla_language_to_composer():
    composer = DummyComposer()
    class DummyWhatsapp:
        def send_message(self, user_id, message=None, media=None):
            return {'ok': True}
    bf = BotFlow(None, None, None, composer=composer)
    bf.whatsapp = DummyWhatsapp()
    bf.handle_message('+100', 'bangla: ki obostha')
    # composer.calls contains dicts with explicit 'language' key
    assert any(c.get('language') == 'bn' for c in composer.calls)
