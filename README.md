# FinMarket Intelligence

The workspace contains a React frontend and a Python backend package under `backend/src`.
The same backend image can run either the FastAPI agent API or the FastMCP service as
separate processes. The API calls the MCP service using `MCP_SERVER_URL`.

## Configure and run

For local demo mode, no Gemini credentials or running MCP service are required:

```sh
docker build -t finmarket-intelligence .
docker run --rm -p 8080:8080 -e DEMO_MODE=true finmarket-intelligence
```

The UI is served at `http://localhost:8080`; `GET /api/health` reports the service mode. The canned response is only for frontend testing.

To run both services locally, use separate terminals after building the image. Provide `ALPHA_VANTAGE_API_KEY` to the MCP process, and set `MCP_SERVER_URL=http://host.docker.internal:8081/mcp` for the API process:

```sh
docker run --rm -p 8081:8081 -e PORT=8081 -e ALPHA_VANTAGE_API_KEY="$ALPHA_VANTAGE_API_KEY" finmarket-intelligence python -m backend.src.mcp_server
docker run --rm -p 8080:8080 -e MCP_SERVER_URL=http://host.docker.internal:8081/mcp -e MCP_AUTH_TOKEN=local-dev-token finmarket-intelligence
```

For local source development, run `uv sync`, `npm ci --prefix frontend`, and `npm run dev --prefix frontend`; start the API with `uv run uvicorn backend.src.api:app --reload --port 8080`. Vite proxies `/api` requests to FastAPI.

## Deploy

Deploy the same root image as two Cloud Run services. The API service uses the image's default FastAPI command. Override the MCP service command to `python -m backend.src.mcp_server`, set `PORT=8080`, and provide `ALPHA_VANTAGE_API_KEY` using Secret Manager. Keep the MCP endpoint private and grant the API service account Cloud Run Invoker access to it. Protect the frontend/API with the access policy appropriate for your users.

```sh
gcloud run deploy finmarket-intelligence \
  --source . \
  --region us-west1 \
  --service-account "$SERVICE_ACCOUNT" \
  --set-env-vars "MODEL=gemini-2.5-flash,MCP_SERVER_URL=https://YOUR-MCP-SERVICE.run.app/mcp,GOOGLE_GENAI_USE_VERTEXAI=true,GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GOOGLE_CLOUD_LOCATION=us-west1"
```

## Google Sign-In

The frontend login uses Google Identity Services. Create a **Web application** OAuth client in Google Auth Platform, set its audience to External, and publish the consent app if any Gmail user should be allowed (Testing mode only permits listed test users). Add the deployed Cloud Run URL and `http://localhost:8080` as authorized JavaScript origins. The API verifies each Google ID token and only accepts verified `@gmail.com` accounts; it does not trust the frontend alone.

Set the public OAuth client ID when deploying the API:

```sh
gcloud run deploy financial-analytics-service \
  --source . \
  --project mcpcloudrun-511200 \
  --region us-west1 \
  --service-account finmarket-api@mcpcloudrun-511200.iam.gserviceaccount.com \
  --update-env-vars GOOGLE_CLIENT_ID=YOUR_WEB_CLIENT_ID
```

The OAuth client ID is public configuration, not a client secret. The React app only keeps the returned ID token in memory, and the API validates it before creating or continuing an agent session.

Conversation sessions currently use ADK's in-memory session service. They are lost when a Cloud Run instance restarts and are not shared between instances; use a persistent ADK session service before relying on cross-instance conversation continuity.