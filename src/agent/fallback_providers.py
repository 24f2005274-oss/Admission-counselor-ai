"""
Provider builders for STT, LLM, and TTS.

Primary providers:
  STT: Deepgram Nova-3 (best multilingual for Indic languages)
  LLM: Gemini 2.5 Flash via LiveKit inference (free on LiveKit tier)
  TTS: Sarvam bulbul:v3 (best Indic language quality)
"""

from __future__ import annotations

import os
import logging

from livekit.agents import stt, tts, llm, inference
from .sarvam_tts import SarvamTTS

logger = logging.getLogger("admission-counselor")


def build_stt(language: str = "multi") -> stt.STT:
    return inference.STT(model="deepgram/nova-3", language=language)


def build_llm() -> llm.LLM:
    return inference.LLM(model="google/gemini-2.5-flash")


def build_tts(language: str = "en") -> tts.TTS:
    return SarvamTTS(language=language, pace=0.95)
