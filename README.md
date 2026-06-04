# AI Admission Counselor — Voice Agent

A real-time voice AI agent that helps students and parents navigate college admissions in West Bengal and across India.

Speaks in **Bengali+English mix (Banglish)**, **Hinglish**, and **English** — the way students actually talk.

---

## What it does

- Answers questions about WBJEE, JEE, CUET, NEET, MAKAUT counseling
- Predicts colleges based on rank, percentage, and category
- Explains cutoff trends with context — not just numbers
- Recommends courses based on interests and career goals
- Handles scholarship queries (Swami Vivekananda, NSP, state schemes)
- Detects confusion, anxiety, and parent mode — adapts tone accordingly
- Asks follow-up questions when the student goes quiet
- Sends a warm goodbye when the session ends

---

## Tech Stack

| Layer | Technology |
|---|---|
| Voice pipeline | [LiveKit Agents](https://docs.livekit.io/agents) |
| Speech-to-Text | Deepgram Nova-3 (multilingual) |
| LLM | Gemini 2.5 Flash via LiveKit inference |
| Text-to-Speech | Sarvam AI bulbul:v3 (streaming) |
| VAD | Silero |
| Turn detection | LiveKit multilingual turn detector |
| Noise cancellation | LiveKit BVC |

---

## Project Structure

```
src/
  admission_counselor.py       # Entry point — LiveKit agent wiring
  agent/
    conversation_engine.py     # System prompt + language modes
    admission_guardrails.py    # Language detection, signal detection
    fallback_providers.py      # STT / LLM / TTS builders
    sarvam_tts.py              # Sarvam streaming TTS adapter
```

---

## Setup

### 1. Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) package manager
- ffmpeg (for audio decoding)

```bash
sudo apt-get install -y ffmpeg     # Ubuntu/Debian
brew install ffmpeg                 # macOS
```

### 2. Install dependencies

```bash
uv sync
```

### 3. Download model files

```bash
uv run python -m livekit.agents download-files
```

### 4. Configure API keys

```bash
cp .env.example .env.local
```

Edit `.env.local` and fill in your keys:

| Key | Get it from |
|---|---|
| `LIVEKIT_URL` | [cloud.livekit.io](https://cloud.livekit.io) → Settings |
| `LIVEKIT_API_KEY` | Same |
| `LIVEKIT_API_SECRET` | Same |
| `DEEPGRAM_API_KEY` | [console.deepgram.com](https://console.deepgram.com) — free $200 credit |
| `SARVAM_API_KEY` | [dashboard.sarvam.ai](https://dashboard.sarvam.ai) — free tier |

---

## Running

**Terminal mode (voice via mic/speaker):**
```bash
uv run src/admission_counselor.py console
```

**Text mode (type instead of speak — good for testing):**
```bash
uv run src/admission_counselor.py console --text
```

**Dev mode (connect to LiveKit Cloud console):**
```bash
uv run src/admission_counselor.py dev
```

---

## Changing the Voice

The default voice is `sumit` (clear male). Change it in `.env.local`:

```
SARVAM_VOICE=sumit      # default
SARVAM_VOICE=arya       # alternative male
SARVAM_VOICE=priya      # female
SARVAM_VOICE=abhilash   # warm male
```

Full voice list: `anushka, abhilash, manisha, vidya, arya, karun, hitesh, aditya, ritu, priya, neha, rahul, pooja, rohan, simran, kavya, amit, dev, ishita, shreya, sumit, roopa, kabir, varun`

---

## Language Modes

The agent asks the student their preference at the start:

| Mode | Style |
|---|---|
| Bengali+English (Banglish) | `"Thik ache, apnar rank er basis e options dekhchi. CSE te chance ache."` |
| Hindi+English (Hinglish) | `"12th mein kitne percentage aaye? CSE mein interest hai?"` |
| English | Professional, clear, friendly |

---

## Supported Institutions

WBJEE · JEE Main · JEE Advanced · CUET · NEET · MAKAUT  
Jadavpur University · University of Calcutta · Presidency University  
St. Xavier's · Heritage Institute · IEM · Techno India · Haldia Institute  
NIT Durgapur · IIEST Shibpur · IITs · NITs · VIT · SRM · KIIT

---

## Environment Variables

| Variable | Description | Required |
|---|---|---|
| `LIVEKIT_URL` | LiveKit Cloud WebSocket URL | Yes |
| `LIVEKIT_API_KEY` | LiveKit API key | Yes |
| `LIVEKIT_API_SECRET` | LiveKit API secret | Yes |
| `DEEPGRAM_API_KEY` | Deepgram STT key | Yes |
| `SARVAM_API_KEY` | Sarvam TTS key | Yes |
| `DEFAULT_LANGUAGE` | Default TTS language: `en`, `hi`, `bn` | No (default: `en`) |
| `SARVAM_VOICE` | Voice name override | No (default: `sumit`) |
