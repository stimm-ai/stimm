---
id: integrations-supervisor-observability
title: Supervisor Observability Integration
---

This document explains how to consume Stimm supervisor observability logs from an integration.

## Scope

Applies to logs emitted by `ConversationSupervisor` in `src/stimm/conversation_supervisor.py`.

The supervisor now emits machine-parseable JSON lines prefixed with `OBS_JSON`.

## Log line format

Each observability line looks like:

```text
... INFO ... OBS_JSON {"component":"conversation_supervisor","event":"inference_started",...}
```

Parsing rule:

1. Keep only lines containing `OBS_JSON ` (with trailing space).
2. Extract the substring after `OBS_JSON `.
3. Parse that substring as JSON.

## Event model

All events share these base fields:

- `component` (string): always `conversation_supervisor`
- `event` (string): event name
- `ts_ms` (int): Unix epoch timestamp in milliseconds
- `inference_seq` (int): monotonically increasing sequence per supervisor instance

### `inference_started`

When a supervisor inference starts.

Additional fields:

- `history_len` (int): number of turns currently in supervisor history
- `processed_up_to` (int): history index snapshot used for this inference

### `inference_completed`

When a supervisor inference returns and is parsed.

Additional fields:

- `latency_ms` (int): end-to-end backend latency measured by supervisor
- `structured_json` (bool): whether parsing indicates a structured JSON response
- `action` (string): parsed decision action (`TRIGGER` or `NO_ACTION`)
- `reason` (string): parse/backend reason (empty string when absent)

### `no_action`

Emitted when decision action is not `TRIGGER`.

No extra fields.

### `trigger_sent`

Emitted after a trigger is pushed to the voice agent context.

Additional fields:

- `text_chars` (int): trigger text length
- `preview` (string): first 120 chars of trigger text

## Correlation

Use `(component, inference_seq)` as the primary correlation key for one inference lifecycle:

- `inference_started`
- `inference_completed`
- optional `no_action` or `trigger_sent`

## Minimal state machine

For each `inference_seq`:

- On `inference_started`: create `running` record
- On `inference_completed`: store `latency_ms`, `structured_json`, `action`, `reason`
- On `trigger_sent`: mark outcome `triggered`
- On `no_action`: mark outcome `no_action`

## Practical alerts

You can implement simple counters/windows in your app logs processor:

- High `structured_json=false` ratio over last N inferences
- Missing terminal event (`trigger_sent`/`no_action`) after `inference_completed`
- Repeated high `latency_ms` outliers

## Python parsing example

```python
import json


def iter_supervisor_events(lines):
    marker = "OBS_JSON "
    for line in lines:
        idx = line.find(marker)
        if idx == -1:
            continue
        payload = line[idx + len(marker):].strip()
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if event.get("component") == "conversation_supervisor":
            yield event
```

## Node.js parsing example

```js
function* iterSupervisorEvents(lines) {
  const marker = 'OBS_JSON ';
  for (const line of lines) {
    const idx = line.indexOf(marker);
    if (idx === -1) continue;
    const payload = line.slice(idx + marker.length).trim();
    let evt;
    try {
      evt = JSON.parse(payload);
    } catch {
      continue;
    }
    if (evt.component === 'conversation_supervisor') {
      yield evt;
    }
  }
}
```

## Compatibility notes

- Unknown fields should be ignored by consumers.
- New event types may be added in the future; unknown `event` values should not break parsing.
- `preview` is informational only and should not be treated as full content.
