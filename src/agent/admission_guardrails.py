"""
Admission Counselor guardrails and signal detection.

Covers:
  1. Response safety — blocks harmful/misleading content
  2. Language detection — detects which language the student is speaking
  3. Emotional signal detection — confusion, frustration, anxiety, parent mode
  4. Silence detection
  5. Lead readiness detection
"""

from __future__ import annotations
import re

# ---------------------------------------------------------------------------
# 1. Response safety — things the counselor must never say
# ---------------------------------------------------------------------------

_FORBIDDEN_PATTERNS = [
    r"\bguaranteed admission\b",
    r"\b100% placement\b",
    r"\bdonation se admission\b",
    r"\bmanagement quota\b.*\bguaranteed\b",
    r"\bdefinitely get\b",
    r"\bno problem getting\b",
    r"\bpackage of \d+\s*lakh\b.*\bguaranteed\b",
]
_COMPILED = [re.compile(p, re.IGNORECASE) for p in _FORBIDDEN_PATTERNS]

SAFE_REDIRECT = (
    "I want to give you accurate information. "
    "Let me share what the actual data shows for this college."
)


def check_response(response: str) -> tuple[bool, str]:
    for pattern in _COMPILED:
        if pattern.search(response):
            return False, SAFE_REDIRECT
    return True, response


# ---------------------------------------------------------------------------
# 2. Language detection from student utterance
# ---------------------------------------------------------------------------

_BENGALI_MARKERS = [
    "ache", "theke", "korbo", "kobe", "koto", "niye", "hobe", "lagbe",
    "janbo", "pabo", "bolun", "dekhi", "amake", "apnar", "chinta",
    "আমার", "আপনি", "করব", "হবে", "কোথায়",
]
_HINDI_MARKERS = [
    "mein", "hai", "hoga", "chahiye", "kitna", "kaise", "bata",
    "chahta", "chahti", "karega", "karegi", "percent", "lakh",
    "क्या", "है", "में", "कितना", "चाहिए",
]


def detect_language(text: str) -> str:
    """Returns 'bengali', 'hindi', or 'english'."""
    lower = text.lower()
    bn_score = sum(1 for w in _BENGALI_MARKERS if w in lower)
    hi_score = sum(1 for w in _HINDI_MARKERS if w in lower)
    if bn_score > hi_score and bn_score >= 1:
        return "bengali"
    if hi_score > bn_score and hi_score >= 1:
        return "hindi"
    return "english"


# ---------------------------------------------------------------------------
# 3. Emotional signal detection
# ---------------------------------------------------------------------------

_CONFUSION_MARKERS = [
    "don't understand", "confused", "not sure", "what does", "what is",
    "bujhte parchi na", "bujhlam na", "kি", "confused", "clear na",
    "samajh nahi", "kya matlab", "nahi samjha",
]

_ANXIETY_MARKERS = [
    "scared", "worried", "tension", "anxious", "nervous", "stress",
    "chinta", "tension hochhe", "dar lag", "nervous", "tension hai",
    "chance ache?", "pabo?", "hobe?", "milega?",
]

_PARENT_MARKERS = [
    "my son", "my daughter", "amar chele", "amar meye",
    "mere bete", "meri beti", "beta", "beti",
    "our child", "for my child",
]


def is_confused(text: str) -> bool:
    lower = text.lower()
    return any(m in lower for m in _CONFUSION_MARKERS)


def is_anxious(text: str) -> bool:
    lower = text.lower()
    return any(m in lower for m in _ANXIETY_MARKERS)


def is_parent(text: str) -> bool:
    lower = text.lower()
    return any(m in lower for m in _PARENT_MARKERS)


# ---------------------------------------------------------------------------
# 4. Silence detection
# ---------------------------------------------------------------------------

def is_silence_or_filler(text: str) -> bool:
    """Detect empty/filler responses — user went quiet or just said 'um'."""
    stripped = text.strip().lower()
    fillers = {"um", "uh", "hmm", "hm", "ah", "er", "", "..."}
    return stripped in fillers or len(stripped) < 3


# ---------------------------------------------------------------------------
# 5. Lead readiness detection
# ---------------------------------------------------------------------------

_INTENT_SIGNALS = [
    "apply karte chahta", "apply korbo", "admission nite chai",
    "how to apply", "registration kaise", "form fill",
    "interested in", "want to join", "join korte chai",
    "counseling date", "kobe apply", "deadline kobe",
]


def is_lead_ready(text: str) -> bool:
    """Student is showing intent to apply — good time to collect contact info."""
    lower = text.lower()
    return any(s in lower for s in _INTENT_SIGNALS)


# ---------------------------------------------------------------------------
# 6. Safety suffix for system prompt
# ---------------------------------------------------------------------------

def build_safety_suffix() -> str:
    return """

GUARDRAILS — never break these:
1. Never guarantee admission or placement outcomes.
2. Never promote management quota or donation-based admissions.
3. Never invent placement statistics — if unknown, say so honestly.
4. If student sounds confused, slow down and simplify immediately.
5. If student sounds anxious about chances, be honest but reassuring.
6. Never pressure the student to apply or share contact information.
7. If parent is asking, shift focus to safety, ROI, and institution credibility.
8. Vary your sentence structure. Never start two consecutive answers the same way.
"""
