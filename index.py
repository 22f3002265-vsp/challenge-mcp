
import hashlib
import re

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

app = FastAPI()

EMAIL = "22f3002265@ds.study.iitm.ac.in"

TOOL = {
    "name": "solve_challenge",
    "description": "Calculate the response for the current exam challenge.",
    "inputSchema": {
        "type": "object",
        "properties": {},
    },
}


def rpc(request_id, result):
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": result,
    }


def error(request_id, code, message):
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


@app.get("/")
async def health():
    return {"status": "ok"}


@app.post("/mcp")
async def mcp_endpoint(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(error(None, -32700, "Parse error"), status_code=400)

    if not isinstance(body, dict) or body.get("jsonrpc") != "2.0":
        return JSONResponse(error(None, -32600, "Invalid Request"), status_code=400)

    method = body.get("method")
    request_id = body.get("id")
    params = body.get("params") or {}

    if method == "initialize":
        return JSONResponse(rpc(request_id, {
            "protocolVersion": params.get("protocolVersion", "2025-03-26"),
            "capabilities": {"tools": {}},
            "serverInfo": {
                "name": "challenge-mcp",
                "version": "1.0.0",
            },
        }))

    if method == "notifications/initialized":
        return Response(status_code=202)

    if method == "ping":
        return JSONResponse(rpc(request_id, {}))

    if method == "tools/list":
        return JSONResponse(rpc(request_id, {"tools": [TOOL]}))

    if method == "tools/call":
        if params.get("name") != "solve_challenge":
            return JSONResponse(
                error(request_id, -32602, "Unknown tool"),
                status_code=400,
            )

        # Always use the challenge from the current HTTP request headers.
        challenge = request.headers.get("X-Exam-Challenge", "")

        if not re.fullmatch(r"[0-9a-f]{32}", challenge):
            return JSONResponse(rpc(request_id, {
                "content": [{
                    "type": "text",
                    "text": "Missing or invalid X-Exam-Challenge header",
                }],
                "isError": True,
            }))

        normalized_email = EMAIL.strip().lower()
        digest = hashlib.sha256(
            f"{challenge}:{normalized_email}".encode("utf-8")
        ).hexdigest()[:16]

        return JSONResponse(rpc(request_id, {
            "content": [{"type": "text", "text": digest}],
            "isError": False,
        }))

    if isinstance(method, str) and method.startswith("notifications/"):
        return Response(status_code=202)

    return JSONResponse(
        error(request_id, -32601, "Method not found"),
        status_code=400,
    )
