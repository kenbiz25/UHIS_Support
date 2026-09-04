# tests/test_composer_bangla_and_intent.py
from adapters.llm import openai_client
from rag.composer import RagComposer

class DummyChat:
    def __init__(self):
        self.calls = []
    def __call__(self, prompt, *, model=None, temperature=None, max_tokens=None, system_prompt=None, language=None):
        self.calls.append({'prompt': prompt, 'model': model, 'language': language})
        # return a deterministic short answer
        return 'Short answer.'


def test_compose_requests_full_bangla_reply(monkeypatch):
    dummy = DummyChat()
    monkeypatch.setattr(openai_client, 'chat_complete', dummy)
    rc = RagComposer(llm_model='gpt-test')
    rc._compose_with_llm('Ki obostha?', [], low_confidence=False, language='bn')
    # Ensure the prompt carries the Bangla instruction and the language is forwarded
    # to chat_complete so it's enforced at the system-prompt layer.
    assert any('Bangla' in c['prompt'] for c in dummy.calls)
    assert any(c['language'] == 'bn' for c in dummy.calls)


def test_answer_returns_intent(monkeypatch):
    monkeypatch.setattr(openai_client, 'chat_complete', lambda *args, **kwargs: "Ok")
    rc = RagComposer()
    ans, meta = rc.answer('Hello there')
    assert meta.get('intent') == 'greeting'
