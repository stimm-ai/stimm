# Digital twin voice agent

A visitor talks hands-free with a person's digital twin, in the person's cloned
voice. **Every answer comes from a grounded `/ask` endpoint**; the voice agent only
acknowledges, covers the wait, and reads out what `/ask` said. It was written for
[etiennelescot.fr](https://etiennelescot.fr): the default URLs point there, and
everything else about the person (voice, phrases, proper nouns) is configuration.

## How it maps onto stimm

| stimm role | Here | Does |
|---|---|---|
| `VoiceAgent` (live, fast) | `TwinAgent` in [twin.py](twin.py) | At the end of a turn, plays a pre-recorded acknowledgement at once, then fillers at 2.5 s and 6 s while the answer has not started. No LLM: it never states a fact. |
| `Supervisor` (deep) | `AskSupervisor` in [twin.py](twin.py) | Puts the question to `/ask`, relays the evidence to the page, and streams the answer into the voice with `Supervisor.speak()`, sentence by sentence, citation markers removed. |

```text
visitor ─ end of turn ─► TwinAgent ─ ack clip (0 s) · filler (2.5 s, 6 s) …
                            │ TranscriptMessage
                            ▼
                       AskSupervisor ─ POST /ask, Authorization: Voice <token> ─► SSE
                            │ cite · citations · done ──► page (twin.* topics)
                            └ speak(sentences) ──► TwinAgent says them, one utterance
visitor speaks over it ─► utterance interrupted ─► speak() → False ─► /ask request aborted
```

The supervisor runs in the agent's own job: `supervisor.attach(agent)` links the two
protocols in-process, so no second participant joins the room. A supervisor in
another service would `connect()` and send the same messages over the data channel.

**Why not a custom `llm_node` streaming `/ask`?** The answer is not the voice agent's
own reply, it is the supervisor's, and `speak()` says it as one utterance whose
interruption cancels the `/ask` request. A reply generated in `llm_node` is queued as
soon as the turn ends, so nothing can be slotted between the acknowledgement and the
answer; fillers queued in front of `speak()` can.

## Turn flow

- **Answer**: each sentence is spoken as soon as it is complete. `/ask` takes 3 to 7 s
  to send its first fragment, which the acknowledgement and fillers cover.
- **`no_source`** and the off-topic refusal: the fixed sentence, as given.
- **`degraded`**: one configured sentence ("the sources are on screen"); the results
  go to the page on `twin.results`.
- **Stream `error`** or HTTP failure: the half sentence is dropped, then a short apology.
- **Barge-in**: stops the voice and aborts the `/ask` request. A new question replaces
  the one in flight.
- **Duration**: goodbye at 285 s with no more questions, hang-up at 300 s; the agent
  leaves a room the visitor has been gone from for 20 s.
- **End**: `POST /voice/settle` with `{ sttSeconds, ttsChars, agentMinutes }` from
  livekit's session usage, once. Best effort: `409` means already settled, a failure
  leaves the reservation in place.

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
| `twin.done` | `{ mode, question, answer, reason?, truncated? }`. `mode` is `answer`, `no_source`, `degraded` or `error`; `answer` is `/ask`'s text with its `[n]` markers, for the page's text history. Not sent when the visitor interrupts the answer. |

Subtitles of both voices, acknowledgements and fillers included, come from livekit's
standard transcription streams (`lk.transcription`).

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
| `MISTRAL_API_KEY`, `ELEVEN_API_KEY`, `DEEPGRAM_API_KEY` | | Read by the plugins in use. |
| `ACK_PHRASES`, `FILLER_PHRASES` (`_FR`, `_EN`) | built in | `\|`-separated, rotated. |
| `CLOSING_PHRASE`, `DEGRADED_PHRASE`, `APOLOGY_PHRASE` (`_FR`, `_EN`) | built in | |
| `FILLER_DELAYS_S` | `2.5,6` | Seconds after the acknowledgement. |
| `MAX_SESSION_S`, `CLOSING_LEAD_S`, `VISITOR_GONE_S` | `300`, `15`, `20` | |
| `CLIPS_DIR` | `./clips` | Cache of the synthesized clips. |

A `_FR` / `_EN` variable wins over the plain one. The acknowledgement and filler clips
are synthesized once per voice and phrase, at the first session, then read from
`CLIPS_DIR`; until a clip exists, its phrase is spoken with live TTS. Ship the
directory in the image to skip that first synthesis.

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

List prices, October 2026, for one 5-minute session:

| Item | Price | Per session |
|---|---|---|
| Voxtral realtime STT (streams all call long) | $0.006/min | ~$0.03 |
| Voxtral TTS, ~3,000 characters | $16 per 1M characters | ~$0.05 |
| `/ask` questions | ~$0.002–0.007 each | ~$0.01–0.05 |
| LiveKit Cloud Build plan | 1,000 agent minutes a month, 5 concurrent sessions | free up to the plan |

ElevenLabs costs about three times more per character (Flash), and its Scribe
realtime STT about $0.39/h. Clips cost their characters once per voice.
