# tests/test_bangla_detection.py
from rag.flow import BotFlow


def test_detect_bangla_explicit():
    bf = BotFlow(None, None, None)
    assert bf._detect_bangla('bangla: ki obostha') is True
    assert bf._detect_bangla('Please speak Bengali') is True


def test_detect_bangla_native_script():
    bf = BotFlow(None, None, None)
    # Native Bengali script should be auto-detected without any explicit request.
    assert bf._detect_bangla('আমার লগইন সমস্যা হচ্ছে') is True


def test_detect_bangla_romanized():
    bf = BotFlow(None, None, None)
    # Common Banglish (romanized Bangla) phrasing should also be auto-detected.
    assert bf._detect_bangla('amar login kore na, ki korbo?') is True


def test_detect_bangla_negative():
    bf = BotFlow(None, None, None)
    assert bf._detect_bangla('Hello, how are you?') is False
