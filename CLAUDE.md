# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Portfolio Quotes API — real-time stock/options quotes and net worth calculations. Notion is the single source of truth for all portfolio data. Deployed on Vercel, accessed via MCP Server by Claude.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests (112 tests: unit + BDD integration)
python3 -m pytest tests/ -v

# Run only unit tests
python3 -m pytest tests/unit/ -v

# Run only BDD tests
python3 -m pytest tests/steps/ -v

# Deploy to Vercel
vercel --prod

# MCP Server (installed via `claude mcp add`)
cd mcp-server && npm install
```

## Architecture

```
Notion (data) → FastAPI on Vercel (api/index.py) → MCP Server → Claude
                     ↕
              Yahoo Finance HTTP API (pricing)
```

### Key Modules

- **`api/index.py`** — Single FastAPI app with all 9 endpoints, deployed as Vercel serverless function
- **`api/lib/`** — Copy of `lib/` for Vercel bundling (must be kept in sync)
- **`lib/notion.py`** — Async Notion API client (httpx), reads all 6 databases + creates trade journal entries
- **`lib/pricing.py`** — Yahoo Finance HTTP API for quotes (serverless-friendly, no yfinance dependency)
- **`lib/calculator.py`** — Pure calculation logic: stock P&L, options DTE/urgency/ITM-OTM/action, bond income, net worth, trade statistics
- **`mcp-server/index.js`** — Node.js MCP Server with 8 tools, calls the Vercel API

### Endpoints

`GET /api/health`, `/api/fx`, `/api/quote/{ticker}`, `/api/stocks/us`, `/api/stocks/tw`, `/api/options`, `/api/networth`, `/api/trades`
`POST /api/trades`

### Data Flow

- Portfolio data (positions, bonds, loans) lives in Notion databases
- API reads from Notion, fetches live prices from Yahoo Finance, calculates P&L
- `api/lib/` is a copy of root `lib/` — Vercel can't import from parent directories

### Important Patterns

- `PriceCache` caches prices per-request to avoid duplicate Yahoo Finance calls
- Taiwan stocks use `.TW` suffix; values reported in TWD and USD
- Options P&L = `cost - current_value` (short positions)
- Options action rules: EXPIRED → Let expire (OTM≤7d) → Close/Roll URGENT (ITM≤7d) → Close (75%+ profit) → Monitor (≤21d) → Hold
- Bond income applies 30% withholding tax
- Trade journal supports filtering by ticker/result/asset_type

## Environment Variables (Vercel)

`NOTION_API_KEY`, `NOTION_US_STOCKS_DB`, `NOTION_TW_STOCKS_DB`, `NOTION_OPTIONS_DB`, `NOTION_BONDS_DB`, `NOTION_LOANS_DB`, `NOTION_TRADES_DB`

## Production URL

https://stock.cwithb.com

## Spec & BDD

- Full system spec: `docs/SPEC.md`
- BDD features: `tests/features/*.feature` (7 files)
- BDD step definitions: `tests/steps/test_*_bdd.py`
