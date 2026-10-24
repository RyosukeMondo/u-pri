# Local MCP client

Run `uv run python scripts/local.py setup` at the repository root. This creates a
private connection file and `mcp/claude-config.snippet.json` under your OS's Upri
data directory. It connects to the API on **this same PC** at 127.0.0.1.
Merge the snippet into the MCP host configuration without replacing unrelated
servers, then restart/reload the host. Keep `local.py serve` running.

Tools: `upri_capabilities`, `upri_prepare_batch`, `upri_get_batch`, `upri_get_csv`.
No print tool is provided. CSV prepared does not mean label printed or carrier accepted.
Customer addresses returned by MCP may enter the AI model context; choose the
appropriate account for the data. Retry creates only with their original idempotency key.

The standalone client also supports an optional remote API via
`python client/install.py --host URL`; this is not needed for the local setup.
Credentials are entered privately and saved in a private connection file, not
embedded in the MCP configuration snippet. No automatic edits to host settings.
