"""
parse_broker_statement.py
Parses a broker holdings statement (Excel/CSV export from Zerodha Console,
Groww, Upstox, etc., or a PDF holdings statement) into a plain list of
holdings: [{"symbol": ..., "quantity": ..., "buy_price": ...}, ...]

Broker exports are messy in practice - title rows before the real header,
different column names per broker, summary/total rows at the bottom. This
module scans for the header row instead of assuming row 0, and matches
columns by keyword rather than exact name.

This is heuristic. It returns warnings alongside the parsed holdings so the
UI can show the user what was extracted for a sanity check before running
any analysis on it.
"""

import os
import pandas as pd

# Keywords used to detect the header row and map columns, in priority order.
SYMBOL_KEYWORDS = ["tradingsymbol", "trading symbol", "instrument", "symbol", "scrip name", "scrip", "stock name", "stock"]
QUANTITY_KEYWORDS = ["quantity available", "net qty", "qty.", "quantity", "qty"]
PRICE_KEYWORDS = ["avg. cost", "avg cost price", "average cost", "avg cost", "average price", "avg price", "buy price", "avg. price"]

# Rows containing any of these (case-insensitive) are treated as summary/junk, not holdings.
SKIP_ROW_MARKERS = ["total", "grand total", "net total", "summary"]


def _cell(v) -> str:
    return "" if v is None else str(v).strip()


def _find_header_row(rows: list) -> int:
    """Scan the first ~20 rows for one that looks like a header (matches >=2 keyword groups)."""
    for i, row in enumerate(rows[:20]):
        cells = [_cell(c).lower() for c in row]
        has_symbol = any(any(kw in c for kw in SYMBOL_KEYWORDS) for c in cells)
        has_qty = any(any(kw in c for kw in QUANTITY_KEYWORDS) for c in cells)
        has_price = any(any(kw in c for kw in PRICE_KEYWORDS) for c in cells)
        if has_symbol and has_qty and has_price:
            return i
    return -1


def _map_columns(header_row: list) -> dict:
    """Return {'symbol': col_index, 'quantity': col_index, 'buy_price': col_index} or missing keys."""
    cells = [_cell(c).lower() for c in header_row]
    mapping = {}
    for idx, c in enumerate(cells):
        if "symbol" not in mapping and any(kw in c for kw in SYMBOL_KEYWORDS):
            mapping["symbol"] = idx
        if "quantity" not in mapping and any(kw in c for kw in QUANTITY_KEYWORDS):
            mapping["quantity"] = idx
        if "buy_price" not in mapping and any(kw in c for kw in PRICE_KEYWORDS):
            mapping["buy_price"] = idx
    return mapping


def _rows_to_holdings(rows: list, header_idx: int) -> tuple:
    """Given raw rows and the header row index, extract holdings from the rows below it."""
    warnings = []
    header_row = rows[header_idx]
    col_map = _map_columns(header_row)

    missing = [k for k in ("symbol", "quantity", "buy_price") if k not in col_map]
    if missing:
        warnings.append(f"Could not confidently identify columns for: {', '.join(missing)}")
        return [], warnings

    holdings = []
    for row in rows[header_idx + 1:]:
        cells = [_cell(c) for c in row]
        if not any(cells):
            continue  # blank row
        symbol_cell = cells[col_map["symbol"]] if col_map["symbol"] < len(cells) else ""
        if not symbol_cell or any(marker in symbol_cell.lower() for marker in SKIP_ROW_MARKERS):
            continue

        try:
            qty_raw = cells[col_map["quantity"]].replace(",", "")
            price_raw = cells[col_map["buy_price"]].replace(",", "")
            quantity = float(qty_raw)
            buy_price = float(price_raw)
        except (ValueError, IndexError):
            warnings.append(f"Skipped row for '{symbol_cell}' - couldn't read quantity/price as numbers")
            continue

        # Symbol may come with exchange suffix like "RELIANCE-EQ" - strip common suffixes
        symbol = symbol_cell.upper().replace("-EQ", "").replace(".NS", "").replace(".BO", "").strip()

        holdings.append({"symbol": symbol, "quantity": quantity, "buy_price": buy_price, "buy_date": "Unknown"})

    if not holdings:
        warnings.append("No holdings rows could be parsed below the detected header.")

    return holdings, warnings


def _read_excel_or_csv_rows(file_path: str, ext: str) -> list:
    if ext == ".csv":
        df = pd.read_csv(file_path, header=None, dtype=str, keep_default_na=False)
    else:
        df = pd.read_excel(file_path, header=None, dtype=str, engine="openpyxl" if ext == ".xlsx" else None)
        df = df.fillna("")
    return df.values.tolist()


def _read_pdf_rows(file_path: str) -> list:
    import pdfplumber
    all_rows = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                all_rows.extend(table)
    return all_rows


def parse_broker_statement(file_path: str) -> dict:
    """
    Parse an uploaded broker statement.

    Returns:
        {"holdings": [...], "warnings": [...], "raw_preview": [[...], ...]}
    """
    ext = os.path.splitext(file_path)[1].lower()

    try:
        if ext in (".xlsx", ".xls", ".csv"):
            rows = _read_excel_or_csv_rows(file_path, ext)
        elif ext == ".pdf":
            rows = _read_pdf_rows(file_path)
        else:
            return {"holdings": [], "warnings": [f"Unsupported file type: {ext}"], "raw_preview": []}
    except Exception as e:
        return {"holdings": [], "warnings": [f"Failed to read file: {e}"], "raw_preview": []}

    if not rows:
        return {"holdings": [], "warnings": ["File appears to be empty or unreadable."], "raw_preview": []}

    header_idx = _find_header_row(rows)
    if header_idx == -1:
        return {
            "holdings": [],
            "warnings": [
                "Couldn't find a recognizable holdings table (expected columns like "
                "Symbol/Instrument, Quantity, Avg. Cost). This broker's export format "
                "may not be supported yet - try exporting as CSV/Excel instead of PDF, "
                "or check the raw preview below."
            ],
            "raw_preview": rows[:10],
        }

    holdings, warnings = _rows_to_holdings(rows, header_idx)
    return {"holdings": holdings, "warnings": warnings, "raw_preview": rows[max(0, header_idx - 1):header_idx + 6]}
