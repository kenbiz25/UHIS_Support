import os
import json
from rag.flow import BotFlow


class DummyFaiss:
    dim = 1536
    def search(self, embedding, top_k=5):
        return []


class DummyLLM:
    def generate_response(self, query, docs, language='en'):
        return "Fallback answer"


class DummyWhatsApp:
    def __init__(self):
        self.sent = []

    def send_message(self, user_id, message=None):
        self.sent.append((user_id, message))


class SpyComposer:
    def answer(self, query, language=None, session_id=None):
        return "Composer reply", {"confidence": 0.9, "citations": []}


def _reset_state(user_id):
    """Clear per-phone sidecar state (intake/contact/ticket) so a leftover
    file from another test using the same fake phone number can't leak into
    this one - conversation memory is separately redirected to tmp_path per
    test, but these live in their own fixed directories."""
    from core.intake import state as intake_state
    from core.tickets import state as ticket_state
    from core.tickets import csat_state
    intake_state.clear(user_id)
    ticket_state.clear_state(user_id)
    csat_state.clear(user_id)


def test_menu_shown_on_first_interaction(tmp_path, monkeypatch):
    from core.memory import memory_service

    orig_init = memory_service.ConversationMemory.__init__

    def fake_init(self, base_dir=None):
        return orig_init(self, base_dir=str(tmp_path / "sessions"))

    monkeypatch.setattr(memory_service.ConversationMemory, "__init__", fake_init)

    faiss = DummyFaiss()
    llm = DummyLLM()
    whatsapp = DummyWhatsApp()
    composer = SpyComposer()

    flow = BotFlow(faiss, llm, whatsapp, composer=composer)
    user_id = "+123"
    session_id = "sess-menu-1"
    _reset_state(user_id)

    # Bypass language selection / contact intake - this test is about the
    # first-touch menu specifically, not those earlier first-touch steps.
    from core.contacts import state as contact_state
    contact_state.set_language(user_id, "en")
    contact_state.set_contact(user_id, skipped=True)

    out, meta = flow.handle_message(user_id, "Hello", session_id=session_id)

    # Should have returned the menu and meta indicating it
    assert meta.get('menu_shown') is True
    assert out is not None
    assert 'Account & Access' in out
    assert 'Add/Update SK, SS, CC or Location Info' in out

    # Session file should include the assistant menu and a system marker
    path = os.path.join(str(tmp_path / "sessions"), f"{session_id}.jsonl")
    assert os.path.exists(path)
    with open(path, 'r', encoding='utf-8') as f:
        lines = [json.loads(l) for l in f if l.strip()]
    roles = [l['role'] for l in lines]
    assert 'assistant' in roles
    assert 'system' in roles

    _reset_state(user_id)


def test_menu_selection_starts_structured_intake(tmp_path, monkeypatch):
    """Selecting a structured-intake category (1-4, 7) should start the
    field-by-field Q&A directly - no RAG, no "describe your problem" free
    text handed to the composer."""
    from core.memory import memory_service

    orig_init = memory_service.ConversationMemory.__init__

    def fake_init(self, base_dir=None):
        return orig_init(self, base_dir=str(tmp_path / "sessions"))

    monkeypatch.setattr(memory_service.ConversationMemory, "__init__", fake_init)

    faiss = DummyFaiss()
    llm = DummyLLM()
    whatsapp = DummyWhatsApp()
    composer = SpyComposer()

    flow = BotFlow(faiss, llm, whatsapp, composer=composer)
    user_id = "+123"
    session_id = "sess-menu-2"
    _reset_state(user_id)

    from core.contacts import state as contact_state
    contact_state.set_language(user_id, "en")
    contact_state.set_contact(user_id, skipped=True)

    # Simulate the menu already having been shown.
    from core.memory.memory_service import ConversationMemory
    mem = ConversationMemory()
    mem.save_message(session_id, "assistant", "menu text")
    mem.save_message(session_id, "system", "menu_shown")

    # User selects '1' - Account & Access.
    out, meta = flow.handle_message(user_id, "1", session_id=session_id)

    assert meta.get('menu_selected') == '1'
    assert 'phone number' in out.lower() or 'mhealth' in out.lower()

    from core.intake import state as intake_state
    state = intake_state.get(user_id)
    assert state is not None
    assert state.get("category_id") == "1"

    # Session should have the assistant prompt and menu_consumed marker.
    path = os.path.join(str(tmp_path / "sessions"), f"{session_id}.jsonl")
    with open(path, 'r', encoding='utf-8') as f:
        lines = [json.loads(l) for l in f if l.strip()]
    texts = [l['text'] for l in lines]
    assert any('menu_consumed' in t for t in texts)

    _reset_state(user_id)


def test_structured_intake_creates_ticket_directly(tmp_path, monkeypatch):
    """Completing the Account & Access Q&A should create a ticket
    immediately - no confidence threshold, no yes/no confirmation."""
    from core.memory import memory_service

    orig_init = memory_service.ConversationMemory.__init__

    def fake_init(self, base_dir=None):
        return orig_init(self, base_dir=str(tmp_path / "sessions"))

    monkeypatch.setattr(memory_service.ConversationMemory, "__init__", fake_init)

    created = {}

    def fake_create_ticket(phone, issue, conversation_summary, name="", division="", status="Open", issue_type=""):
        created["phone"] = phone
        created["issue"] = issue
        created["issue_type"] = issue_type
        created["status"] = status
        return 42, "SL-0042"

    import core.tickets.ticket_manager as ticket_manager
    monkeypatch.setattr(ticket_manager, "create_ticket", fake_create_ticket)

    faiss = DummyFaiss()
    llm = DummyLLM()
    whatsapp = DummyWhatsApp()
    composer = SpyComposer()

    flow = BotFlow(faiss, llm, whatsapp, composer=composer)
    user_id = "+123"
    session_id = "sess-menu-3"
    _reset_state(user_id)

    from core.contacts import state as contact_state
    contact_state.set_language(user_id, "en")
    contact_state.set_contact(user_id, skipped=True)

    from core.memory.memory_service import ConversationMemory
    mem = ConversationMemory()
    mem.save_message(session_id, "assistant", "menu text")
    mem.save_message(session_id, "system", "menu_shown")

    # Select category 1, then answer both fields.
    flow.handle_message(user_id, "1", session_id=session_id)
    flow.handle_message(user_id, "01313053555", session_id=session_id)
    out, meta = flow.handle_message(user_id, "account is locked", session_id=session_id)

    assert meta.get("ticket_created") is True
    assert created.get("issue_type") == "Account & Access"
    assert "01313053555" in created.get("issue", "")
    assert "account is locked" in created.get("issue", "")
    assert "SL-0042" in out

    from core.intake import state as intake_state
    assert intake_state.get(user_id) is None  # cleared once complete

    _reset_state(user_id)
