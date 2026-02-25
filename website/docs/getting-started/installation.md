---
id: getting-started-installation
title: Installation
---

## Python + TypeScript

```bash
# Core package first
pip install stimm

# Then install user-selected providers only
pip install stimm[deepgram,openai]

# Optional: all providers
pip install stimm[all]

# Supervisor protocol client for Node.js
npm install @stimm/protocol
```

Provider plugins are installed in the integrator environment; Stimm does not vendor plugin code in the wheel.
