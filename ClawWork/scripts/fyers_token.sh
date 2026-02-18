#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -f ".env" ]]; then
	set -a
	source .env
	set +a
fi

echo "🔐 Starting FYERS OAuth helper (interactive mode)"
echo "   Working directory: $ROOT_DIR"

python -m livebench.trading.fyers_oauth_helper interactive --open-browser --write-env

echo "✅ FYERS token flow completed"
