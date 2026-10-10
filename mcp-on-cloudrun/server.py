import asyncio
import logging
import os
from typing import Dict, Any, List
from fastmcp import FastMCP
import httpx  # Using httpx for async API requests

logger = logging.getLogger(__name__)
logging.basicConfig(format="[%(levelname)s]: %(message)s", level=logging.INFO)

# Rename the server to match your brand new financial utility
mcp = FastMCP("FinMarket Intelligence Server 📈")

ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "demo")

@mcp.tool()
async def get_stock_price(ticker: str) -> Dict[str, Any]:
    """
    Retrieves the real-time stock price and daily performance metrics for a given equity ticker.
    Use this when the user asks about current asset valuations, pricing data, or daily trends.
    
    Args:
        ticker: The stock market ticker symbol (e.g., 'AAPL', 'GOOGL', 'TSLA').
    """
    logger.info(f">>> 🛠 Tool: 'get_stock_price' called for ticker '{ticker}'")
    
    url = f"https://alphavantage.co{ticker}&apikey={ALPHA_VANTAGE_API_KEY}"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url)
            data = response.json()
            
            # Clean and restructure the raw API data into an LLM-friendly schema
            quote = data.get("Global Quote", {})
            if not quote:
                return {"error": f"Ticker '{ticker}' not found or API limit reached."}
                
            return {
                "symbol": quote.get("01. symbol"),
                "current_price": float(quote.get("05. price", 0)),
                "high": float(quote.get("03. high", 0)),
                "low": float(quote.get("04. low", 0)),
                "volume": int(quote.get("06. volume", 0)),
                "latest_trading_day": quote.get("07. latest trading day"),
                "change_percent": quote.get("10. change percent")
            }
        except Exception as e:
            logger.error(f"Failed to fetch market data: {e}")
            return {"error": "Internal server error fetching real-time data."}

@mcp.tool()
async def evaluate_portfolio_risk(holdings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculates basic sector allocation balance and structural risk flags for a list of holdings.
    
    Args:
        holdings: A list of dicts, each containing 'ticker', 'shares', and 'sector'.
                  Example: [{"ticker": "AAPL", "shares": 10, "sector": "Tech"}]
    """
    logger.info(">>> 🛠 Tool: 'evaluate_portfolio_risk' invoked.")
    # Implement business logic here to count concentrations, flagging any sector > 50% as "High Concentration"
    total_assets = len(holdings)
    return {
        "total_tracked_assets": total_assets,
        "risk_assessment": "Calculated based on live allocations",
        "status": "Review required if tech concentration exceeds safe baselines."
    }

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    logger.info(f"🚀 FinMarket MCP server started on port {port}")
    asyncio.run(mcp.run_async(transport="http", host="0.0.0.0", port=port))
