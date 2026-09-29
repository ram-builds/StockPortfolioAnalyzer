"""
news_fetcher.py
Pulls latest Indian stock market headlines from free RSS feeds (no API key
needed) and filters them by stock/company name for relevance.

Swap in a paid API (NewsAPI, Marketaux, etc.) later if you want deeper
coverage or sentiment scores - just change fetch_latest_news().
"""

import feedparser

RSS_FEEDS = {
    "Economic Times Markets": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "Moneycontrol Markets": "https://www.moneycontrol.com/rss/marketreports.xml",
    "Livemint Markets": "https://www.livemint.com/rss/markets",
    "Business Standard Markets": "https://www.business-standard.com/rss/markets-106.rss",
}

# Map NSE symbols to extra keywords/company names to catch more mentions
SYMBOL_ALIASES = {
    "RELIANCE": ["reliance", "ril", "mukesh ambani", "jio"],
    "TCS": ["tcs", "tata consultancy"],
    "INFY": ["infosys", "infy"],
    "HDFCBANK": ["hdfc bank", "hdfcbank"],
}


def fetch_latest_news(limit_per_feed: int = 15) -> list:
    """Fetch recent headlines across all configured RSS feeds."""
    all_items = []
    for source, url in RSS_FEEDS.items():
        try:
            parsed = feedparser.parse(url)
        except Exception as e:
            print(f"Warning: could not fetch {source}: {e}")
            continue

        for entry in parsed.entries[:limit_per_feed]:
            all_items.append({
                "source": source,
                "title": entry.get("title", ""),
                "summary": entry.get("summary", ""),
                "link": entry.get("link", ""),
                "published": entry.get("published", ""),
            })
    return all_items


def filter_news_for_symbol(news_items: list, symbol: str) -> list:
    """Return only headlines that mention the given stock symbol or its aliases."""
    keywords = [symbol.lower()] + SYMBOL_ALIASES.get(symbol.upper(), [])
    matches = []
    for item in news_items:
        text = (item["title"] + " " + item["summary"]).lower()
        if any(kw in text for kw in keywords):
            matches.append(item)
    return matches


def get_general_market_headlines(news_items: list, limit: int = 10) -> list:
    """Return the top N general headlines (macro/index-level news)."""
    return news_items[:limit]


if __name__ == "__main__":
    items = fetch_latest_news()
    print(f"Fetched {len(items)} headlines total\n")
    for sym in SYMBOL_ALIASES:
        matched = filter_news_for_symbol(items, sym)
        print(f"{sym}: {len(matched)} relevant headlines")
        for m in matched[:3]:
            print(f"  - {m['title']}")
