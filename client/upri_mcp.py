#!/usr/bin/env python3
"""Dependency-free stdio MCP client for a separately hosted Upri REST service.

Python 3.9+; does not install or launch Wine, printers, or the carrier application.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward the API token to a redirect target.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", help="REST base URL, e.g. http://127.0.0.1:18767")
    parser.add_argument("--config", type=Path, help="Private JSON with url and token")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding='utf-8')) if args.config else {}
    base = (args.host or os.environ.get("UPRI_URL") or config.get("url", "")).rstrip("/")
    token = os.environ.get("UPRI_API_TOKEN") or config.get("token", "")
    url = urllib.parse.urlsplit(base)
    if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password or url.query or url.fragment or url.path:
        parser.error("--host must be an http(s) origin without credentials, path, query or fragment")
    if len(token) < 32:
        parser.error("Provide API token through environment or private config")
    opener = urllib.request.build_opener(NoRedirect, urllib.request.ProxyHandler({}))
    schema = json.loads(Path(__file__).with_name("batch.schema.json").read_text(encoding='utf-8'))

    def tool(name, desc, properties, required=(), read_only=True, definitions=None):
        shape = {"type": "object", "properties": properties, "required": list(required), "additionalProperties": False}
        if definitions:
            shape["$defs"] = definitions
        return {"name": name, "description": desc, "inputSchema": shape,
                "annotations": {"readOnlyHint": read_only, "destructiveHint": False,
                                "idempotentHint": True, "openWorldHint": False}}

    batch_shape = {k: v for k, v in schema.items() if k != "$defs"}
    tools = [
        tool("upri_capabilities", "Check what the backend can actually do. Printing is not implemented.", {}),
        tool("upri_prepare_batch", "Prepare a CSV batch only; does NOT print or ship. Reuse the same idempotency key for retries. Confirm addresses with the user.",
             {"batch": batch_shape, "idempotency_key": {"type": "string", "minLength": 1, "maxLength": 128}},
             ("batch", "idempotency_key"), False, schema.get("$defs")),
        tool("upri_get_batch", "Read batch state. history_received is not evidence of delivery or printing.",
             {"batch_id": {"type": "string", "format": "uuid"}}, ("batch_id",)),
        tool("upri_get_csv", "Return the prepared CSV as text for review. Original download is CP932; this tool does not save or print it.",
             {"batch_id": {"type": "string", "format": "uuid"}}, ("batch_id",)),
    ]

    def call(name, arguments):
        definition = next((t for t in tools if t["name"] == name), None)
        if definition is None or not isinstance(arguments, dict):
            raise ValueError("Unknown tool or invalid arguments")
        shape = definition["inputSchema"]
        if set(arguments) - set(shape["properties"]) or set(shape["required"]) - set(arguments):
            raise ValueError("Unexpected or missing arguments")
        headers = {"Authorization": "Bearer " + token}
        data = None
        if name == "upri_capabilities":
            path = "/v1/capabilities"
        elif name == "upri_prepare_batch":
            key = arguments["idempotency_key"]
            if not isinstance(key, str) or not 1 <= len(key) <= 128 or not key.isascii() or any(ord(c) < 32 or ord(c) == 127 for c in key):
                raise ValueError("Invalid idempotency key")
            path = "/v1/batches"
            headers.update({"Idempotency-Key": key, "Content-Type": "application/json"})
            data = json.dumps(arguments["batch"]).encode()
        else:
            bid = str(uuid.UUID(arguments["batch_id"]))
            path = "/v1/batches/" + bid + ("/csv" if name == "upri_get_csv" else "")
        request = urllib.request.Request(base + path, data=data, headers=headers)
        with opener.open(request, timeout=20) as response:
            raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise ValueError("Response too large")
        text = raw.decode("cp932" if name == "upri_get_csv" else "utf-8")
        return {"content": [{"type": "text", "text": text}], "isError": False}

    initialized = False
    while True:
        line = sys.stdin.buffer.readline(1_000_001)
        if not line:
            return
        if len(line) > 1_000_000:
            return  # Oversized protocol input: close instead of losing framing.
        request = None
        try:
            request = json.loads(line)
            if not isinstance(request, dict) or request.get("jsonrpc") != "2.0" or not isinstance(request.get("method"), str):
                raise ValueError("Invalid JSON-RPC request")
            if "id" not in request:
                continue
            method = request["method"]
            params = request.get("params", {})
            if not isinstance(params, dict):
                raise ValueError("Invalid params")
            if method == "initialize":
                version = params.get("protocolVersion")
                if version not in ("2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"):
                    version = "2025-06-18"
                result = {"protocolVersion": version, "capabilities": {"tools": {}},
                          "serverInfo": {"name": "upri-csv-bridge", "version": "0.2.0"},
                          "instructions": "CSV preparation only. No label printing backend is verified. Never describe a prepared CSV as a printed label."}
                initialized = True
            elif method == "ping":
                result = {}
            elif not initialized:
                raise ValueError("Initialize first")
            elif method == "tools/list":
                result = {"tools": tools}
            elif method == "tools/call":
                try:
                    result = call(params.get("name"), params.get("arguments", {}))
                except urllib.error.HTTPError as exc:
                    result = {"content": [{"type": "text", "text": "Backend HTTP %s; check input or token. Retry with the SAME idempotency key." % exc.code}], "isError": True}
                except Exception:
                    result = {"content": [{"type": "text", "text": "Invalid input or backend unavailable. Outcome may be uncertain; retry only with the same idempotency key."}], "isError": True}
            else:
                print(json.dumps({"jsonrpc": "2.0", "id": request["id"], "error": {"code": -32601, "message": "Method not found"}}), flush=True)
                continue
            answer = {"jsonrpc": "2.0", "id": request["id"], "result": result}
        except (ValueError, TypeError):
            answer = {"jsonrpc": "2.0", "id": request.get("id") if isinstance(request, dict) else None,
                      "error": {"code": -32600, "message": "Invalid request"}}
        print(json.dumps(answer, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    main()
