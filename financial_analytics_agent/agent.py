import os
import logging
import google.cloud.logging
from dotenv import load_dotenv

from google.adk import Agent
from google.adk.agents import SequentialAgent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StreamableHTTPConnectionParams
from google.adk.tools.tool_context import ToolContext
from google.adk.tools.langchain_tool import LangchainTool

from langchain_community.tools import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper

import google.auth
import google.auth.transport.requests
import google.oauth2.id_token

# --- Setup Logging and Environment ---

cloud_logging_client = google.cloud.logging.Client()
cloud_logging_client.setup_logging()

load_dotenv()

model_name = os.getenv("MODEL")

# Save user query to state

def add_prompt_to_state(
    tool_context: ToolContext, prompt: str
) -> dict[str, str]:
    """Saves the user's initial financial query prompt to the workflow state."""
    tool_context.state["PROMPT"] = prompt
    logging.info(f"[State updated] Added to PROMPT: {prompt}")
    return {"status": "success"}


# --- Configuring the FinMarket MCP Tool Component ---

mcp_server_url = os.getenv("MCP_SERVER_URL")
if not mcp_server_url:
    raise ValueError("The environment variable MCP_SERVER_URL is not set.")

def get_id_token():
    """Get an ID token to authenticate securely with the Cloud Run MCP server."""
    target_url = os.getenv("MCP_SERVER_URL")
    audience = target_url.split('/mcp/')[0]
    request = google.auth.transport.requests.Request()
    id_token = google.oauth2.id_token.fetch_id_token(request, audience)
    return id_token

# Connects to your custom Cloud Run FinMarket server with GCP IAM token authentication
mcp_tools = MCPToolset(
    connection_params=StreamableHTTPConnectionParams(
        url=mcp_server_url,
        headers={
            "Authorization": f"Bearer {get_id_token()}",
        },
    ),
)

# Configuring the Wikipedia Tool for macro/historical background context
wikipedia_tool = LangchainTool(
    tool=WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper())
)


# --- Agent Definitions ---

# 1. Market Researcher Agent
market_researcher = Agent(
    name="market_researcher",
    model=model_name,
    description="The primary financial analyst with access to real-time market data over MCP and macro knowledge from Wikipedia.",
    instruction="""
    You are an expert financial research analyst. Your goal is to thoroughly evaluate the user's PROMPT.
    You have access to two specific tools:
    1. An MCP toolset for getting real-time market data (stock prices, valuations, volumes) and portfolio risk calculations.
    2. A Wikipedia tool for general historical knowledge, corporate backgrounds, and macroeconomic concepts.

    First, analyze the user's PROMPT.
    - If the user is tracking an active stock or looking for dynamic market statistics, prioritize using the MCP tools.
    - If the query requires qualitative corporate history or foundational sector metrics alongside real-time asset pricing, you MUST combine data from both tools.
    - Synthesize the real-time financial stats with your background research into a structured preliminary summary.

    PROMPT:
    {{ PROMPT }}
    """,
    tools=[
        mcp_tools,
        wikipedia_tool
    ],
    output_key="RESEARCH_DATA"  # Stores data metrics for the next agent step
)

# 2. Financial Insights Formatter Agent
financial_formatter = Agent(
    name="financial_formatter",
    model=model_name,
    description="Synthesizes complex quantitative market outputs into crisp, professional investor summaries.",
    instruction="""
    You are a professional, high-signal Financial Market Intelligence Assistant. 
    Your task is to take the raw corporate and price data inside RESEARCH_DATA and package it into a scannable, executive summary.

    Structure your delivery with the following rules:
    - **Market Performance Metrics First**: Bold key asset identifiers, ticker symbols, and current pricing data cleanly.
    - **Macro Context**: Supplement the raw metrics with relevant operational or historical insights uncovered during research.
    - **Risk & Actionability**: Highlight performance changes or concentration flags objectively without offering definitive investment mandates.
    - Keep your tone concise, analytical, and professional.

    RESEARCH_DATA:
    {{ RESEARCH_DATA }}
    """
)

# --- Workflow Orchestration ---

market_intelligence_workflow = SequentialAgent(
    name="market_intelligence_workflow",
    description="The multi-agent workflow for analyzing equities and portfolio data structures.",
    sub_agents=[
        market_researcher,  # Step 1: Query API & fetch background context
        financial_formatter, # Step 2: Clean metrics into consumer-ready format
    ]
)

root_agent = Agent(
    name="greeter",
    model=model_name,
    description="The greeting gateway for the Financial Market Intelligence workflow.",
    instruction="""
    - Introduce yourself to the user as a real-time Market Intelligence & Portfolio Tracking workflow assistant.
    - When the user asks their investment or stock tracking question, execute 'add_prompt_to_state' to safely capture their request.
    - After saving the input, immediately transition orchestration to the 'market_intelligence_workflow' multi-agent system.
    """,
    tools=[add_prompt_to_state],
    sub_agents=[market_intelligence_workflow]
)
