from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

class MockBot:
    def __init__(self):
        self.calls = []
    def handle_message(self, user_id, message, session_id=None):
        self.calls.append((user_id, message))


def test_whatsapp_webhook_json():
    mock = MockBot()
    app.state.bot = mock
    payload = {
        "entry": [
            {"changes": [{"value": {"messages": [{"from": "+254700000000", "text": {"body": "Hello JSON"}}]}}]}
        ]
    }
    r = client.post("/whatsapp/webhook", json=payload)
    assert r.status_code == 200
    assert mock.calls == [("+254700000000", "Hello JSON")]
