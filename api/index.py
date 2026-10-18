
import hashlib
import json
import re

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

app = FastAPI()

EMAIL = "22f3002265@ds.study.iitm.ac.in"
TOOL_NAME = "solve_challenge"

TOOL = {
    "name": TOOL_NAME,
    "description": "Compute the challenge response using the current HTTP request headers.",
    "inputSchema": {
        "type": "object",
        "properties": {},
    },
}


def rpc_result(request_id, result):
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": result,
    }


def rpc_error(request_id, code, message):
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


async def handle_mcp(request: Request):
    # Notifications have no JSON-RPC id and receive HTTP 202.
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(
            rpc_error(None, -32700, "Parse error"),
            status_code=400,
        )

    if not isinstance(payload, dict):
        return JSONResponse(
            rpc_error(None, -32600, "Invalid Request"),
            status_code=400,
        )

    method = payload.get("method")
    request_id = payload.get("id")
    params = payload.get("params") or {}

    # MCP initialize handshake
    if method == "initialize":
        result = {
            "protocolVersion": params.get(
                "protocolVersion", "2025-03-26"
            ),
            "capabilities": {
                "tools": {"listChanged": False}
            },
            "serverInfo": {
                "name": "challenge-mcp",
                "version": "1.0.0",
            },
        }
        return JSONResponse(rpc_result(request_id, result))

    # notifications/initialized and other notifications
    if method == "notifications/initialized":
        return Response(status_code=202)

    if method == "ping":
        return JSONResponse(rpc_result(request_id, {}))

    # Exactly one exposed tool
    if method == "tools/list":
        return JSONResponse(
            rpc_result(request_id, {"tools": [TOOL]})
        )

    if method == "tools/call":
        if not isinstance(params, dict):
            return JSONResponse(
                rpc_error(request_id, -32602, "Invalid params"),
                status_code=400,
            )

        if params.get("name") != TOOL_NAME:
            return JSONResponse(
                rpc_error(request_id, -32602, "Unknown tool"),
                status_code=400,
            )

        # Read the challenge from THIS HTTP request's headers.
        challenge = request.headers.get("X-Exam-Challenge", "")

        if not re.fullmatch(r"[0-9a-f]{32}", challenge):
            result = {
                "content": [
                    {
                        "type": "text",
                        "text": "Missing or invalid X-Exam-Challenge header",
                    }
                ],
                "isError": True,
            }
            return JSONResponse(rpc_result(request_id, result))

        normalized_email = EMAIL.strip().lower()
        message = f"{challenge}:{normalized_email}"
        answer = hashlib.sha256(
            message.encode("utf-8")
        ).hexdigest()[:16]

        result = {
            "content": [
                {"type": "text", "text": answer}
            ],
            "isError": False,
        }
        return JSONResponse(rpc_result(request_id, result))

    if method and method.startswith("notifications/"):
        return Response(status_code=202)

    return JSONResponse(
        rpc_error(request_id, -32601, "Method not found"),
        status_code=400,
    )


# Vercel rewrites /mcp to this function.
@app.post("/")
@app.post("/mcp")
async def mcp_endpoint(request: Request):
    return await handle_mcp(request)


@app.get("/")
@app.get("/mcp")
async def mcp_get():
    # This minimal server uses POST for MCP JSON-RPC messages.
    return JSONResponse(
        {"error": "Use POST for MCP requests"},
        status_code=405,
        headers={"Allow": "POST"},
    )
