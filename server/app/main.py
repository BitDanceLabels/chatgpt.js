import asyncio
import sys
import time
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .chatgpt import build_controller
from .schemas import AskRequest, AskResponse, StatusResponse

# Ensure subprocess support for Playwright on Windows
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


app = FastAPI(title="chatgpt.js FastAPI bridge", version="0.1.0")
controller = build_controller()

# Allow local testing; tighten origins in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event() -> None:
    await controller.start()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await controller.shutdown()


@app.get("/status", response_model=StatusResponse)
async def status() -> Any:
    return await controller.status()


@app.post("/ask", response_model=AskResponse)
async def ask(body: AskRequest) -> Any:
    started = time.perf_counter()
    reply = await controller.ask(body.prompt, timeout=body.timeout or 60)
    duration_ms = int((time.perf_counter() - started) * 1000)
    return AskResponse(reply=reply, duration_ms=duration_ms)


@app.post("/continue")
async def continue_last() -> dict[str, Any]:
    reply = await controller.continue_last()
    return {"reply": reply}


@app.post("/stop")
async def stop() -> dict[str, Any]:
    stopped = await controller.stop()
    return {"stopped": stopped}


@app.get("/history")
async def history() -> dict[str, Any]:
    data = await controller.history()
    return {"history": data}


@app.get("/last-reply")
async def last_reply() -> dict[str, Any]:
    reply = await controller.last_reply()
    return {"reply": reply}


@app.post("/clear")
async def clear() -> dict[str, Any]:
    cleared = await controller.clear()
    return {"cleared": cleared}


# Simple health endpoint to ensure server is alive (without hitting ChatGPT).
@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}
