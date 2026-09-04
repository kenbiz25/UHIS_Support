# core/llm/llm_service.py
import logging
from config.settings import settings
from adapters.llm.openai_client import chat_complete

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self, model: str | None = None, temperature: float | None = None):
        self.model = model or settings.LLM_MODEL
        self.temperature = settings.LLM_TEMPERATURE if temperature is None else temperature

    def generate_response(self, user_message: str, faiss_docs: list, language: str | None = None):
        context = "\n".join([d["text"] for d in faiss_docs])
        lang_instruction = ""
        if language == 'bn':
            lang_instruction = (
                "\nNote: Reply fully in natural, simple Bangla (Bengali script) suitable for low-literacy users."
            )
        prompt = f"""
You are a helpful assistant.
User asked: "{user_message}"
Relevant knowledge:
{context}
Answer concisely and clearly.
{lang_instruction}
"""
        try:
            answer = chat_complete(
                prompt,
                model=self.model,
                temperature=self.temperature,
                max_tokens=settings.LLM_MAX_TOKENS,
                system_prompt="You are a helpful assistant. Respond naturally, clearly, and safely.",
                language=language,
            )
            logger.info(f"LLM generated response | len={len(answer)}")
            return answer
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return "Sorry, I couldn't generate an answer right now."
