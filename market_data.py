"""
market_data.py
Fetches live/latest market data for NSE-listed stocks using yfinance.

NSE tickers on Yahoo Finance need a ".NS" suffix, e.g. RELIANCE -> RELIANCE.NS

Broker exports don't always give a clean ticker - some (like Groww) give the
full company name ("IRCON INTERNATIONAL LTD") instead of the symbol
("IRCON"). If a direct ticker lookup fails, we fall back to Yahoo Finance's
search to resolve the company name to its actual NSE symbol.
"""

import yfinance as yf


def _resolve_to_nse_symbol(query: str) -> str | None:
    """
    Try to resolve a company name (or a symbol that didn't work directly)
    to its actual NSE ticker symbol using Yahoo Finance search.

    Returns the bare symbol (no .NS suffix) or None if nothing matched.
    """
    try:
        results = yf.Search(query, max_results=10, raise_errors=False)
        quotes = results.quotes or []
    except Exception:
        return None

    # Prefer an NSE (India) listing - Yahoo tags these with exchange "NSI"
    # or a symbol ending in .NS
    for q in quotes:
        symbol = q.get("symbol", "")
        exchange = q.get("exchange", "")
        if exchange == "NSI" or symbol.endswith(".NS"):
            return symbol.replace(".NS", "")

    return None


def get_stock_data(symbol: str) -> dict:
    """
    Fetch current market data for a single NSE stock. Accepts either a
    plain ticker ("RELIANCE") or a full company name ("Reliance Industries
    Ltd") - it will try the direct ticker first, then fall back to a name
    search if that fails.

    Args:
        symbol: NSE symbol or company name as it appeared on the broker statement

    Returns:
        dict with current_price, day_change_pct, week52_high, week52_low,
        pe_ratio, market_cap, sector. Missing fields are set to None.
        Includes "resolved_symbol" and "resolved_from_name" when a name
        search was needed, so the caller can show what was matched.
    """
    data = _fetch_ticker_info(symbol)
    if not data.get("error"):
        return data

    # Direct lookup failed - try resolving via company name search
    resolved = _resolve_to_nse_symbol(symbol)
    if resolved:
        data = _fetch_ticker_info(resolved)
        if not data.get("error"):
            data["resolved_symbol"] = resolved
            data["resolved_from_name"] = symbol
            return data

    return {"symbol": symbol, "error": f"No data returned - check symbol spelling (tried resolving '{symbol}' too)"}


def _fetch_ticker_info(symbol: str) -> dict:
    ticker_symbol = f"{symbol.upper()}.NS"
    ticker = yf.Ticker(ticker_symbol)

    try:
        info = ticker.info
    except Exception as e:
        return {"symbol": symbol, "error": f"Failed to fetch data: {e}"}

    # yfinance sometimes returns an empty/partial dict for delisted or
    # mistyped symbols - guard against that.
    if not info or info.get("regularMarketPrice") is None:
        return {"symbol": symbol, "error": "No data returned - check symbol spelling"}

    current_price = info.get("regularMarketPrice") or info.get("currentPrice")
    prev_close = info.get("regularMarketPreviousClose") or info.get("previousClose")

    day_change_pct = None
    if current_price is not None and prev_close:
        day_change_pct = round(((current_price - prev_close) / prev_close) * 100, 2)

    return {
        "symbol": symbol,
        "current_price": current_price,
        "day_change_pct": day_change_pct,
        "week52_high": info.get("fiftyTwoWeekHigh"),
        "week52_low": info.get("fiftyTwoWeekLow"),
        "pe_ratio": info.get("trailingPE"),
        "market_cap": info.get("marketCap"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
    }


def get_portfolio_market_data(symbols: list) -> dict:
    """Fetch market data for a list of symbols. Returns {symbol: data_dict}."""
    return {symbol: get_stock_data(symbol) for symbol in symbols}


if __name__ == "__main__":
    # Quick manual test
    for sym in ["RELIANCE", "TCS", "INFY"]:
        print(get_stock_data(sym))
