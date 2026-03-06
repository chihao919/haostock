# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Portfolio Quotes API — a FastAPI server that provides real-time stock/options quotes and net worth calculations. Uses `yfinance` for market data. Designed to be queried by Claude for portfolio monitoring.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally (with hot reload)
uvicorn main:app --reload
# API docs at http://localhost:8000/docs

# Production (used by Procfile)
uvicorn main:app --host 0.0.0.0 --port $PORT
```

## Architecture

Single-file app (`main.py`) with everything inline:

- **Portfolio data**: Hardcoded dicts at top of file — `US_STOCKS`, `TW_STOCKS`, `OPTIONS`, `BONDS`, `LOANS_TWD`. Organized by brokerage account (Firstrade, TW_Brokerage, IBKR, Cathay_US, Yongfeng_A/B, Cathay_TW).
- **Helpers**: `get_price()` fetches via yfinance, `get_fx()` for USD/TWD rate, `dte()` calculates days to expiry, `suggest_action()` recommends options actions based on DTE/P&L/ITM status.
- **Endpoints**: `/stocks/us`, `/stocks/tw`, `/options`, `/quote/{ticker}`, `/networth`, `/fx`, `/health`

Key patterns:
- Price results are cached per-request via `price_cache` dict to avoid duplicate yfinance calls
- Taiwan stocks use `.TW` suffix tickers and report values in both TWD and USD
- Options P&L is calculated as `cost - current_value` (short positions, so premium received is the cost basis)
- Net worth aggregates US stocks (USD) + TW stocks (converted via FX) + bonds - loans

## Deployment

Configured for PaaS deployment via `Procfile`. README describes Railway, Render, and Fly.io options. No authentication — CORS allows all origins, GET methods only.
