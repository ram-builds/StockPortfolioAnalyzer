# Indian Stock Portfolio AI Agent (Phase 1: script)

A prototype that reads your portfolio, pulls live market data + news, and
asks Google Gemini for a hold/reduce/increase view on each stock.

This is Phase 1 — a script you run locally. Phase 2 (later) wraps this in
a web dashboard.

## Setup

```bash
cd stock-portfolio-agent
pip install -r requirements.txt
export GEMINI_API_KEY=your_key_here
```

Get a **free** API key at https://aistudio.google.com/apikey — no credit
card needed, just a Google account. The default model (`gemini-2.0-flash`)
is free to use within Google's daily quota, which is far more than this
script needs for a once-a-day run on a handful of stocks.

## Your portfolio

Edit `portfolio.csv` with your real holdings:

```
symbol,quantity,buy_price,buy_date
RELIANCE,10,2450.50,2024-01-15
```

Use the plain NSE symbol (no `.NS` suffix — the code adds that automatically).

## Run it

```bash
python portfolio_analyzer.py
```

This will:
1. Load your holdings from `portfolio.csv`
2. Pull live price, day change, 52-week range, P/E for each stock (via Yahoo Finance)
3. Pull recent headlines from Economic Times, Moneycontrol, Livemint, and Business Standard RSS feeds
4. Filter news relevant to each of your stocks
5. Send it all to Gemini and get back a per-stock HOLD/REDUCE/INCREASE/EXIT view with reasoning
6. Save the report to `reports/report_<timestamp>.md` and print it

## Things you'll likely want to tweak

- **`news_fetcher.py` → `SYMBOL_ALIASES`**: add aliases/company names for
  each stock you hold so news filtering catches more relevant mentions
  (e.g. "Adani Enterprises" for ADANIENT).
- **`market_data.py`**: yfinance data for Indian stocks is sometimes delayed
  or has gaps for smaller-cap names. If a stock keeps erroring out, try
  checking the exact Yahoo Finance ticker at https://finance.yahoo.com.
- **News depth**: RSS feeds only give headlines, not full articles or
  sentiment scores. If you want deeper coverage later, a paid API like
  Marketaux or NewsAPI can slot into `news_fetcher.py` in place of/alongside
  the RSS feeds.
- **Model**: set `GEMINI_MODEL` env var to change which Gemini model is used
  (defaults to `gemini-3.8-flash`, free on the free tier as of late 2026).
  Google renames/retires models periodically — if you get a 404 "model not
  found" error, the error message itself tells you the current replacement
  name to use.

## Important

This is a decision-support tool, not financial advice, and Gemini is not a
licensed financial advisor. Treat the output as one input into your own
research, not an instruction to execute trades.

## Roadmap ideas for Phase 2 (web dashboard)

**Done — see below for how to run it.**

- Flask/FastAPI backend serving this same logic
- Simple React/HTML frontend showing your portfolio table + AI commentary
- Scheduled daily run (cron) that emails or messages you the report
- Optional: swap manual CSV for a live broker API (Zerodha Kite Connect, etc.)

## Running the web dashboard

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=your_key_here
python app.py
```

Then open **http://127.0.0.1:5000** in your browser.

What it does:
- Shows your holdings in a table with live current price, day change %, and P&L, pulled the same way the script does
- "Refresh Data" reloads live prices/news
- "Run AI Analysis" calls Gemini with your portfolio + news and shows the hold/reduce/increase view right on the page, and also saves it to `reports/` like before

This is a local dev server (Flask's built-in one) — fine for personal use on your own machine, not meant to be exposed to the internet as-is.

## Letting someone else upload their own holdings

There's a second page, **`/upload`**, where anyone can upload their own broker
holdings statement (CSV/Excel export from Zerodha Console, Groww, Upstox,
etc., or a PDF) and get their own AI analysis — without touching your
`portfolio.csv`.

It works by scanning the file for a row that looks like a holdings table
header (matching things like "Instrument"/"Symbol", "Qty.", "Avg. cost")
rather than assuming a fixed format, since every broker's export is laid
out a bit differently. It shows the extracted holdings on screen before
running any analysis, so the person can sanity-check that it read their
file correctly.

This is a best-effort parser, not a certified one — if a broker's PDF
export doesn't come through cleanly, try CSV/Excel instead (usually
available from the same "export holdings" button).

## Sharing a link with someone else (temporary, free, no signup)

To let someone outside your machine reach `/upload`, expose your local
server with a Cloudflare Quick Tunnel — no account needed, and it closes
the moment you stop it.

1. Download `cloudflared` for Windows from:
   https://github.com/cloudflare/cloudflared/releases/latest
   (grab `cloudflared-windows-amd64.exe`, rename it to `cloudflared.exe` for convenience)
2. With your Flask app already running (`python app.py`, port 5000), open a
   **second** terminal and run:
   ```powershell
   cloudflared.exe tunnel --url http://localhost:5000
   ```
3. It prints a random public URL like `https://some-words-here.trycloudflare.com`.
   Send that link (with `/upload` on the end, e.g.
   `https://some-words-here.trycloudflare.com/upload`) to whoever you want
   to try it.
4. The link stops working as soon as you close that terminal or your PC —
   this is meant for quick testing today, not a permanent address.

For something always-on later (no need to keep your PC running), the app
can be deployed to a free host like Render or PythonAnywhere — say the word
when you're ready for that and I'll walk you through it.
