from fastapi.testclient import TestClient
import app


def test_webhook_handler_exception_is_logged_not_leaked(monkeypatch):
    """A handle_message crash must never surface (or leak secrets) in the HTTP response.

    The webhook acks WhatsApp immediately and processes the message in a background
    task, so a downstream crash can only ever be logged — it can't turn into a 500
    the way it could before that was made non-blocking.
    """
    client = TestClient(app.app)

    class CrashingBot:
        def handle_message(self, user_id, message, session_id=None):
            raise RuntimeError("bot handler crashed: secret-token-567")

    app.app.state.bot = CrashingBot()

    payload = {
        "entry": [
            {"changes": [{"value": {"messages": [{"from": "+15551234567", "text": {"body": "hello"}}]}}]}
        ]
    }
    res = client.post("/whatsapp/webhook", json=payload)
    assert res.status_code == 200
    assert "secret-token-567" not in res.text
