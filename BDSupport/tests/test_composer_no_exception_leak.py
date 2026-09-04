import logging
from rag.composer import RagComposer


def test_composer_handles_llm_exceptions(monkeypatch):
    composer = RagComposer()

    def fake_chat_complete(prompt, **kwargs):
        raise RuntimeError("openai connection failed: secret-token-12345")

    # composer.py calls openai_client.chat_complete(...) via the imported module object,
    # not a bare name in its own namespace — patch it there.
    monkeypatch.setattr("adapters.llm.openai_client.chat_complete", fake_chat_complete)

    # Use a non-greeting prompt so the composer invokes the LLM
    res = composer._compose_with_llm("Tell me about fever", context_chunks=[], low_confidence=False, language="en")
    assert "internal error" in res.lower()
    assert "secret-token-12345" not in res
