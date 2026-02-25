#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[stimm] Local dev build starting..."

echo "[stimm] Building @stimm/protocol (TypeScript)..."
cd "$ROOT_DIR/packages/protocol-ts"
npm install
npm run build

echo "[stimm] Validating provider catalogs..."
cd "$ROOT_DIR"
python3 scripts/sync_livekit_plugins.py
python3 scripts/validate_runtime_contract.py

echo "[stimm] Local dev build completed."
