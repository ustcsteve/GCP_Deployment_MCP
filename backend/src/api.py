import logging
import os
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.staticfiles import StaticFiles
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.genai import types
from dotenv import load_dotenv
from google.oauth2.id_token import verify_oauth2_token
from pydantic import BaseModel, Field

from backend.src.agent import build_agent

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

APP_NAME = "financial-analytics"
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
session_service = InMemorySessionService()

app = FastAPI(title="FinMarket Intelligence API", version="1.0.0")
demo_mode = os.getenv("DEMO_MODE", "false").strip().lower() == "true"


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: str | None = None


class ChatResponse(BaseModel):
    response: str
    session_id: str


def require_google_user(authorization: str | None = Header(default=None)) -> dict:
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=503,
            detail="Google Sign-In is not configured for this service.",
        )
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Sign in with Google to continue.")

    token = authorization.removeprefix("Bearer ").strip()
    try:
        claims = verify_oauth2_token(
            token,
            GoogleAuthRequest(),
            audience=GOOGLE_CLIENT_ID,
        )
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Google sign-in token is invalid or expired.") from exc

    email = str(claims.get("email", "")).lower()
    if claims.get("email_verified") is not True or not email.endswith("@gmail.com"):
        raise HTTPException(
            status_code=403,
            detail="Use a verified Gmail account to access FinMarket.",
        )
    if not claims.get("sub"):
        raise HTTPException(status_code=401, detail="Google sign-in token has no user identity.")
    return claims


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "mode": "demo" if demo_mode else "live"}


@app.get("/api/auth/config")
async def auth_config() -> dict[str, str]:
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=503,
            detail="Set GOOGLE_CLIENT_ID to a Web application OAuth client ID.",
        )
    return {"client_id": GOOGLE_CLIENT_ID}


@app.get("/api/auth/me")
async def auth_me(user: dict = Depends(require_google_user)) -> dict[str, str]:
    return {
        "email": user["email"],
        "name": user.get("name", user["email"]),
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    user: dict = Depends(require_google_user),
) -> ChatResponse:
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="Message cannot be blank")

    user_id = user["sub"]
    try:
        session = None
        if request.session_id:
            session = await session_service.get_session(
                app_name=APP_NAME,
                user_id=user_id,
                session_id=request.session_id,
            )
        if session is None:
            session = await session_service.create_session(
                app_name=APP_NAME,
                user_id=user_id,
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
            user_id=user_id,
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