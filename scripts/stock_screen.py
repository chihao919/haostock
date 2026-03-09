#!/usr/bin/env python3
"""Stock screener using Huang Kuo-Hua method (TW) and fundamental analysis (US).

Usage:
    python3 scripts/stock_screen.py --test          # Test with a few stocks
    python3 scripts/stock_screen.py --tw             # Screen TW stocks
    python3 scripts/stock_screen.py --us             # Screen US stocks (S&P 500 sample)
    python3 scripts/stock_screen.py --ticker 2330    # Analyze single stock
"""

import asyncio
import json
import sys
import os
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.tw_financial import analyze_stock as analyze_tw, fetch_finmind, CRITERIA
from lib.us_financial import analyze_stock as analyze_us
from lib.pricing import PriceCache
from lib.five_lines import analyze as five_lines_analyze


async def screen_tw_stocks(stock_ids: list[str] | None = None) -> list[dict]:
    """Screen Taiwan stocks using Huang Kuo-Hua criteria.

    If stock_ids not provided, fetch from FinMind revenue data
    and filter by price > 50 TWD, capital < 100 billion.
    """
    if not stock_ids:
        # Fetch TW stock list from FinMind (all listed stocks)
        import httpx
        params = {
            "dataset": "TaiwanStockInfo",
            "token": os.environ.get("FINMIND_TOKEN", ""),
        }
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get("https://api.finmindtrade.com/api/v4/data", params=params)
            r.raise_for_status()
            info_data = r.json().get("data", [])
        # Filter: only numeric stock IDs (exclude ETFs with letters, warrants, etc.)
        stock_ids = list(set(
            r.get("stock_id", "") for r in info_data
            if r.get("stock_id", "").isdigit() and len(r.get("stock_id", "")) == 4
        ))
        print(f"Found {len(stock_ids)} listed TW stocks")

    cache = PriceCache()
    passed = []
    total = len(stock_ids)

    for i, sid in enumerate(stock_ids):
        try:
            # Pre-filter: price > 50
            price = cache.get_price(f"{sid}.TW")
            if not price or price < CRITERIA["price_min"]:
                continue

            print(f"[{i+1}/{total}] Analyzing {sid} (price={price})...")
            result = await analyze_tw(sid)

            if result.get("overall_pass"):
                result["current_price"] = price
                passed.append(result)
                print(f"  PASS: {sid} score={result['score']}")
        except Exception as e:
            print(f"  Error analyzing {sid}: {e}")

    return passed


async def screen_us_stocks(tickers: list[str] | None = None) -> list[dict]:
    """Screen US stocks. Default: a sample of major stocks."""
    if not tickers:
        # Fetch S&P 500 constituents from GitHub
        import httpx as _httpx
        import csv as _csv
        import io as _io
        r = _httpx.get(
            "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv",
            timeout=10,
        )
        reader = _csv.DictReader(_io.StringIO(r.text))
        tickers = [row["Symbol"].replace(".", "-") for row in reader]
        print(f"Fetched {len(tickers)} S&P 500 stocks")

    passed = []
    total = len(tickers)

    for i, ticker in enumerate(tickers):
        try:
            print(f"[{i+1}/{total}] Analyzing {ticker}...")
            result = await analyze_us(ticker)

            if result.get("overall_pass"):
                passed.append(result)
                print(f"  PASS: {ticker} score={result['score']}")
        except Exception as e:
            print(f"  Error analyzing {ticker}: {e}")

    return passed


def scan_five_lines(tickers: list[str], years: float = 3.5) -> list[dict]:
    """Scan multiple tickers for five lines signals. Returns list of results."""
    results = []
    total = len(tickers)
    buy_signals = {"強烈買入", "加碼買入"}

    for i, ticker in enumerate(tickers):
        try:
            print(f"[{i+1}/{total}] Five Lines: {ticker}...")
            result = five_lines_analyze(ticker, years=years, include_history=False)
            signal = result["signal"]
            marker = " ★ BUY" if signal in buy_signals else ""
            print(f"  {ticker}: ${result['current_price']} — {signal}{marker}")
            results.append({
                "ticker": ticker,
                "current_price": result["current_price"],
                "signal": signal,
                "position": result["position"],
                "lines": result["lines"],
            })
        except Exception as e:
            print(f"  Error: {ticker}: {e}")

    # Summary
    buys = [r for r in results if r["signal"] in buy_signals]
    if buys:
        print(f"\n{'='*40}")
        print(f"Buy signals ({len(buys)}/{len(results)}):")
        for r in buys:
            print(f"  {r['ticker']}: ${r['current_price']} — {r['signal']}")
    else:
        print(f"\nNo buy signals found in {len(results)} stocks.")

    return results


async def main():
    parser = argparse.ArgumentParser(description="Stock Screener")
    parser.add_argument("--tw", action="store_true", help="Screen TW stocks")
    parser.add_argument("--us", action="store_true", help="Screen US stocks")
    parser.add_argument("--ticker", type=str, help="Analyze a single ticker")
    parser.add_argument("--test", action="store_true", help="Test mode with a few stocks")
    parser.add_argument("--fivelines", action="store_true", help="Scan five lines signals")
    parser.add_argument("--fivelines-tickers", type=str, nargs="+",
                        default=["0050.TW", "2330.TW", "VOO", "QQQ", "SPY", "0056.TW"],
                        help="Tickers for five lines scan")
    parser.add_argument("--output", type=str, help="Output JSON file path")
    args = parser.parse_args()

    results = {}

    if args.ticker:
        ticker = args.ticker.strip()
        if ticker.isdigit():
            result = await analyze_tw(ticker)
        else:
            result = await analyze_us(ticker.upper())
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        return

    if args.test:
        print("=== Test Mode ===")
        print("\n--- TW Stock: 2330 (TSMC) ---")
        tw_result = await analyze_tw("2330")
        print(json.dumps(tw_result, indent=2, ensure_ascii=False, default=str))

        print("\n--- US Stock: NVDA ---")
        us_result = await analyze_us("NVDA")
        print(json.dumps(us_result, indent=2, ensure_ascii=False, default=str))
        return

    if args.tw:
        print("=== Screening TW Stocks ===")
        results["tw"] = await screen_tw_stocks()

    if args.us:
        print("=== Screening US Stocks ===")
        results["us"] = await screen_us_stocks()

    if args.fivelines:
        print("=== Five Lines (樂活五線譜) Scan ===")
        results["five_lines"] = scan_five_lines(args.fivelines_tickers)

    if not args.tw and not args.us and not args.fivelines:
        parser.print_help()
        return

    # Output results
    output = {
        "screen_date": datetime.now().isoformat(),
        "results": results,
    }
    output_json = json.dumps(output, indent=2, ensure_ascii=False, default=str)

    if args.output:
        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        with open(args.output, "w") as f:
            f.write(output_json)
        print(f"\nResults saved to {args.output}")
    else:
        print("\n=== Results ===")
        print(output_json)


if __name__ == "__main__":
    asyncio.run(main())
