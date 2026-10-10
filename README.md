# FinMarket Intelligence

I’ll summarize the current workspace rather than relying on earlier layout assumptions. I’ll check the active README, backend entrypoints, MCP implementation, frontend, and root build/dependency files; I’ll avoid repeating any values from `.env`.

Read 

Read 

Read 

Read 

Read 

Read 

Read 

**Architecture**
```mermaid
flowchart LR
  User[User] --> UI[React frontend]
  UI -->|Google ID token + chat| API[FastAPI]
  API -->|verify token, manage session| Auth[Google Identity Services]
  API --> Agent[Google ADK agent workflow]
  Agent -->|inference| Gemini[Gemini on Vertex AI]
  Agent -->|Streamable HTTP tools| MCP[FastMCP service on Cloud Run]
  MCP --> Market[Alpha Vantage]
  Agent -. optional background .-> Wiki[Wikipedia]
```

The API verifies Google ID tokens server-side, permits verified Gmail accounts, and associates ADK sessions with each user. The agent researches with MCP tools and optional Wikipedia context, then formats a response. Wikipedia failures are handled as optional context so they don’t abort the workflow.

**Tech Stack**
- Frontend: React 19, TypeScript, Vite, Google Identity Services, React Markdown with GFM tables.
- Backend: Python 3.13, FastAPI, Google ADK, Google Auth, FastMCP, HTTPX.
- Model and data: Gemini on Vertex AI, Alpha Vantage, Wikipedia.
- Deployment: One multi-stage Docker image builds the UI and backend; Cloud Run runs it as two services, with different commands for the API and MCP server. Dependencies are managed with `uv` and npm lockfiles.
- Google login is implemented is active on Cloud Run.


<img width="1699" height="946" alt="Screenshot 2026-10-10 at 7 44 12 PM" src="https://github.com/user-attachments/assets/f3f0f9c3-0fc1-42a0-966f-1c56d3637c1f" />
<img width="1697" height="946" alt="Screenshot 2026-10-10 at 7 44 39 PM" src="https://github.com/user-attachments/assets/ad585743-1a64-4c81-bdee-fa2ec1f09395" />
