# API Reference

Stimm exposes a RESTful API for managing agents, RAG configurations, documents, and system health. The API is built with FastAPI and includes an interactive OpenAPI UI that allows you to explore endpoints, try requests, and view schemas directly from your browser.

## Interactive Documentation (Swagger UI)

The easiest way to explore the API is via the built‑in Swagger UI:

- **Local Docker Compose**: [http://api.localhost/docs](http://api.localhost/docs)
- **Local backend**: [http://localhost:8001/docs](http://localhost:8001/docs)
- **Production**: Replace the host with your deployed domain.

The Swagger UI provides:
- A complete list of all endpoints with HTTP methods.
- Schema definitions for request/response bodies.
- An interactive “Try it out” feature to execute requests directly from the browser.
- Authentication support (if configured).

We recommend using the Swagger UI for experimentation and debugging. The rest of this page serves as a textual reference for quick lookup.

### Embedded Swagger UI

Below is an embedded Swagger UI that connects to the live API (requires the backend to be running). If the API is not reachable, you can still use the links above.

<swagger-ui src="http://api.localhost/openapi.json" tryitoutenabled="true" docexpansion="list" filter="true"></swagger-ui>

## Base URL

When running locally with Docker Compose:

```
http://api.localhost
```

When running the backend directly:

```
http://localhost:8001
```

In production, replace with your domain.

## Authentication

Currently, the API does not require authentication for local development. For production deployments, you should add an authentication layer (e.g., API keys, JWT) via a reverse proxy or middleware.

## Endpoints Overview

### Agents

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/agents/` | List all agents |
| POST | `/api/agents/` | Create a new agent |
| GET | `/api/agents/{agent_id}` | Retrieve a specific agent |
| PUT | `/api/agents/{agent_id}` | Update an agent |
| DELETE | `/api/agents/{agent_id}` | Delete an agent |
| GET | `/api/agents/{agent_id}/conversation` | Start a conversation with an agent |

### RAG Configurations

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/rag‑configs/` | List all RAG configurations |
| POST | `/api/rag‑configs/` | Create a new RAG configuration |
| GET | `/api/rag‑configs/{id}` | Retrieve a specific configuration |
| PUT | `/api/rag‑configs/{id}` | Update a configuration |
| DELETE | `/api/rag‑configs/{id}` | Delete a configuration |
| GET | `/api/rag‑configs/default/current` | Get the current default RAG configuration |
| PUT | `/api/rag‑configs/{id}/set‑default` | Set a configuration as the default |
| GET | `/api/rag‑configs/providers/available` | List available RAG providers with field definitions |
| GET | `/api/rag‑configs/providers/{provider}/fields` | Get field definitions for a specific provider |

### Documents

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/rag‑configs/{rag_config_id}/documents` | Upload and ingest a document |
| GET | `/api/rag‑configs/{rag_config_id}/documents` | List documents for a RAG configuration |
| DELETE | `/api/documents/{document_id}` | Delete a document |

### Conversation

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/conversation/stream` | Start a streaming conversation (WebSocket) |
| GET | `/api/conversation/status` | Get conversation status |

### Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Overall system health |
| GET | `/health/sip‑bridge` | SIP bridge health |
| GET | `/health/sip‑bridge‑status` | Detailed SIP bridge status |

### SIP Integration

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/sip/dispatch‑rules` | Update SIP dispatch rules |
| GET | `/api/sip/trunks` | List SIP trunks |

## Examples

### Create an Agent

```bash
curl -X POST "http://api.localhost/api/agents/" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "MyAgent",
    "description": "A helpful voice assistant",
    "llm_provider": "groq",
    "llm_model": "mixtral-8x7b-32768",
    "stt_provider": "deepgram",
    "tts_provider": "deepgram"
  }'
```

### Upload a Document

```bash
curl -X POST "http://api.localhost/api/rag-configs/{config_id}/documents" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/document.pdf"
```

## Error Responses

The API uses standard HTTP status codes and returns JSON error details.

```json
{
  "detail": "Agent not found"
}
```

Common status codes:

- `200` – Success
- `201` – Created
- `400` – Bad request (validation error)
- `404` – Resource not found
- `500` – Internal server error

## Rate Limiting

Rate limiting is not currently enforced but can be added via Traefik or a middleware.

## WebSocket Endpoints

For real‑time audio streaming, use the WebSocket endpoint:

```
ws://api.localhost/api/conversation/stream
```

See the [Data Flow](../developer-guide/data-flow.md) section for details on the audio pipeline.
