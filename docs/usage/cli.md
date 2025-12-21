# Command-Line Interface

Stimm includes a powerful CLI tool for development, testing, and administrative tasks. It can operate in two modes:

- **Local mode** – Instantiates services directly from your source code (requires infrastructure services to be running).
- **HTTP mode** – Acts as a client to a running backend server (useful for testing deployed instances).

## Installation

The CLI is part of the Stimm Python package. If you have installed the project dependencies (via `uv sync`), you can run it with:

```bash
uv run python -m src.cli.main [GLOBAL_OPTIONS] <COMMAND> [COMMAND_OPTIONS]
```

> [!IMPORTANT]
> Some commands (like `talk` or `test echo`) require local audio hardware access via `pyaudio`. You must install the project with the `audio` extra to use these:
>
> ```bash
> uv sync --extra audio
> ```

## Global Options

- `--http [URL]` – Activate HTTP mode. If `URL` is provided, it uses that specific backend URL. If omitted, it uses the URL from your `.env` file.
- `--verbose, -v` – Enable detailed `DEBUG` logging.
- `--help` – Show help message.

## Commands

### `talk`

Start a full, real-time voice conversation with an agent.

```bash
# Local mode with agent "ava"
uv run python -m src.cli.main talk --agent-name "ava"

# With custom room name
uv run python -m src.cli.main talk --agent-name "ava" --room-name "my-test-room"

# HTTP mode (connect to remote backend)
uv run python -m src.cli.main --http talk --agent-name "ava"
```

**Options:**

- `--agent-name NAME` – The name of the agent to talk to.
- `--room-name NAME` – Custom LiveKit room name.
- `--disable-rag` – Disable Retrieval-Augmented Generation for the session.

### `chat`

Start an interactive text-only chat session with an agent.

```bash
# Local text chat with default agent
uv run python -m src.cli.main chat

# With a specific agent, disabling RAG
uv run python -m src.cli.main chat --agent-name "ava" --disable-rag
```

**Options:** Same as `talk` (except room-related options).

### `agents`

Manage agents in the system.

```bash
# List all agents
uv run python -m src.cli.main agents list
```

**Subcommands:**

- `list` – Display a list of all configured agents.

### `test`

Run diagnostic tests.

```bash
# Test the full LiveKit audio pipeline with an echo server
uv run python -m src.cli.main test echo

# With verbose logging
uv run python -m src.cli.main --verbose test echo
```

**Subcommands:**

- `echo` – Starts an echo client and server to verify that your audio is being correctly captured and played back through LiveKit.

### `livekit`

Manage LiveKit rooms and SIP bridge.

```bash
# List all LiveKit rooms
uv run python -m src.cli.main livekit list-rooms

# Delete all SIP rooms and terminate agent processes
uv run python -m src.cli.main livekit clear-sip-bridge

# Delete all LiveKit rooms (SIP and non-SIP; non-SIP rooms may be protected)
uv run python -m src.cli.main livekit clear-rooms
```

**Subcommands:**

- `list-rooms` – Lists all LiveKit rooms with participant counts.
- `clear-rooms` – Deletes all LiveKit rooms (some rooms may be protected and produce a warning).
- `clear-sip-bridge` – Cleans up SIP bridge agent processes and deletes SIP rooms.

## Examples

### Connect to a Remote Backend

```bash
uv run python -m src.cli.main --http http://api.example.com talk --agent-name "ava"
```

### Debug a Voice Session

```bash
uv run python -m src.cli.main --verbose talk --agent-name "debug-agent"
```

### Check SIP Bridge Status

```bash
uv run python -m src.cli.main livekit list-rooms
```

## Troubleshooting

- **“Agent not found”** – Ensure the agent exists in the database (create it via the web interface or API).
- **“Cannot connect to LiveKit”** – Verify that LiveKit is running and the `LIVEKIT_URL` environment variable is correct.
- **“No audio heard”** – Check your microphone permissions and that your speakers are working. Use the `test echo` command to verify the audio pipeline.
- **“ModuleNotFoundError: No module named 'pyaudio'”** – The CLI audio tools require the `audio` extra. Run `uv sync --extra audio` to install it.

## Next Steps

- Learn about [Managing Agents](managing-agents.md) via the web interface.
- Explore the [REST API](../api-reference/rest.md) for programmatic control.
