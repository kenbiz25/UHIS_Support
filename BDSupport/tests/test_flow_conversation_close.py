from types import SimpleNamespace

from rag.flow import BotFlow

class MockWhatsApp:
    def __init__(self):
        self.sent = []
    def send_message(self, to, message=None, media=None):
        self.sent.append((to, message))

class MockComposer:
    def answer(self, query, language='en', session_id=None):
        return ("Please try restarting your device and clearing the app cache.", {"confidence": 0.8})

class MockMem:
    def __init__(self):
        self._messages = []
    def get_recent(self, session_id, limit=10):
        return list(self._messages[-limit:])
    def save_message(self, session_id, role, text):
        self._messages.append({"role": role, "text": text})


def test_close_and_ignore_followups(monkeypatch):
    # rag.flow already holds its own bound reference to the settings singleton (`from
    # config.settings import settings`), so replacing `config.settings.settings` wholesale
    # has no effect there — mutate attributes on the real object instead.
    from config.settings import settings
    monkeypatch.setattr(settings, 'ENABLE_CONVERSATION_MEMORY', True)
    monkeypatch.setattr(settings, 'ENABLE_FIRST_TOUCH_MENU', False)

    # Replace ConversationMemory with our MockMem
    mock_mem = MockMem()
    monkeypatch.setattr('core.memory.memory_service.ConversationMemory', lambda: mock_mem)

    whatsapp = MockWhatsApp()
    # BotFlow requires faiss and llm but we won't use them in this test
    bot = BotFlow(faiss_store=None, llm_service=None, whatsapp_service=whatsapp, composer=MockComposer())

    # Bypass language selection / contact intake - this test is about
    # close/ignore-followup behavior, not those earlier first-touch steps.
    from core.contacts import state as contact_state
    contact_state.set_language('+100', "en")
    contact_state.set_contact('+100', skipped=True)

    # 1) Initial user message -> normal reply
    out1, meta1 = bot.handle_message('+100', 'My phone is just loading when i open any page', session_id='+100')
    assert whatsapp.sent[-1][1].startswith('Please try restarting')

    # 2) User says 'Than you bye' -> closing reply
    out2, meta2 = bot.handle_message('+100', 'Than you bye', session_id='+100')
    assert meta2.get('conversation_closed') is True
    # Source uses a typographic apostrophe/dash ("You’re welcome — ..."); match on
    # substrings instead of startswith() to avoid brittleness on exact punctuation.
    assert "You" in whatsapp.sent[-1][1] and "welcome" in whatsapp.sent[-1][1]

    # 3) Later user sends 'Okay' -> should be ignored (no extra message sent)
    out3, meta3 = bot.handle_message('+100', 'Okay', session_id='+100')
    assert meta3.get('ignored') is True
    # Ensure only two messages were sent total
    assert len(whatsapp.sent) == 2