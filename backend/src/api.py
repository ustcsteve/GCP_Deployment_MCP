import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from backend.src.agent import build_agent

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

APP_NAME = "financial-analytics"
USER_ID = "web-user"
session_service = InMemorySessionService()

app = FastAPI(title="FinMarket Intelligence API", version="1.0.0")
demo_mode = os.getenv("DEMO_MODE", "false").strip().lower() == "true"


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: str | None = None


class ChatResponse(BaseModel):
    response: str
    session_id: str


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "mode": "demo" if demo_mode else "live"}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="Message cannot be blank")

    try:
        session = None
        if request.session_id:
            session = await session_service.get_session(
                app_name=APP_NAME,
                user_id=USER_ID,
                session_id=request.session_id,
            )
        if session is None:
            session = await session_service.create_session(
                app_name=APP_NAME,
                user_id=USER_ID,
            )

        if demo_mode:
            return ChatResponse(
                response=(
                    "DEMO MODE: This is a sample response for testing the chat UI. "
                    "It contains no live market data or financial analysis.\n\n"
                    f"Your prompt: {message}\n\n"
                    "No Gemini request or MCP tool call was made."
                ),
                session_id=session.id,
            )

        agent, mcp_toolset = build_agent()
    except Exception as exc:
        logger.exception("Agent setup failed")
        raise HTTPException(
            status_code=503,
            detail="The agent is not configured or its MCP service is unavailable.",
        ) from exc

    response_text = ""
    try:
        runner = Runner(
            agent=agent,
            app_name=APP_NAME,
            session_service=session_service,
        )
        async for event in runner.run_async(
            user_id=USER_ID,
            session_id=session.id,
            new_message=types.Content(
                role="user",
                parts=[types.Part(text=message)],
            ),
        ):
            if event.is_final_response() and event.content:
                response_text = "".join(
                    part.text or ""
                    for part in event.content.parts or []
                    if getattr(part, "text", None)
                )
    except Exception as exc:
        logger.exception("Agent request failed")
        raise HTTPException(
            status_code=502,
            detail="The agent could not complete this request.",
        ) from exc
    finally:
        try:
            await mcp_toolset.close()
        except Exception:
            logger.exception("Failed to close the MCP toolset")

    if not response_text:
        raise HTTPException(status_code=502, detail="The agent returned no response.")
    return ChatResponse(response=response_text, session_id=session.id)


FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if FRONTEND_DIST.is_dir():
    app.mount(
        "/",
        StaticFiles(directory=FRONTEND_DIST, html=True),
        name="frontend",
    )