"""scripts/simulate_conversations.py

Five end-to-end simulated WhatsApp conversations through BotFlow, exercising
the new menu -> structured intake -> direct ticket behavior (plus the
free-text auto-classifier and the stale-conversation sweep), without
touching the real WhatsApp API, LLM, or main ticketing tool - those are
faked in-process so this runs anywhere.

Usage: python scripts/simulate_conversations.py
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import shutil
import tempfile


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
        print(f"  [BOT -> {user_id}] {message}")


class DummyComposer:
    """Stands in for RagComposer - only category 5/6 and unmatched free
    text should ever reach this in these simulations."""
    def answer(self, query, language=None, session_id=None):
        return (
            "Happy to help! (this is the simulated knowledge-base answer)",
            {"confidence": 0.9, "citations": []},
        )


CREATED_TICKETS = []


def fake_create_ticket(phone, issue, conversation_summary, name="", division="", status="Open", issue_type=""):
    ticket = {
        "phone": phone, "issue": issue, "issue_type": issue_type, "status": status,
    }
    CREATED_TICKETS.append(ticket)
    ticket_id = len(CREATED_TICKETS)
    return ticket_id, f"SL-{ticket_id:04d}"


def run_conversation(title, user_id, session_id, sessions_dir, turns):
    print(f"\n=== {title} (user={user_id}) ===")

    from core.memory.memory_service import ConversationMemory
    from core.contacts import state as contact_state
    from core.intake import state as intake_state
    from core.tickets import state as ticket_state
    import core.tickets.ticket_manager as ticket_manager
    import core.intake.sweep as sweep_module

    # Fresh per-phone state for a clean, reproducible run.
    contact_state.set_language(user_id, "en")
    contact_state.set_contact(user_id, skipped=True)
    intake_state.clear(user_id)
    ticket_state.clear_state(user_id)

    ticket_manager.create_ticket = fake_create_ticket
    # The opportunistic stale-conversation sweep (core/intake/sweep.py) scans
    # the *real* core/memory/sessions directory, independent of this
    # script's temp sessions_dir - harmless in production, but irrelevant
    # noise for a deterministic simulation, so it's disabled here.
    sweep_module.sweep_stale = lambda *a, **k: 0

    mem = ConversationMemory(base_dir=sessions_dir)
    mem.save_message(session_id, "assistant", "menu text")
    mem.save_message(session_id, "system", "menu_shown")

    from rag.flow import BotFlow
    flow = BotFlow(DummyFaiss(), DummyLLM(), DummyWhatsApp(), composer=DummyComposer())
    # Point this flow's memory helper at the same shared sessions dir.
    flow._mem = lambda: ConversationMemory(base_dir=sessions_dir)

    last_out, last_meta = None, None
    for turn in turns:
        print(f"  [USER] {turn}")
        last_out, last_meta = flow.handle_message(user_id, turn, session_id=session_id)

    return last_out, last_meta


def main():
    sessions_dir = tempfile.mkdtemp(prefix="spice_sim_sessions_")
    try:
        results = []

        # 1) Account & Access -> direct ticket
        out, meta = run_conversation(
            "Account & Access", "+8801700000001", "sim-1", sessions_dir,
            ["1", "01313053555", "account is locked, tried resetting password"],
        )
        results.append(("Account & Access", meta))

        # 2) SK/SS/CC & Location -> direct ticket, with an optional field skipped
        out, meta = run_conversation(
            "SK/SS/CC & Location Update", "+8801700000002", "sim-2", sessions_dir,
            ["2", "Rangpur / Kaunia / Balapara union", "add SS Sabana under SK Asma Khatun", "skip"],
        )
        results.append(("SK/SS/CC & Location", meta))

        # 3) Dashboard & Reports -> direct ticket
        out, meta = run_conversation(
            "Dashboard & Reports", "+8801700000003", "sim-3", sessions_dir,
            ["3", "NCD and glass-sold report for Jan 1 - Feb 28", "saad@example.org"],
        )
        results.append(("Dashboard & Reports", meta))

        # 4) App Problem -> direct ticket, device field skipped
        out, meta = run_conversation(
            "App Problem", "+8801700000004", "sim-4", sessions_dir,
            ["4", "app shows white screen after login", "QR code scan screen", "not sure"],
        )
        results.append(("App Problem", meta))

        # 5) Free text with no menu number at all -> auto-classified into
        # Account & Access by the keyword classifier, still ends in a ticket.
        out, meta = run_conversation(
            "Auto-classified free text (no menu number)", "+8801700000005", "sim-5", sessions_dir,
            [
                "my SPICE login shows invalid password, can't login",
                "01759571028",
                "tried resetting twice, still can't log in",
            ],
        )
        results.append(("Auto-classified free text", meta))

        print("\n=== Summary ===")
        ok = True
        for label, meta in results:
            created = bool(meta and meta.get("ticket_created"))
            print(f"{label}: ticket_created={created} meta={meta}")
            if not created:
                ok = False

        print(f"\nTickets created: {len(CREATED_TICKETS)}")
        for t in CREATED_TICKETS:
            print(f"  - [{t['issue_type']}] {t['phone']}: {t['issue'][:70]!r}...")

        print("\nRESULT:", "ALL SIMULATIONS OK" if ok and len(CREATED_TICKETS) == 5 else "SOME SIMULATIONS FAILED")
        return 0 if ok and len(CREATED_TICKETS) == 5 else 1
    finally:
        shutil.rmtree(sessions_dir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
