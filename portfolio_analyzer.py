"""
portfolio_analyzer.py
Main entry point. Reads your portfolio CSV, fetches live market data and
recent news per stock, and asks Gemini to produce a hold/reduce/increase
view with reasoning for each holding.

Setup:
    pip install -r requirements.txt
    export GEMINI_API_KEY=your_key_here     (get one free at aistudio.google.com)

Run:
    python portfolio_analyzer.py
"""

import os
import csv
from datetime import datetime

import google.genai as genai
from market_data import get_portfolio_market_data
from news_fetcher import fetch_latest_news, filter_news_for_symbol, get_general_market_headlines

MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")


def load_portfolio(csv_path: str = "portfolio.csv") -> list:
    holdings = []
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            holdings.append({
                "symbol": row["symbol"].strip().upper(),
                "quantity": float(row["quantity"]),
                "buy_price": float(row["buy_price"]),
                "buy_date": row["buy_date"].strip(),
            })
    return holdings


def build_portfolio_summary(holdings: list, market_data: dict) -> list:
    """Attach current value, P&L, P&L% to each holding."""
    summary = []
    for h in holdings:
        data = market_data.get(h["symbol"], {})
        current_price = data.get("current_price")
        row = dict(h)
        row.update(data)
        if current_price:
            invested = h["quantity"] * h["buy_price"]
            current_value = h["quantity"] * current_price
            row["invested_value"] = round(invested, 2)
            row["current_value"] = round(current_value, 2)
            row["pnl"] = round(current_value - invested, 2)
            row["pnl_pct"] = round(((current_value - invested) / invested) * 100, 2)
        summary.append(row)
    return summary


def build_prompt(portfolio_summary: list, news_items: list) -> str:
    lines = []
    lines.append("You are a portfolio analysis assistant helping a retail investor in India review their holdings.")
    lines.append("For EACH stock below, give a clear view: HOLD, REDUCE, INCREASE, or EXIT, with 2-3 sentences of reasoning")
    lines.append("that references the specific data and news given. Then give one short paragraph of overall portfolio commentary.")
    lines.append("Be balanced and mention risks/uncertainty. This is decision support, not financial advice.\n")

    lines.append("=== PORTFOLIO ===")
    for row in portfolio_summary:
        if row.get("error"):
            lines.append(f"- {row['symbol']}: ERROR fetching data ({row['error']})")
            continue
        lines.append(
            f"- {row['symbol']}: qty={row['quantity']}, buy_price={row['buy_price']}, "
            f"current_price={row.get('current_price')}, day_change={row.get('day_change_pct')}%, "
            f"52w_range=[{row.get('week52_low')}, {row.get('week52_high')}], "
            f"pe_ratio={row.get('pe_ratio')}, sector={row.get('sector')}, "
            f"P&L={row.get('pnl')} ({row.get('pnl_pct')}%)"
        )

    lines.append("\n=== RELEVANT NEWS PER STOCK ===")
    for row in portfolio_summary:
        symbol = row["symbol"]
        matched = filter_news_for_symbol(news_items, symbol)
        if matched:
            lines.append(f"\n{symbol} news:")
            for m in matched[:5]:
                lines.append(f"  - [{m['source']}] {m['title']}")
        else:
            lines.append(f"\n{symbol} news: (none found in current feed pull)")

    lines.append("\n=== GENERAL MARKET HEADLINES ===")
    for m in get_general_market_headlines(news_items, limit=8):
        lines.append(f"  - [{m['source']}] {m['title']}")

    return "\n".join(lines)


def get_ai_analysis(prompt: str) -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY not set. Get a free key at https://aistudio.google.com/apikey "
            "and run: export GEMINI_API_KEY=your_key_here"
        )
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
    return response.text


def save_report(text: str, out_dir: str = "reports") -> str:
    os.makedirs(out_dir, exist_ok=True)
    filename = f"{out_dir}/report_{datetime.now().strftime('%Y-%m-%d_%H%M')}.md"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"# Portfolio Analysis - {datetime.now().strftime('%d %b %Y, %H:%M')}\n\n")
        f.write(text)
    return filename


def main():
    print("Loading portfolio...")
    holdings = load_portfolio()

    print("Fetching live market data...")
    symbols = [h["symbol"] for h in holdings]
    market_data = get_portfolio_market_data(symbols)

    print("Fetching news...")
    news_items = fetch_latest_news()

    portfolio_summary = build_portfolio_summary(holdings, market_data)
    prompt = build_prompt(portfolio_summary, news_items)

    print("Asking Gemini for analysis...")
    analysis = get_ai_analysis(prompt)

    report_path = save_report(analysis)
    print(f"\nDone. Report saved to: {report_path}\n")
    try:
        print(analysis)
    except UnicodeEncodeError:
        # Some Windows terminals can't print certain characters (e.g. ₹) even
        # though the file itself saved fine in UTF-8. Fall back to a safe print.
        print(analysis.encode("ascii", errors="replace").decode("ascii"))
        print(f"\n(Some special characters couldn't display in this terminal - open {report_path} to see the full report correctly.)")


if __name__ == "__main__":
    main()
