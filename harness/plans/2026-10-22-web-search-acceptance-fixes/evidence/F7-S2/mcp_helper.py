"""Minimal stdio MCP helper for F7-S2 cases 13 and 14: python mcp_helper.py <healthy|hang_call|hang_start>"""
import json
import sys
import time

mode = sys.argv[1]
if mode == "hang_start":
    time.sleep(120)
for line in sys.stdin:
    message = json.loads(line)
    if "id" not in message:
        continue
    method = message["method"]
    if method == "initialize":
        result = {"protocolVersion": "2025-03-26", "capabilities": {"tools": {}}, "serverInfo": {"name": "helper", "version": "1"}}
    elif method == "tools/list":
        name = "local_probe" if mode == "healthy" else "get-single-web-page-content"
        result = {"tools": [{"name": name, "inputSchema": {"type": "object", "properties": {}}}]}
    else:
        if mode == "hang_call":
            time.sleep(120)
        result = {"content": [{"type": "text", "text": "helper result"}]}
    print(json.dumps({"jsonrpc": "2.0", "id": message["id"], "result": result}), flush=True)
