#!/usr/bin/env python3
"""Install only the small MCP client; Python 3.9+, no package downloads."""
import argparse
import getpass
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import urllib.parse

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--host", required=True, help="REST service URL")
parser.add_argument("--token-stdin", action="store_true")
parser.add_argument("--directory", type=Path, default=Path.home() / ".local/share/upri-client")
args = parser.parse_args()
url = urllib.parse.urlsplit(args.host)
if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password or url.path not in ("", "/") or url.query or url.fragment:
    parser.error("Provide an HTTP(S) origin URL")
token = sys.stdin.readline().strip() if args.token_stdin else getpass.getpass("Upri API token: ")
if len(token) < 32:
    parser.error("Token must be at least 32 characters")
directory = args.directory.expanduser().resolve()
directory.mkdir(parents=True, exist_ok=True, mode=0o700)
os.chmod(directory, 0o700)
def atomic_write(destination, data):
    fd, temp = tempfile.mkstemp(prefix=".upri-", dir=directory)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(temp, destination)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)

for name in ("upri_mcp.py", "batch.schema.json"):
    atomic_write(directory / name, (Path(__file__).parent / name).read_bytes())
config = directory / "connection.json"
atomic_write(config, json.dumps({"url": args.host.rstrip("/"), "token": token}).encode())
snippet = {"mcpServers": {"upri": {"command": sys.executable,
    "args": [str(directory / "upri_mcp.py"), "--config", str(config)]}}}
atomic_write(directory / "claude-config.snippet.json", (json.dumps(snippet, indent=2) + "\n").encode())
print("Installed client in " + str(directory))
print("Config snippet: " + str(directory / "claude-config.snippet.json"))
print("Merge mcpServers.upri into your agent configuration; existing configurations were not changed.")
print("Installed bytes: " + str(sum(p.stat().st_size for p in directory.iterdir() if p.is_file())))
