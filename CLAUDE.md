# Upri setup instructions for coding agents

Read README.md, docs/standalone.md and docs/standalone-verification.md first.
The intended architecture is **one user's computer**: API, dashboard, SQLite,
MCP client and (where supported/experimental) local desktop application.
Do not substitute a remote Ubuntu/Windows PC. Detect the actual host OS;
a Cowork VM/cloud shell is not evidence of installing on the user's Mac.

Use `uv sync --frozen --python 3.12`, then scripts/local.py setup/serve/doctor.
Preserve existing data and MCP host configuration. Loopback is the default;
LAN binding is opt-in. Never print connection.json, API keys or member credentials.
Run scripts/smoke.py only with its own synthetic temporary database.

For desktop.py, inspect prerequisites and supplier terms before using
--accept-experimental. Use official downloads and pinned verification.
Do not weaken authentication, disable Gatekeeper globally, reuse another
machine's PC ID, or copy a preinstalled Windows/.NET environment from another PC.
Stop at owner-only credentials and report what was actually verified.
Do not issue real shipping data or print a physical label without explicit intent.
Existing Wine prefixes are never reset: failed installations retain logs and data.

Verification: `uv run pytest`; the cross-OS CI subset is
`uv run pytest tests/test_api.py tests/test_dashboard.py tests/test_local_setup.py`.
The fresh desktop installer requires successful DB, identity and real
registration-window probes. A successful installer exit or a demo PDF does not
prove carrier authentication, official label validity or print completion.
