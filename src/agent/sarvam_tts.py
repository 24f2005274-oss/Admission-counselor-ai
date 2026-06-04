"""
Sarvam AI TTS plugin for LiveKit Agents.

Uses the Sarvam streaming endpoint:
  POST https://api.sarvam.ai/text-to-speech/stream
  Returns MP3 chunks as they arrive — lower latency than the batch API.

Model: bulbul:v3
Voice: sumit (clear male) by default. Override via SARVAM_VOICE env var.
"""

from __future__ import annotations

import io
import os

import aiohttp
import pydub

from livekit.agents import tts, utils
from livekit.agents.types import APIConnectOptions, DEFAULT_API_CONNECT_OPTIONS

STREAM_URL = "https://api.sarvam.ai/text-to-speech/stream"
SAMPLE_RATE = 22050
NUM_CHANNELS = 1

_LANGUAGE_MAP: dict[str, str] = {
    "hi": "hi-IN", "hi-IN": "hi-IN",
    "bn": "bn-IN", "bn-IN": "bn-IN",
    "en": "en-IN", "en-IN": "en-IN",
}

# Clear professional male voices — override via SARVAM_VOICE env var
_DEFAULT_VOICE: dict[str, str] = {
    "hi-IN": "sumit",
    "bn-IN": "sumit",
    "en-IN": "sumit",
}


class SarvamTTS(tts.TTS):
    def __init__(
        self,
        *,
        api_key: str | None = None,
        language: str | None = None,
        speaker: str | None = None,
        pace: float = 1.0,
    ) -> None:
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False),
            sample_rate=SAMPLE_RATE,
            num_channels=NUM_CHANNELS,
        )
        self._api_key = api_key or os.environ.get("SARVAM_API_KEY", "")
        if not self._api_key:
            raise ValueError("SARVAM_API_KEY not set in .env.local")

        lang_env = language or os.environ.get("DEFAULT_LANGUAGE", "en")
        self._language = _LANGUAGE_MAP.get(lang_env, "en-IN")

        env_voice = os.environ.get("SARVAM_VOICE", "")
        self._speaker = speaker or env_voice or _DEFAULT_VOICE.get(self._language, "sumit")
        self._pace = pace

    def synthesize(
        self,
        text: str,
        *,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
    ) -> "SarvamChunkedStream":
        return SarvamChunkedStream(
            tts=self,
            input_text=text,
            conn_options=conn_options,
            api_key=self._api_key,
            language=self._language,
            speaker=self._speaker,
            pace=self._pace,
        )


class SarvamChunkedStream(tts.ChunkedStream):
    def __init__(self, *, tts, input_text, conn_options, api_key, language, speaker, pace):
        super().__init__(tts=tts, input_text=input_text, conn_options=conn_options)
        self._api_key = api_key
        self._language = language
        self._speaker = speaker
        self._pace = pace

    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        headers = {
            "api-subscription-key": self._api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "text": self._input_text,
            "target_language_code": self._language,
            "speaker": self._speaker,
            "model": "bulbul:v3",
            "pace": self._pace,
            "speech_sample_rate": SAMPLE_RATE,
            "output_audio_codec": "mp3",
            "enable_preprocessing": True,
        }

        output_emitter.initialize(
            request_id=utils.shortuuid(),
            sample_rate=SAMPLE_RATE,
            num_channels=NUM_CHANNELS,
            mime_type="audio/pcm",
        )

        async with aiohttp.ClientSession() as session:
            async with session.post(STREAM_URL, headers=headers, json=payload) as response:
                response.raise_for_status()

                mp3_chunks: list[bytes] = []
                async for chunk in response.content.iter_chunked(8192):
                    if chunk:
                        mp3_chunks.append(chunk)

        # Decode accumulated MP3 → raw PCM and push
        mp3_bytes = b"".join(mp3_chunks)
        pcm_bytes = _mp3_to_pcm(mp3_bytes, SAMPLE_RATE)
        output_emitter.push(pcm_bytes)
        output_emitter.flush()


def _mp3_to_pcm(mp3_bytes: bytes, target_sample_rate: int) -> bytes:
    """Decode MP3 bytes → 16-bit PCM at target sample rate."""
    audio = pydub.AudioSegment.from_file(io.BytesIO(mp3_bytes), format="mp3")
    audio = audio.set_frame_rate(target_sample_rate).set_channels(NUM_CHANNELS).set_sample_width(2)
    return audio.raw_data
