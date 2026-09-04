from fastapi.testclient import TestClient
from app import app

client = TestClient(app)


class MockBot:
    def __init__(self):
        self.calls = []
    def handle_message(self, user_id, message, session_id=None):
        self.calls.append((user_id, message))


def _media_payload(from_, media_id):
    return {
        "entry": [
            {"changes": [{"value": {"messages": [
                {"from": from_, "type": "audio", "audio": {"id": media_id}}
            ]}}]}
        ]
    }


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, content=b"", headers=None):
        self.status_code = status_code
        self._json = json_data or {}
        self.content = content
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx
            raise httpx.HTTPStatusError("error", request=None, response=self)

    def json(self):
        return self._json


def test_whatsapp_webhook_audio_transcribed_success(monkeypatch):
    mock = MockBot()
    app.state.bot = mock

    media_id = "media-123"

    def fake_get(self, url, headers=None, timeout=None):
        if url.endswith(media_id):
            return FakeResponse(200, json_data={"url": "https://cdn.example.com/audio.ogg", "mime_type": "audio/ogg"})
        return FakeResponse(200, content=b"FAKE-AUDIO-BYTES", headers={"content-type": "audio/ogg"})

    monkeypatch.setattr("httpx.Client.get", fake_get)
    monkeypatch.setattr(
        "adapters.llm.openai_client.whisper_transcribe",
        lambda audio_bytes, filename="voice.ogg": "This is a transcribed voice note",
    )

    r = client.post("/whatsapp/webhook", json=_media_payload("+254700000000", media_id))
    assert r.status_code == 200
    assert mock.calls == [("+254700000000", "This is a transcribed voice note")]


def test_whatsapp_webhook_audio_transcribe_failure_is_swallowed(monkeypatch):
    mock = MockBot()
    app.state.bot = mock

    media_id = "media-456"

    def fake_get(self, url, headers=None, timeout=None):
        if url.endswith(media_id):
            return FakeResponse(200, json_data={"url": "https://cdn.example.com/audio.ogg", "mime_type": "audio/ogg"})
        return FakeResponse(200, content=b"FAKE-AUDIO-BYTES", headers={"content-type": "audio/ogg"})

    def fake_transcribe(audio_bytes, filename="voice.ogg"):
        raise RuntimeError("transcription failed")

    monkeypatch.setattr("httpx.Client.get", fake_get)
    monkeypatch.setattr("adapters.llm.openai_client.whisper_transcribe", fake_transcribe)

    # Background processing errors are logged, not raised — the webhook still acks fast
    # and the bot is simply never called for this message.
    r = client.post("/whatsapp/webhook", json=_media_payload("+254700000001", media_id))
    assert r.status_code == 200
    assert mock.calls == []


def test_whatsapp_webhook_audio_media_lookup_failure_is_swallowed(monkeypatch):
    mock = MockBot()
    app.state.bot = mock

    media_id = "media-789"

    def fake_get(self, url, headers=None, timeout=None):
        return FakeResponse(400)

    monkeypatch.setattr("httpx.Client.get", fake_get)

    r = client.post("/whatsapp/webhook", json=_media_payload("+254700000002", media_id))
    assert r.status_code == 200
    assert mock.calls == []
