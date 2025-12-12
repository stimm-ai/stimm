# Using the Web Interface

The Stimm web interface is a modern, responsive dashboard built with Next.js that allows you to manage agents, RAG configurations, and have real-time voice conversations.

## Accessing the Interface

After starting the platform (see [Installation](../getting-started/installation.md)), open your browser and navigate to:

- **Local development**: http://front.localhost (Docker Compose) or http://localhost:3000 (local frontend)
- **Production**: Your configured domain (e.g., https://stimm.yourcompany.com)

## Dashboard Overview

The dashboard is divided into several sections accessible via the sidebar:

- **Home** – Overview of the platform with quick links.
- **Stimm** – Voice conversation interface.
- **Agents** – Agent management (create, edit, delete).
- **RAG** – RAG configuration management.
- **Settings** – System settings (future).

## Starting a Voice Conversation

1. Click **Speak with an agent** in the header.
2. Select an agent from the dropdown (agents must be created first).
3. Click **Start Conversation** and allow microphone access when prompted.
4. Speak into your microphone – the agent will respond in real-time.

The interface shows a transcript of the conversation and some metrics.

## Managing Agents

Navigate to **Agents** to see a list of all configured agents. From there you can:

- **Create a new agent** – Click “Create Agent” and fill in the form (name, description, provider settings).
- **Edit an existing agent** – Click the edit icon next to an agent.
- **Delete an agent** – Click the delete icon (requires confirmation).

Each agent can be associated with a RAG configuration for knowledge-augmented responses.

## Managing RAG Configurations

Navigate to **RAG** to manage Retrieval-Augmented Generation configurations.

- **Create a RAG configuration** – Choose a provider (Qdrant) and fill in the required fields.
- **Upload documents** – After creating a configuration, you can upload PDF, DOCX, Markdown, or text files that will be ingested into the vector database.
- **Set as default** – One configuration can be marked as the default, used by agents that don’t have an explicit RAG configuration.

## SIP Integration

If SIP bridge is enabled, you can monitor active SIP calls and configure dispatch rules via the API (web interface for SIP management is planned).

## Troubleshooting

- **Microphone not working**: Ensure your browser has permission to access the microphone. Check the browser console for errors.
- **No agents listed**: Create at least one agent via the Agents page.
- **Audio latency**: Check your network connection and check providers (prefer small and fast models).

## Next Steps

- Learn about the [Command-Line Interface](cli.md) for advanced operations.
- Explore [Managing Agents](managing-agents.md) in detail.
- See [SIP Integration](../developer/sip-integration.md) for telephony setup.
