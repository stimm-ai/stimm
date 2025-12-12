# Quick Start

This guide will help you run your first voice conversation with Stimm in under 5 minutes.

## Prerequisites

- Docker and Docker Compose installed
- A microphone (for voice interaction) or you can use text-only chat

## Step 1: Clone and Start Services

```bash
git clone https://github.com/stimm-ai/stimm.git
cd stimm
docker-compose up --build
```

Wait for all services to be healthy (this may take a few minutes). You can monitor logs in the terminal.

## Step 2: Access the Web Interface

Open your browser and navigate to [http://front.localhost](http://front.localhost). You should see the Stimm dashboard.

## Step 3: Create an Agent

1. Click on **Agents** in the sidebar.
2. Click **Create Agent**.
3. Fill in the agent details (name, description, provider settings). You can use the default values for a quick test.
4. Click **Save**.

## Step 4: Start a Voice Conversation

1. Go to the **Stimm** page from the sidebar.
2. Select the agent you just created from the dropdown.
3. Click **Start Conversation** and allow microphone access.
4. Speak into your microphone – the agent will respond in real-time.

## Step 5: Try the CLI Tool

Stimm includes a powerful CLI tool for development and testing. You can start a text chat with an agent directly from the terminal.

```bash
# Ensure the backend is running (if using Docker Compose, it already is)
# Run the CLI in HTTP mode (connect to the running backend)
uv run python -m src.cli.main --http chat --agent-name "your-agent-name"
```

Replace `"your-agent-name"` with the name of the agent you created.

## Next Steps

- Explore the [Architecture](../developer/architecture-overview.md) to understand how Stimm works.
- Learn about [Configuration](configuration.md) to customize your setup.
- Check out the [API Reference](../api-reference/python.md) for programmatic usage.
