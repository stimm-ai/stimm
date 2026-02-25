---
id: integrations-agent-md
title: Agent Integration Contract
---

`AGENT.md` defines the expected behavior for AI agents integrating Stimm.

- Use public APIs from `stimm` for wizard and install logic.
- Keep provider discovery separate from runtime instantiation.
- Persist only provider IDs and parameter values.
- Never persist runtime module paths or constructors.

See the root contract: `AGENT.md`.
