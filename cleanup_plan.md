# Cleanup & Legacy Removal Plan

This document outlines the strategy for removing legacy server-side rendered (SSR) templates and associated routes, moving fully to the Next.js frontend architecture.

## 1. Analysis Summary

### Legacy Assets Identified for Removal:
- **Templates:**
    - `src/services/stt/templates/stt_interface.html`
    - `src/services/rag/templates/chatbot.html`
    - `src/services/tts/templates/tts_interface.html`
- **Routes:**
    - `src/services/stt/web_routes.py` (Full file, serving STT interface)
    - `src/services/tts/web_routes.py` (Full file, serving TTS interface)
    - `src/services/rag/chatbot_routes.py` (Partially - `chat_interface` endpoint, but `chat_message` API endpoint might be used by API consumers? -> *Check*: The new frontend uses LiveKit mostly, but might fallback to REST? No, the new frontend uses `src/front/components/voicebot/VoicebotInterface.tsx` which uses `useLiveKit`. The RAG routes in `chatbot_routes.py` seem to be mixed: `chat_interface` returns HTML, but `chat_message` returns a StreamingResponse. We need to check if `chat_message` is used by the Next.js app.
        - *Correction*: `src/services/rag/chatbot_routes.py` has `chat_interface` (HTML) and `chat_message` (API). The API part should be preserved if used. However, the `VoicebotInterface.tsx` seems to rely purely on LiveKit/WebSockets (`useLiveKit`). Let's verify if `chat_message` is used.
        - `src/front` search showed `apiCall` usage but not specifically for `/rag/chat/message`. The new architecture seems to be LiveKit-centric.
        - *Decision*: We will remove the HTML serving endpoints. We will keep the API endpoints in `chatbot_routes.py` for now to avoid breaking potential non-LiveKit API usage, but remove `chat_interface`.
    - `src/main.py`: Remove mounts for `stt_web_router`, `tts_web_router`, `voicebot_interface`, and static file mounts if they are only for legacy.

- **Static Files:**
    - `src/static/` contains `agent_selector.js`, `audio_streamer.js`. These seem to be used by the legacy HTML templates.

### Dependencies/Risks:
- **Shared Logic:** `stt_web_routes.py` uses `AgentService`. This service is core and must stay.
- **API Endpoints:** `chatbot_routes.py` contains `chat_message` which might be useful. We will only strip the HTML serving part (`chat_interface`).
- **Main Entry:** `src/main.py` imports and mounts these routers. These imports must be removed.

## 2. Action Plan

### Step 1: Remove Legacy Templates
- Delete `src/services/stt/templates/stt_interface.html`
- Delete `src/services/rag/templates/chatbot.html`
- Delete `src/services/tts/templates/tts_interface.html`
- Delete `src/services/agents/templates/` (if exists and empty/legacy) -> Checked, it's empty/non-existent.

### Step 2: Remove Legacy Web Routes
- **STT**: Delete `src/services/stt/web_routes.py`.
- **TTS**: Delete `src/services/tts/web_routes.py`.
- **RAG**: Edit `src/services/rag/chatbot_routes.py` to remove `chat_interface` (HTMLResponse) and `templates` initialization. Keep API endpoints.

### Step 3: Cleanup `src/main.py`
- Remove imports:
    - `from services.stt.web_routes import router as stt_web_router`
    - `from services.tts.web_routes import router as tts_web_router`
    - `from fastapi.templating import Jinja2Templates` (if only used for legacy)
- Remove Router Includes:
    - `app.include_router(stt_web_router, prefix="/stt", tags=["stt-web"])`
    - `app.include_router(tts_web_router, prefix="/tts", tags=["tts-web"])`
- Remove Legacy Endpoints in `main.py`:
    - `voicebot_interface` endpoint returning `voicebot.html`.
    - `templates` initialization in `main.py`.
- Remove Static Mounts:
    - `app.mount("/static", ...)` if it points to `services/agents/static`.
    - Verify if `src/static` is still needed.

### Step 4: Remove Legacy Static Files
- Check usage of `src/static/agent_selector.js`, `audio_streamer.js`. If they are for the HTML interfaces, delete them.

### Step 5: Verification
- Run `python src/main.py` (or equivalent startup) to ensure no import errors.
- Check `http://localhost:8001/docs` to ensure legacy routes are gone and API routes remain.
