"""
Admission Counselor Voice Agent — LiveKit entry point.

Pipeline: Deepgram Nova-3 STT → Gemini 2.5 Flash LLM → Sarvam TTS (neel, pace=1.15)
"""

from __future__ import annotations

import os
import re
import logging

from dotenv import load_dotenv

from livekit import agents
from livekit.agents import (
    Agent,
    AgentSession,
    AgentServer,
    JobContext,
    room_io,
    TurnHandlingOptions,
)
from livekit.plugins import silero, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

from src.agent.fallback_providers import build_stt, build_llm, build_tts
from src.agent.conversation_engine import build_system_prompt, get_silence_response
from src.agent.admission_guardrails import (
    detect_language,
    is_confused,
    is_anxious,
    is_parent,
    is_silence_or_filler,
    is_lead_ready,
)

load_dotenv(".env.local")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("admission-counselor")

AGENT_NAME = "admission-counselor"

# Goodbye messages — vary so it never sounds scripted
_GOODBYE_MESSAGES = [
    "Thank you so much for reaching out. Wishing you all the very best for your admissions. Feel free to call us anytime!",
    "It was wonderful speaking with you. Best of luck with your college journey. We are always here to help!",
    "Thank you for contacting us. We hope we could help. All the best for your future ahead!",
    "Great speaking with you today. Wishing you success in your admissions. Do reach out if you need anything!",
]

import random


# ---------------------------------------------------------------------------
# Admission Counselor Agent
# ---------------------------------------------------------------------------

class AdmissionCounselorAgent(Agent):
    def __init__(self, session_ref: AgentSession) -> None:
        self._language = "english"
        self._student_profile: dict = {}
        self._turn_count = 0
        self._language_asked = False
        self._session = session_ref

        super().__init__(
            instructions=build_system_prompt(language=self._language),
            # Proactive follow-up: if user is silent for 8 seconds, speak up
            min_endpointing_delay=0.4,
        )

    async def on_enter(self) -> None:
        logger.info("Session started")

    async def on_user_turn_exceeded(self, ev) -> None:
        """Fires when the user hasn't spoken within the endpointing window — ask a follow-up."""
        await self._session.generate_reply(
            instructions=(
                "The student has gone quiet. "
                "Ask a short, natural follow-up question to continue the conversation. "
                "Pick ONE from: their rank, their course interest, whether they need hostel, "
                "or their preferred city. Keep it to one sentence only."
            )
        )

    async def on_user_turn_completed(self, turn_ctx, new_message) -> None:
        user_text: str = new_message.text_content or ""
        self._turn_count += 1

        # -- Silence / filler: ask a follow-up --
        if is_silence_or_filler(user_text):
            turn_ctx.add_message(
                role="system",
                content=(
                    f"The student went quiet. Say: '{get_silence_response()}' "
                    "then ask one simple follow-up question."
                ),
            )
            await super().on_user_turn_completed(turn_ctx, new_message)
            return

        # -- Language detection: only on first 2 turns, don't keep re-asking --
        if self._turn_count <= 2:
            detected = detect_language(user_text)
            if detected != self._language:
                self._language = detected
                logger.info("Language: %s", self._language)
                await self.update_instructions(
                    build_system_prompt(
                        language=self._language,
                        student_profile=self._student_profile,
                    )
                )
            # Tell LLM: language chosen, do NOT ask again
            if self._language_asked:
                turn_ctx.add_message(
                    role="system",
                    content=(
                        f"Language is now confirmed as {self._language}. "
                        "Do NOT ask about language preference again. Move to the next step."
                    ),
                )
            self._language_asked = True

        # -- Emotional signal injection --
        if is_confused(user_text):
            turn_ctx.add_message(
                role="system",
                content=(
                    "Student sounds confused. Give ONE piece of info only. "
                    "Ask one simple clarifying question. Be brief."
                ),
            )
        elif is_anxious(user_text):
            turn_ctx.add_message(
                role="system",
                content=(
                    "Student is anxious about chances. "
                    "Acknowledge first, then give honest + reassuring picture. No overpromising."
                ),
            )
        elif is_parent(user_text):
            turn_ctx.add_message(
                role="system",
                content=(
                    "Parent is speaking. Focus on: safety, placements, faculty, hostel, ROI. "
                    "Tone: trustworthy and professional."
                ),
            )

        # -- Lead capture --
        if is_lead_ready(user_text) and self._turn_count > 3:
            turn_ctx.add_message(
                role="system",
                content=(
                    "Student wants to apply. Naturally ask for name + phone number "
                    "to send details. One ask, not a form."
                ),
            )

        # -- Extract profile facts --
        self._update_profile(user_text)

        # -- Refresh prompt every 5 turns with updated profile --
        if self._turn_count % 5 == 0:
            await self.update_instructions(
                build_system_prompt(
                    language=self._language,
                    student_profile=self._student_profile,
                )
            )

        await super().on_user_turn_completed(turn_ctx, new_message)

    def _update_profile(self, text: str) -> None:
        lower = text.lower()
        pct = re.search(r"(\d{2,3})\s*%", text)
        if pct:
            self._student_profile["percentage"] = pct.group(1) + "%"
        rank = re.search(r"rank\s*[:\-]?\s*(\d+)", lower)
        if rank:
            self._student_profile["rank"] = rank.group(1)
        for course in ["cse", "ece", "civil", "mechanical", "bca", "bsc", "bba", "ai", "ml", "data science"]:
            if course in lower:
                self._student_profile["interested_course"] = course.upper()
                break
        if "hostel" in lower:
            self._student_profile["hostel_required"] = "yes"
        budget = re.search(r"(\d+)\s*(lakh|lac|k)", lower)
        if budget:
            self._student_profile["budget"] = budget.group(1) + " " + budget.group(2)


# ---------------------------------------------------------------------------
# LiveKit server wiring
# ---------------------------------------------------------------------------

server = AgentServer()


@server.rtc_session(agent_name=AGENT_NAME)
async def counselor_session(ctx: JobContext):
    await ctx.connect()

    lang = os.getenv("DEFAULT_LANGUAGE", "en")

    session = AgentSession(
        stt=build_stt(language="multi"),
        llm=build_llm(),
        tts=build_tts(language=lang),
        vad=silero.VAD.load(),
        turn_handling=TurnHandlingOptions(
            turn_detection=MultilingualModel(),
        ),
    )

    agent = AdmissionCounselorAgent(session_ref=session)

    # Goodbye message just before disconnect
    @ctx.room.on("participant_disconnected")
    def on_participant_left(participant):
        logger.info("Participant left: %s", ctx.room.name)
        session.generate_reply(
            instructions=(
                f"The student is leaving. Say this goodbye warmly in one sentence: "
                f"'{random.choice(_GOODBYE_MESSAGES)}'"
            )
        )

    await session.start(
        room=ctx.room,
        agent=agent,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=noise_cancellation.BVC(),
            ),
        ),
    )

    # Opening greeting — ask language ONCE, naturally
    await session.generate_reply(
        instructions=(
            "Greet the student warmly."
            "Ask which language they prefer: English, Hindi, or Bengali. "
            "Ask this ONCE only. Keep it under 1 sentences."
        )
    )



def main():
    agents.cli.run_app(server)


if __name__ == "__main__":
    main()
