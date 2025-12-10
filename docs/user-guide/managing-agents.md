# Managing Agents

Agents are the core conversational entities in Stimm. Each agent has a unique personality, voice, and knowledge base (via RAG). This guide explains how to create, configure, and manage agents through the web interface and API.

## What is an Agent?

An agent is a configured instance that can hold real‑time voice or text conversations. It consists of:

- **Name** – A unique identifier (e.g., “ava”, “support‑bot”).
- **Description** – Human‑readable description of the agent’s role.
- **System prompt** – Instructions that define the agent’s behavior and tone.
- **Provider settings** – Which LLM, TTS, and STT providers to use, along with model selections.
- **RAG configuration** (optional) – Which knowledge base the agent should use for retrieval‑augmented generation.

## Creating an Agent

### Via Web Interface

1. Navigate to **Agents** in the sidebar.
2. Click **Create Agent**.
3. Fill in the form:

   - **Name** – Required, alphanumeric and underscores only.
   - **Description** – Optional.
   - **System Prompt** – You can use the default or write your own.
   - **LLM Provider** – Choose from Groq, Mistral, OpenRouter, Llama.cpp, or OpenAI‑compatible.
   - **LLM Model** – Model name specific to the provider (e.g., `mixtral‑8x7b‑32768` for Groq).
   - **TTS Provider** – Deepgram, ElevenLabs, Async.ai, or Kokoro (local).
   - **STT Provider** – Deepgram or Whisper (local).
   - **RAG Configuration** – Select a RAG configuration from the dropdown, or leave empty to use the default.

4. Click **Save**. The agent will be immediately available for conversations.

### Via API

You can also create agents programmatically using the REST API:

```bash
curl -X POST "http://api.localhost/api/agents/" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my‑agent",
    "description": "A helpful assistant",
    "llm_provider": "groq",
    "llm_model": "mixtral‑8x7b‑32768",
    "tts_provider": "deepgram",
    "stt_provider": "deepgram",
    "rag_config_id": "optional‑uuid"
  }'
```

See the [REST API](../api/rest.md) for full details.

## Editing an Agent

To modify an existing agent:

1. Go to **Agents**.
2. Click the edit icon (✏️) next to the agent you want to change.
3. Update any fields and click **Save**.

Changes take effect immediately for new conversations; existing conversations continue with the previous configuration.

## Deleting an Agent

1. Go to **Agents**.
2. Click the delete icon (🗑) next to the agent.
3. Confirm deletion.

Deleting an agent does not affect any RAG configurations or documents.

## Default Agent

If you have only one agent, it will be used as the default for the voice interface. If you have multiple agents, you must select which one to use when starting a conversation.

## Agent System Prompts

The system prompt is a crucial part of the agent’s behavior. It is sent to the LLM before each conversation to set the tone, constraints, and instructions.

Example prompt for a customer‑support agent:

```
You are a friendly customer‑support representative for Stimm.
Answer questions clearly and concisely, and always be polite.
If you don’t know the answer, say so and offer to escalate the issue.
Do not make up information.
```

You can edit the system prompt when creating or editing an agent.

## Associating with RAG

If you want the agent to have access to a specific knowledge base, select a RAG configuration in the agent form. The agent will then use that configuration for retrieval during conversations.

If no RAG configuration is selected, the agent will use the **default RAG configuration** (if one is set). If there is no default, RAG is disabled for that agent.

## Testing an Agent

After creating an agent, you can test it immediately:

- **Voice conversation**: Go to the **Stimm** page, select the agent, and start talking.
- **Text chat**: Use the CLI `chat` command (see [CLI](cli.md)).
- **API**: Send a test query via the `/api/conversation/stream` endpoint.

## Best Practices

- **Naming**: Use descriptive but short names (e.g., `support‑en`, `sales‑fr`).
- **Provider selection**: Choose providers based on latency, cost, and language support.
- **System prompts**: Keep them concise but explicit about the agent’s role.
- **RAG**: Associate agents with relevant knowledge bases to improve answer quality.

## Next Steps

- Learn about [Managing RAG Configurations](managing‑rag.md).
- Explore the [Web Interface](web‑interface.md) for more administrative tasks.
- Read about [SIP Integration](sip‑integration.md) to connect agents to phone calls.
