#!/usr/bin/env bash
# ==============================================================================
# Personal Job Agent - Automated Release Gate & Quality Verification
# Inspired by production engineering standards in iyov-ai
# ==============================================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python3}"

cd "$ROOT_DIR"

echo "=========================================================="
echo "🛡️  RUNNING PRE-RELEASE & DEPLOYMENT GATE: PROJECT VERONICA"
echo "=========================================================="

# 1. Verify sensitive files are not exposed
echo "👉 Checking secret containment and .dockerignore rules..."
if git status --porcelain | grep -E '^\s*(\?\?|M|A)\s+\.env$' > /dev/null; then
    echo "❌ ERROR: .env is tracked or staged in git! Unstage it before proceeding."
    exit 1
fi

if [[ ! -f ".dockerignore" ]] || ! grep -q '\.env' ".dockerignore"; then
    echo "❌ ERROR: .dockerignore is missing or does not exclude .env files."
    exit 1
fi
echo "✅ Secrets containment verified."

# 2. Syntax & bytecode compilation check
echo "👉 Verifying Python syntax and compiling packages..."
"$PYTHON_BIN" -m compileall -q app tests
echo "✅ Compilation successful with 0 bytecode errors."

# 3. Run full automated test suite
echo "👉 Running pytest suite..."
"$PYTHON_BIN" -m pytest -v
echo "✅ All unit and integration test assertions passed."

# 4. Live API smoke test
echo "👉 Executing ASGI smoke test on core endpoints..."
"$PYTHON_BIN" -c "
import asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.database import init_db

async def smoke():
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as ac:
        endpoints = [
            ('GET', '/'),
            ('HEAD', '/'),
            ('GET', '/health'),
            ('HEAD', '/health'),
            ('GET', '/settings'),
            ('GET', '/trace')
        ]
        for method, path in endpoints:
            r = await ac.request(method, path)
            assert r.status_code == 200, f'Endpoint {method} {path} returned {r.status_code}'
            print(f'   ✓ {method:<4} {path:<10} -> 200 OK')

asyncio.run(smoke())
"
echo "✅ Core endpoints verified healthy."

echo "=========================================================="
echo "🎉 RELEASE GATE PASSED: Code is clean and production ready"
echo "=========================================================="

