# SIP Integration

Stimm can connect incoming phone calls to AI agents via SIP (Session Initiation Protocol). This allows you to offer voice‑based customer support, interactive voice response (IVR), or any other telephony‑powered application.

## Overview

The SIP integration works as follows:

1. An external SIP client (softphone, IP phone, or telephony carrier) places a call to a configured phone number.
2. The LiveKit SIP server receives the call and creates a LiveKit room with the prefix `sip‑inbound‑`.
3. The Stimm SIP bridge detects the new room and spawns an agent specifically for that call.
4. The agent joins the room and begins a real‑time voice conversation with the caller.
5. When the call ends, the room is cleaned up and the agent process terminates.

## Prerequisites

- A running LiveKit instance with SIP support enabled (the default Docker Compose includes this).
- Redis (used for SIP trunk and dispatch rule storage).
- At least one configured agent.

## Enabling SIP Bridge

1. Set the environment variable `ENABLE_SIP_BRIDGE=true` in your `.env` file (root and/or `docker/stimm/.env`).
2. Restart the Stimm backend (or the whole Docker Compose stack).

## Configuring SIP Trunks

A SIP trunk defines how LiveKit accepts incoming calls. You can create a trunk using the provided script:

```bash
uv run python scripts/sip_integration/create_sip_trunk.py
```

This script stores the trunk configuration in Redis. You can list existing trunks with:

```bash
uv run python scripts/sip_integration/update_trunk.py
```

To update a trunk’s phone number or allowed addresses:

```bash
uv run python scripts/sip_integration/update_trunk.py --trunk-id <ID> --number +1234567
```

Or use the shell wrapper:

```bash
./scripts/sip_integration/update_trunk.sh --trunk-id <ID> --number +1234567
```

## Configuring Dispatch Rules

Dispatch rules determine which agent answers a call based on the called number. The rules are stored in Redis under the key `sip_dispatch_rules`.

To set up a rule that routes calls to `+1234567` to agent `support`:

```bash
uv run python scripts/sip_integration/sip-dispatch-config.py
```

The script will guide you through interactive rule creation. Alternatively, you can edit the Redis key directly.

## Making a Test Call

1. Ensure all services are running (`docker compose up`).
2. Use a SIP client (e.g., MicroSIP, Linphone) to dial the phone number you configured (e.g., `+1234567`).
3. The call should be answered by the default agent (or the agent specified in dispatch rules).

## Monitoring

### Health Endpoints

- `GET /health/sip‑bridge` – Basic health check (enabled/running status).
- `GET /health/sip‑bridge‑status` – Detailed status (active rooms, agent processes, errors).

### Logs

SIP bridge logs are written with the `SIP` prefix. You can view them with:

```bash
docker logs stimm‑app | grep SIP
```

## Cleaning Up Stale Rooms

If a call ends abruptly, rooms may remain in LiveKit. You can clean them up using the CLI:

```bash
# List all LiveKit rooms
uv run python -m src.cli.main livekit list-rooms

# Delete all SIP rooms and terminate agent processes
uv run python -m src.cli.main livekit clear-sip-bridge

# Delete all LiveKit rooms (SIP and non‑SIP)
uv run python -m src.cli.main livekit clear-rooms
```

## Advanced Configuration

### SIP Server Settings

The LiveKit SIP server is configured via `sip‑server‑config.yaml`. Refer to the [LiveKit SIP documentation](https://docs.livekit.io/guides/sip) for advanced options (codecs, DTMF, encryption, etc.).

### Custom Agent per Number

You can modify the dispatch rules to route different numbers to different agents. The SIP bridge reads the `agent_name` from the rule and spawns that specific agent.

### Fallback Agent

If no dispatch rule matches the called number, the SIP bridge uses a default agent (configurable via environment variable `DEFAULT_SIP_AGENT`). If that variable is not set, it uses the first agent found in the database.

## Troubleshooting

- **“No agent spawned”**: Check that `ENABLE_SIP_BRIDGE=true` and that there is at least one agent in the database.
- **“Call rejected”**: Verify that the SIP trunk is correctly configured and that the caller’s IP is allowed.
- **“One‑way audio”**: Ensure your network allows bidirectional UDP traffic on the RTP ports (50000‑60000 by default).
- **“High latency”**: Consider using a media server closer to the caller or enabling OPUS low‑bitrate codec.

## Next Steps

- Learn about [Managing Agents](managing‑agents.md) to create specialized agents for phone support.
- Explore the [Architecture](../developer‑guide/architecture‑overview.md) to understand how SIP fits into the overall system.
- Read the [LiveKit SIP documentation](https://docs.livekit.io/guides/sip) for advanced telephony features.
