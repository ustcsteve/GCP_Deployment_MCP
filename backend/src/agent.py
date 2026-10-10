import logging
import os

from google.adk import Agent
from google.adk.agents import SequentialAgent
from google.adk.tools.mcp_tool.mcp_toolset import (
    MCPToolset,
    StreamableHTTPConnectionParams,
)
from google.adk.tools.tool_context import ToolContext
from google.auth.transport.requests import Request
from google.oauth2.id_token import fetch_id_token
from langchain_community.tools import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper


def add_prompt_to_state(tool_context: ToolContext, prompt: str) -> dict[str, str]:
    """Save the initial financial query in the current ADK session."""
    tool_context.state["PROMPT"] = prompt
    logging.info("Saved user prompt to agent state")
    return {"status": "success"}


def _mcp_headers(mcp_server_url: str) -> dict[str, str]:
    token = os.getenv("MCP_AUTH_TOKEN")
    if not token:
        audience = os.getenv("MCP_SERVER_AUDIENCE") or mcp_server_url.removesuffix(
            "/mcp"
        ).rstrip("/")
        token = fetch_id_token(Request(), audience)
    return {"Authorization": f"Bearer {token}"}


def search_company_background(query: str) -> str:
    """Search Wikipedia for company history or background context."""
    try:
        tool = WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper())
        return tool.run(query)
    except Exception:
        logging.warning("Wikipedia lookup failed; continuing without background context")
        return "Wikipedia is unavailable right now. Continue using other available sources."


def build_agent() -> tuple[Agent, MCPToolset]:
    """Build an ADK agent and its authenticated remote MCP toolset."""
    mcp_server_url = os.getenv("MCP_SERVER_URL")
    if not mcp_server_url:
        raise RuntimeError("MCP_SERVER_URL is required")

    mcp_tools = MCPToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=mcp_server_url,
            headers=_mcp_headers(mcp_server_url),
            timeout=15,
            sse_read_timeout=300,
        ),
        tool_filter=["get_stock_price", "evaluate_portfolio_risk"],
    )
    model_name = os.getenv("MODEL", "gemini-2.5-flash")
    market_researcher = Agent(
        name="market_researcher",
        model=model_name,
        description=(
            "Research equities using live market tools and background knowledge."
        ),
        instruction="""
        You are an expert financial research analyst. Thoroughly evaluate the user's
        PROMPT. Use the MCP tools for current prices and portfolio risk. Use
        Wikipedia for relevant company history or macroeconomic context, and combine
        the sources when both are useful. Clearly identify unavailable or stale data.

        PROMPT:
        {{ PROMPT }}
        """,
        tools=[mcp_tools, search_company_background],
        output_key="RESEARCH_DATA",
    )

    financial_formatter = Agent(
        name="financial_formatter",
        model=model_name,
        description="Format research into a concise investor-oriented summary.",
        instruction="""
        Turn RESEARCH_DATA into a concise, professional financial research summary.
        Lead with the asset identifiers and available market metrics, add relevant
        context, and state material risks objectively. Do not give definitive
        investment mandates. Do not invent missing prices, dates, or calculations.

        RESEARCH_DATA:
        {{ RESEARCH_DATA }}
        """,
    )

    workflow = SequentialAgent(
        name="market_intelligence_workflow",
        description="Research market data and format financial insights.",
        sub_agents=[market_researcher, financial_formatter],
    )
    root_agent = Agent(
        name="greeter",
        model=model_name,
        description="Financial market intelligence and portfolio tracking assistant.",
        instruction="""
        Introduce yourself as a market intelligence assistant. For each financial
        question, call add_prompt_to_state with the complete user request, then
        delegate the analysis to market_intelligence_workflow.
        """,
        tools=[add_prompt_to_state],
        sub_agents=[workflow],
    )
    return root_agent, mcp_tools
