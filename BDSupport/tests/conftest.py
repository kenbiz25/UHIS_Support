import pytest


@pytest.fixture(autouse=True)
def _isolate_contact_state(tmp_path, monkeypatch):
    """Every test gets its own on-disk contact/language state directory, so
    contact-intake/language-selection state from one test (or a prior test
    run) never leaks into another - mirrors how tests already isolate
    ConversationMemory via a tmp sessions dir."""
    from core.contacts import state as contact_state

    def _tmp_state_dir():
        d = tmp_path / "contacts_state"
        d.mkdir(parents=True, exist_ok=True)
        return d

    monkeypatch.setattr(contact_state, "_state_dir", _tmp_state_dir)
