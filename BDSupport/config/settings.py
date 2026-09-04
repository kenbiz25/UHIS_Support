# config/settings.py
import os
from dotenv import load_dotenv

# Load environment vars from .env
load_dotenv()

def _to_bool(val, default=True):
    if val is None:
        return default
    return str(val).strip().lower() in ("true", "1", "yes", "y")

def _to_float(val, default=0.55):
    try:
        return float(val)
    except (TypeError, ValueError):
        return default

def _to_int(val, default=3):
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _to_list(val):
    if not val:
        return []
    return [s.strip() for s in str(val).split(",") if s.strip()]


# ---------------------------------------------------------------------------
# Confidence thresholds
# ---------------------------------------------------------------------------
class ConfidenceThresholds:
    """
    RAG confidence thresholds:
      - HIGH (≥0.75): respond directly
      - MEDIUM (≥0.55): respond with caution
      - LOW (≥0.18): fallback with menu-first + AI interpretation
      - REJECT (<0.18): strong fallback
    """
    HIGH = _to_float(os.getenv("CONFIDENCE_HIGH"), 0.75)
    MEDIUM = _to_float(os.getenv("CONFIDENCE_MEDIUM"), 0.55)
    LOW = _to_float(os.getenv("CONFIDENCE_LOW"), 0.18)

    @classmethod
    def get_strategy(cls, confidence: float) -> str:
        if confidence >= cls.HIGH:
            return "direct"
        elif confidence >= cls.MEDIUM:
            return "cautious"
        elif confidence >= cls.LOW:
            return "low_confidence"
        else:
            return "reject"

    @classmethod
    def should_answer(cls, confidence: float) -> bool:
        return confidence >= cls.LOW


# ---------------------------------------------------------------------------
# Main Settings
# ---------------------------------------------------------------------------
class Settings:
    # ==================== WhatsApp / Meta ====================
    META_VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN", "")
    META_WHATSAPP_TOKEN = os.getenv("META_WHATSAPP_TOKEN", "")
    WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID", "")
    WHATSAPP_API_VERSION = os.getenv("WHATSAPP_API_VERSION", "v24.0")

    # ==================== Knowledge Base ====================
    KB_NAMESPACE = os.getenv("KB_NAMESPACE", "default")
    KB_DIR = os.getenv("KB_DIR", "KB")
    # Optional admin key to restrict KB reloads without restarting the app
    KB_RELOAD_KEY = os.getenv("KB_RELOAD_KEY", "")

    # Vector search top‑k
    TOP_K = _to_int(os.getenv("TOP_K"), 3)
    MAX_CONTEXT_CHUNKS = _to_int(os.getenv("MAX_CONTEXT_CHUNKS"), 3)

    # ==================== LLM Models ====================
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

    # Default LLM (Chat)
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
    LLM_MODEL = os.getenv("LLM_MODEL", OPENAI_MODEL)
    LLM_TEMPERATURE = _to_float(os.getenv("LLM_TEMPERATURE"), 0.3)
    LLM_MAX_TOKENS = _to_int(os.getenv("LLM_MAX_TOKENS"), 300)

    # ==================== Embeddings ====================
    EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")
    HF_EMBED_MODEL = os.getenv("HF_EMBED_MODEL", "all-MiniLM-L6-v2")

    # ==================== Vector Store ====================
    FAISS_INDEX_DIR = os.getenv("FAISS_INDEX_DIR", "core/faiss_index")
    FAISS_INDEX_FILE = os.getenv("FAISS_INDEX_FILE", "index.faiss")
    FAISS_DOCS_FILE = os.getenv("FAISS_DOCS_FILE", "documents.pkl")

    # Backwards compatibility
    PG_DSN = os.getenv("PG_DSN", "")
    VECTOR_TABLE = os.getenv("VECTOR_TABLE", "kb_chunks")

    # ==================== Confidence Logic ====================
    ANSWER_CONFIDENCE_THRESHOLD = _to_float(
        os.getenv("ANSWER_CONFIDENCE_THRESHOLD"),
        ConfidenceThresholds.MEDIUM
    )

    SAFEGUARD_ENABLE = _to_bool(os.getenv("SAFEGUARD_ENABLE"), True)

    # ==================== Support Contacts ====================
    SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL", "support@spice.com")
    SUPPORT_PHONE = os.getenv("SUPPORT_PHONE", "+1-555-SPICE")
    SUPPORT_DOCS_URL = os.getenv("SUPPORT_DOCS_URL", "https://docs.spice.com")

    FALLBACK_MESSAGE = os.getenv(
        "FALLBACK_MESSAGE",
        "I don't have quite enough information to answer that confidently. Please contact SPICE Support."
    )

    # ==================== NLP / STT / Language Support ====================
    ENABLE_STT = _to_bool(os.getenv("ENABLE_STT"), True)
    # Model used for WhatsApp voice-note transcription (supports Bangla natively)
    TRANSCRIBE_MODEL = os.getenv("TRANSCRIBE_MODEL", "gpt-4o-transcribe")

    # Bangla (Banglish) → English normalization, applied before RAG retrieval
    # since the KB is English-language.
    BANGLA_TRANSLATION = _to_bool(os.getenv("BANGLA_TRANSLATION"), True)
    BANGLA_NORMALIZE_AGGRESSIVE = _to_bool(os.getenv("BANGLA_NORMALIZE_AGGRESSIVE"), True)

    # ==================== Rate Limiting ====================
    MAX_CONCURRENT_REQUESTS = _to_int(os.getenv("MAX_CONCURRENT_REQUESTS"), 10)
    REQUEST_TIMEOUT = _to_int(os.getenv("REQUEST_TIMEOUT"), 30)

    # ==================== Logging ====================
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT = os.getenv("LOG_FORMAT", "%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    LOG_QUERIES = _to_bool(os.getenv("LOG_QUERIES"), True)
    LOG_RESPONSES = _to_bool(os.getenv("LOG_RESPONSES"), False)

    # ==================== Feature Flags ====================
    ENABLE_WEB_SEARCH = _to_bool(os.getenv("ENABLE_WEB_SEARCH"), False)
    ENABLE_CONVERSATION_MEMORY = _to_bool(os.getenv("ENABLE_CONVERSATION_MEMORY"), True)
    ENABLE_HUMAN_HANDOFF = _to_bool(os.getenv("ENABLE_HUMAN_HANDOFF"), True)
    # Show a structured short menu on the first interaction for users who have difficulty typing
    ENABLE_FIRST_TOUCH_MENU = _to_bool(os.getenv("ENABLE_FIRST_TOUCH_MENU"), True)

    # ==================== Ticketing ====================
    ENABLE_TICKETING = _to_bool(os.getenv("ENABLE_TICKETING"), True)
    # Path to the Excel file where tickets are saved - used only as a fallback
    # when the ticketing tool's API (below) is unreachable.
    TICKET_FILE_PATH = os.getenv("TICKET_FILE_PATH", "tickets.xlsx")

    # ==================== Ticketing tool integration ====================
    # Base URL of the main Flask ticketing tool, and the shared secret used to
    # call its /api/bd-support/* endpoints. Same key must be set on that app's
    # side as BD_SUPPORT_API_KEY - also used for its calls back into this
    # service's /internal/whatsapp/send endpoint.
    MAIN_APP_BASE_URL = os.getenv("MAIN_APP_BASE_URL", "")
    BD_SUPPORT_API_KEY = os.getenv("BD_SUPPORT_API_KEY", "")

    # ==================== Vector Memory / DB Backends ====================
    ENABLE_VECTOR_MEMORY = _to_bool(os.getenv("ENABLE_VECTOR_MEMORY"), True)
    ENABLE_ENCRYPTED_VECTOR_DB = _to_bool(os.getenv("ENABLE_ENCRYPTED_VECTOR_DB"), False)
    VECTOR_DB_PATH = os.getenv("VECTOR_DB_PATH", "core/memory/vectors.db")
    VECTOR_DB_ENCRYPTION_KEY = os.getenv("VECTOR_DB_ENCRYPTION_KEY", None)
    MEMORY_VECTOR_TOP_K = _to_int(os.getenv("MEMORY_VECTOR_TOP_K"), 3)

    # ==================== CORS / Network ====================
    # Comma-separated list of allowed origins; empty list disables CORS middleware (safer for production)
    ALLOWED_ORIGINS = _to_list(os.getenv("ALLOWED_ORIGINS", ""))

    # ==================== Validation ====================
    @classmethod
    def validate(cls) -> list[str]:
        issues = []
        if not cls.META_WHATSAPP_TOKEN:
            issues.append("❌ META_WHATSAPP_TOKEN is not set")
        if not cls.WHATSAPP_PHONE_ID:
            issues.append("❌ WHATSAPP_PHONE_ID is not set")
        if not cls.OPENAI_API_KEY:
            issues.append("❌ OPENAI_API_KEY is not set")
        if cls.ENABLE_TICKETING and (not cls.MAIN_APP_BASE_URL or not cls.BD_SUPPORT_API_KEY):
            issues.append("⚠️ MAIN_APP_BASE_URL/BD_SUPPORT_API_KEY not set — tickets will fall back to the local Excel file")

        if not os.path.exists(cls.KB_DIR):
            issues.append(f"⚠️ KB directory missing: {cls.KB_DIR}")

        faiss_path = os.path.join(cls.FAISS_INDEX_DIR, cls.FAISS_INDEX_FILE)
        if not os.path.exists(faiss_path):
            issues.append(f"⚠️ FAISS index missing: {faiss_path}")

        # Threshold sanity
        if ConfidenceThresholds.HIGH <= ConfidenceThresholds.MEDIUM:
            issues.append("⚠️ CONFIDENCE_HIGH should be > CONFIDENCE_MEDIUM")
        if ConfidenceThresholds.MEDIUM <= ConfidenceThresholds.LOW:
            issues.append("⚠️ CONFIDENCE_MEDIUM should be > CONFIDENCE_LOW")

        return issues


settings = Settings()
confidence_thresholds = ConfidenceThresholds

_validation_issues = settings.validate()
if _validation_issues:
    import logging
    logger = logging.getLogger(__name__)
    logger.warning("Configuration issues detected:")
    for issue in _validation_issues:
        logger.warning(f"  {issue}")