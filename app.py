"""
app.py
Flask web dashboard for your stock portfolio agent.

Setup:
    pip install -r requirements.txt
    export GEMINI_API_KEY=your_key_here

Run:
    python app.py
Then open http://127.0.0.1:5000 in your browser.
"""

import os
from flask import Flask, render_template, jsonify, request

from market_data import get_portfolio_market_data
from news_fetcher import fetch_latest_news, filter_news_for_symbol
from parse_broker_statement import parse_broker_statement
from portfolio_analyzer import (
    load_portfolio,
    build_portfolio_summary,
    build_prompt,
    get_ai_analysis,
    save_report,
)

app = Flask(__name__)
UPLOAD_DIR = "uploads"
ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".pdf"}

# Simple in-memory cache so we don't refetch on every click within a session
_cache = {"summary": None, "news": None}
_uploaded_cache = {"summary": None, "news": None}


def _compute_totals(summary: list) -> dict:
    total_invested = sum(r.get("invested_value", 0) or 0 for r in summary)
    total_current = sum(r.get("current_value", 0) or 0 for r in summary)
    total_pnl = round(total_current - total_invested, 2)
    total_pnl_pct = round((total_pnl / total_invested) * 100, 2) if total_invested else 0
    return {
        "invested": round(total_invested, 2),
        "current": round(total_current, 2),
        "pnl": total_pnl,
        "pnl_pct": total_pnl_pct,
    }


def _load_dashboard_data():
    holdings = load_portfolio()
    symbols = [h["symbol"] for h in holdings]
    market_data = get_portfolio_market_data(symbols)
    news_items = fetch_latest_news()
    summary = build_portfolio_summary(holdings, market_data)

    _cache["summary"] = summary
    _cache["news"] = news_items

    return {"holdings": summary, "totals": _compute_totals(summary)}


@app.route("/")
def dashboard():
    data = _load_dashboard_data()
    return render_template("index.html", holdings=data["holdings"], totals=data["totals"])


@app.route("/refresh")
def refresh():
    """Re-fetch market data + news and return the dashboard again."""
    return dashboard()


@app.route("/analyze")
def analyze():
    """Run the Gemini analysis using the last-fetched data (or fetch fresh if empty)."""
    if _cache["summary"] is None:
        _load_dashboard_data()

    try:
        prompt = build_prompt(_cache["summary"], _cache["news"])
        analysis_text = get_ai_analysis(prompt)
        save_report(analysis_text)
        return jsonify({"ok": True, "analysis": analysis_text})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/upload", methods=["GET"])
def upload_form():
    """Page where someone else uploads their broker holdings statement."""
    return render_template("upload.html")


@app.route("/upload", methods=["POST"])
def upload_statement():
    uploaded = request.files.get("statement")
    if not uploaded or uploaded.filename == "":
        return render_template("upload.html", error="Please choose a file to upload.")

    ext = os.path.splitext(uploaded.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return render_template(
            "upload.html",
            error=f"Unsupported file type '{ext}'. Please upload a CSV, Excel (.xlsx/.xls), or PDF holdings statement.",
        )

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    save_path = os.path.join(UPLOAD_DIR, uploaded.filename)
    uploaded.save(save_path)

    result = parse_broker_statement(save_path)
    holdings = result["holdings"]
    warnings = result["warnings"]

    if not holdings:
        return render_template("upload.html", error=None, warnings=warnings, raw_preview=result.get("raw_preview"))

    symbols = [h["symbol"] for h in holdings]
    market_data = get_portfolio_market_data(symbols)
    news_items = fetch_latest_news()
    summary = build_portfolio_summary(holdings, market_data)
    totals = _compute_totals(summary)

    _uploaded_cache["summary"] = summary
    _uploaded_cache["news"] = news_items

    return render_template(
        "upload_results.html",
        holdings=summary,
        totals=totals,
        warnings=warnings,
    )


@app.route("/analyze_uploaded")
def analyze_uploaded():
    if _uploaded_cache["summary"] is None:
        return jsonify({"ok": False, "error": "No uploaded portfolio found. Please upload a statement first."}), 400

    try:
        prompt = build_prompt(_uploaded_cache["summary"], _uploaded_cache["news"])
        analysis_text = get_ai_analysis(prompt)
        return jsonify({"ok": True, "analysis": analysis_text})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)
