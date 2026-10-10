# Digital twin voice agent

A visitor talks hands-free with a person's digital twin, in the person's cloned
voice. **Every answer comes from a grounded `/ask` endpoint**; the voice agent only
bridges the wait in its own words, then reads out what `/ask` said. It was written for
[etiennelescot.fr](https://etiennelescot.fr): the default URLs point there, and
everything else about the person (voice, phrases, proper nouns) is configuration.

## How it maps onto stimm

| stimm role | Here | Does |
|---|---|---|
| `VoiceAgent` (live, fast) | `TwinAgent` in [twin.py](twin.py) | At the end of a turn, says a bridge in stimm's [`direct` style](../../README.md#conversation-styles): one short line a fast LLM writes for the turn, in the twin's voice. It never states a fact. |
| `Supervisor` (deep) | `AskSupervisor` in [twin.py](twin.py) | Puts the question to `/ask`, relays the evidence to the page, and streams the answer into the voice with `Supervisor.speak()`, sentence by sentence, citation markers removed. |

```text
visitor ─ end of turn ─► TwinAgent ─ bridge LLM ─► "Mmm, ton parcours…"
                            │ TranscriptMessage
                            ▼
                       AskSupervisor ─ POST /ask, Authorization: Voice <token> ─► SSE
                            │ cite · citations · done ──► page (twin.* topics)
                            └ speak(sentences) ──► TwinAgent says them after the bridge
visitor speaks over it ─► utterance interrupted ─► speak() → False ─► /ask request aborted
```

The supervisor runs in the agent's own job: `supervisor.attach(agent)` links the two
protocols in-process, so no second participant joins the room. A supervisor in
another service would `connect()` and send the same messages over the data channel.

**Why not a custom `llm_node` streaming `/ask`?** The answer is not the voice agent's
own reply, it is the supervisor's, and `speak()` says it as one utterance whose
interruption cancels the `/ask` request.

## Turn flow

- **Bridge**: one short line, written each turn by a fast LLM without reasoning, never
  a canned phrase: an interjection, the subject of the question, or both, trailing
  off into the answer. It never mentions notes, checking or waiting. No text within
  1 s, or an error: silence.
- **Answer**: right after the bridge, each sentence spoken as soon as it is complete.
  `/ask` takes 3 to 7 s to send its first fragment.
- **Text to speech**: the voice drops the `[n]` markers and the light markdown of
  `/ask`, `**bold**` and `- ` list items. Each list item is a sentence of its own.
- **`no_source`** and the off-topic refusal: the fixed sentence, as given.
- **`degraded`**: one configured sentence ("the sources are on screen"); the results
  go to the page on `twin.results`.
- **Stream `error`** or HTTP failure: the half sentence is dropped, then a short apology.
- **Barge-in**: on the bridge or the answer, stops the voice and aborts the `/ask`
  request. A new question replaces the one in flight.
- **Duration**: goodbye at 285 s with no more questions, hang-up at 300 s; the agent
  leaves a room the visitor has been gone from for 20 s.
- **End**: `POST /voice/settle` with `{ sttSeconds, ttsChars, agentMinutes }` from
  livekit's session usage, clamped to one session's worth (300 s, 5,000 characters,
  5 min), as soon as the session closes. Best effort: `409` means already settled, a
  failure leaves the reservation in place.

## Session credential

The backend dispatches the agent (`agent_name="digital-twin"`, explicit dispatch)
with the **voice session token as the job metadata**:
`base64url(JSON payload).base64url(HMAC)`. The agent does not verify it. It sends it
as `Authorization: Voice <token>` to `/ask` and `/voice/settle`, reads `lang` from the
payload, and never logs it. Without metadata (console, `lk agent dev`), `/ask` serves
its public level to the agent's own IP, and nothing is settled.

## Data channel contract

The page receives JSON on LiveKit **text streams**
(`room.registerTextStreamHandler(topic, …)` in livekit-client):

| Topic | Payload |
|---|---|
| `twin.cite` | The `/ask` `cite` event, unchanged: `{ n, id, url, title, type, fact }`. Sent before the sentence that cites it is spoken. |
| `twin.citations` | The `/ask` `citations` event: `[{ n, id, url, title }]`. |
| `twin.results` | Degraded mode only, `done.results`: `[{ id, url, title, type, excerpt, fact }]`. |
| `twin.done` | `{ mode, question, answer, reason?, truncated? }`. `mode` is `answer`, `no_source`, `degraded` or `error`; `answer` is `/ask`'s raw text, `[n]` markers and markdown included, for the page's text history. Not sent when the visitor interrupts the answer. |

Subtitles of both voices, bridges included, come from livekit's standard
transcription streams (`lk.transcription`); the twin's are the spoken text.

## Configuration

| Variable | Default | Notes |
|---|---|---|
| `ASK_URL` | `https://mcp.etiennelescot.fr/ask` | |
| `SETTLE_URL` | `https://mcp.etiennelescot.fr/voice/settle` | |
| `TWIN_LANG` | `fr` | When the token carries no `lang`. `fr` or `en`. |
| `STT_PROVIDER` | `mistral` | `mistral`, `elevenlabs` or `deepgram` |
| `STT_MODEL` | `voxtral-mini-transcribe-realtime-2602`, `scribe_v2_realtime`, `nova-3` | |
| `STT_KEYTERMS` | | Comma-separated proper nouns. ElevenLabs and Deepgram only: the Voxtral realtime model takes none. |
| `TTS_PROVIDER` | `mistral` | `mistral` or `elevenlabs` |
| `TTS_MODEL` | `voxtral-mini-tts-latest`, `eleven_flash_v2_5` | |
| `TTS_VOICE`, `TTS_VOICE_FR`, `TTS_VOICE_EN` | | The cloned voice: a Mistral voice id or an ElevenLabs `voice_id`. |
| `TTS_REF_AUDIO`, `…_FR`, `…_EN` | | Mistral only: path to a 3–25 s sample for zero-shot cloning. |
| `TTS_STABILITY`, `TTS_SIMILARITY`, `TTS_STYLE`, `TTS_SPEED` | `0.3`, `0.75`, `0.2`, the voice's own | ElevenLabs only. Stability below ElevenLabs' 0.5 makes the voice more expressive. `eleven_v3` and `eleven_v4*` go through text-to-dialogue, where livekit-plugins-elevenlabs 1.8.5 sends stability alone and logs that it drops the rest. |
| `CHARACTER_URL` | `https://mcp.etiennelescot.fr/api/v1/character` | How the person sounds: its `interaction` entries, fetched once per worker and language with `?lang=`, are given to the bridge LLM to colour its tone; the bridge rules still come first, and the `calibration` samples are marked as a register never to say. Empty: none. Unreachable within 1.5 s: the session goes on without it. |
| `INTERRUPTION_MODE`, `INTERRUPTION_MIN_S` | `vad`, `0.4` | How the visitor cuts the twin off: livekit's `vad` (as soon as they speak this long) or `adaptive` (an ML model that ignores backchannels, slower to react). |
| `BRIDGE_PROVIDER` | `mistral` | The bridge LLM: `mistral`, `openai-compatible` or `livekit` (LiveKit Inference, default model `google/gemma-4-31b-it`, credentials `LIVEKIT_INFERENCE_API_KEY`/`LIVEKIT_INFERENCE_API_SECRET` of a LiveKit Cloud project; EU-only models through the project's *Inference region restriction*). Temperature 0.8, 24 tokens at most. |
| `BRIDGE_MODEL` | `ministral-8b-latest` | Required with `openai-compatible`. `mistral-medium-latest` keeps to the bridge rules more reliably, at about the same latency. |
| `BRIDGE_BASE_URL`, `BRIDGE_API_KEY` | | `openai-compatible` only, e.g. `https://api.deepseek.com/v1` with `deepseek-flash`. Sent with `thinking: {"type": "disabled"}`. |
| `MISTRAL_API_KEY`, `ELEVEN_API_KEY`, `DEEPGRAM_API_KEY` | | Read by the plugins in use. |
| `CLOSING_PHRASE`, `DEGRADED_PHRASE`, `APOLOGY_PHRASE` (`_FR`, `_EN`) | built in | |
| `MAX_SESSION_S`, `CLOSING_LEAD_S`, `VISITOR_GONE_S` | `300`, `15`, `20` | |

A `_FR` / `_EN` variable wins over the plain one.

Each turn logs its timeline at INFO, in ms from the end of the user's turn: `bridge
text` (its word count), `bridge audio`, `ask first delta`, `first sentence` (its
length), `answer audio`. Sizes only, never what was said.

## Run locally

```bash
cd examples/digital-twin
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m livekit.agents download-files
export MISTRAL_API_KEY=...
lk agent console              # or: python agent.py console. Microphone and speaker.
```

`lk agent dev` connects the agent to your LiveKit project instead (`LIVEKIT_URL`,
`LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`). It only joins the rooms it is dispatched
to: `lk dispatch create --new-room --agent-name digital-twin`.

Tests need no network and no key: `pytest examples/digital-twin/tests` from the repo
root, with stimm installed (`pip install -e .`). Use `pytest`, not `python -m pytest`,
which would put the repo-root `livekit/` test stubs on the path.

## Deploy on LiveKit Cloud

```bash
cd examples/digital-twin
lk agent create --secrets-file secrets.env   # writes livekit.toml (gitignored)
lk agent deploy                              # later versions
lk agent update-secrets --secrets-file secrets.env
```

`secrets.env` holds the provider keys and any variable above; LiveKit Cloud sets
`LIVEKIT_URL`, `LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET` itself. A file such as a
reference sample can be mounted with `--secret-mount`, under `/etc/secrets/` (16 KB
maximum), or copied into the build context. To deploy from CI, `lk agent config
--id <agent-id>` writes `livekit.toml` for an existing agent. `requirements.txt`
installs stimm from a pinned commit; bump it with the example.

## Cost notes

List prices, October 2026, for one 5-minute session, before the bridge LLM (under
1,000 tokens in and 24 out a turn):

| Item | Price | Per session |
|---|---|---|
| Voxtral realtime STT (streams all call long) | $0.006/min | ~$0.03 |
| Voxtral TTS, ~3,000 characters | $16 per 1M characters | ~$0.05 |
| `/ask` questions | ~$0.002–0.007 each, ~$0.015 reserved until settled | ~$0.01–0.05 |
| LiveKit Cloud Build plan | 1,000 agent minutes a month, 5 concurrent sessions | free up to the plan |

ElevenLabs costs about three times more per character (Flash), and its Scribe
realtime STT about $0.39/h.
