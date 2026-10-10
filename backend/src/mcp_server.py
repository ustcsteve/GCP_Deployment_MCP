import asyncio
import logging
import os
import re
from pathlib import Path
from typing import Dict, Any, List

import httpx
from dotenv import load_dotenv
from fastmcp import FastMCP

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

logger = logging.getLogger(__name__)
logging.basicConfig(format="[%(levelname)s]: %(message)s", level=logging.INFO)

mcp = FastMCP("FinMarket Intelligence Server 📈")

ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")

@mcp.tool()
async def get_stock_price(ticker: str) -> Dict[str, Any]:
    """
    Retrieves the real-time stock price and daily performance metrics for a given equity ticker.
    Use this when the user asks about current asset valuations, pricing data, or daily trends.
    
    Args:
        ticker: The stock market ticker symbol (e.g., 'AAPL', 'GOOGL', 'TSLA').
    """
    ticker = ticker.strip().upper()
    if not re.fullmatch(r"[A-Z0-9.\-]{1,15}", ticker):
        return {"error": "Provide a valid stock ticker symbol."}
    if not ALPHA_VANTAGE_API_KEY:
        return {"error": "The market data API key is not configured."}

    url = "https://www.alphavantage.co/query"
    params = {
        "function": "GLOBAL_QUOTE",
        "symbol": ticker,
        "apikey": ALPHA_VANTAGE_API_KEY,
    }
    logger.info("Fetching market quote for %s", ticker)

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            quote = data.get("Global Quote", {})
            if not quote:
                reason = data.get("Note") or data.get("Information")
                if reason:
                    return {"error": reason}
                return {"error": f"No quote returned for ticker '{ticker}'."}

            return {
                "symbol": quote.get("01. symbol"),
                "current_price": float(quote.get("05. price", 0)),
                "high": float(quote.get("03. high", 0)),
                "low": float(quote.get("04. low", 0)),
                "volume": int(quote.get("06. volume", 0)),
                "latest_trading_day": quote.get("07. latest trading day"),
                "change_percent": quote.get("10. change percent")
            }
        except Exception:
            logger.exception("Failed to fetch market data")
            return {"error": "Internal server error fetching real-time data."}

@mcp.tool()
async def evaluate_portfolio_risk(holdings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculates basic sector allocation balance and structural risk flags for a list of holdings.
    
    Args:
        holdings: A list of dicts, each containing 'ticker', 'shares', and 'sector'.
                  Example: [{"ticker": "AAPL", "shares": 10, "sector": "Tech"}]
    """
    sector_counts: Dict[str, int] = {}
    for holding in holdings:
        sector = str(holding.get("sector") or "Unspecified").strip()
        sector_counts[sector] = sector_counts.get(sector, 0) + 1

    total_assets = len(holdings)
    sector_position_percentages = {
        sector: round(count / total_assets * 100, 2)
        for sector, count in sector_counts.items()
    } if total_assets else {}
    concentrated_sectors = [
        sector
        for sector, percentage in sector_position_percentages.items()
        if percentage > 50
    ]
    return {
        "total_tracked_assets": total_assets,
        "methodology": "Position-count share by sector; not market-value weighted.",
        "sector_position_percentages": sector_position_percentages,
        "high_concentration_sectors": concentrated_sectors,
    }

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    logger.info(f"🚀 FinMarket MCP server started on port {port}")
    asyncio.run(
        mcp.run_async(
            transport="http",
            host="0.0.0.0",
            port=port,
            path="/mcp",
        )
    )
