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

- **`api/index.py`** — Single FastAPI app with all 10 endpoints, deployed as Vercel serverless function
- **`api/lib/`** — Copy of `lib/` for Vercel bundling (must be kept in sync)
- **`lib/notion.py`** — Async Notion API client (httpx), reads all 6 databases + creates trade journal entries
- **`lib/pricing.py`** — Yahoo Finance HTTP API for quotes (serverless-friendly, no yfinance dependency)
- **`lib/calculator.py`** — Pure calculation logic: stock P&L, options DTE/urgency/ITM-OTM/action, bond income, net worth, trade statistics
- **`lib/tw_financial.py`** — Taiwan stock financial analysis using FinMind API (Huang Kuo-Hua method)
- **`lib/us_financial.py`** — US stock financial analysis using yfinance
- **`scripts/stock_screen.py`** — Batch stock screener for TW/US markets
- **`mcp-server/index.js`** — Node.js MCP Server with 9 tools, calls the Vercel API

### Endpoints

`GET /api/health`, `/api/fx`, `/api/quote/{ticker}`, `/api/stocks/us`, `/api/stocks/tw`, `/api/options`, `/api/networth`, `/api/trades`, `/api/financial/analyze/{ticker}`
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

`NOTION_API_KEY`, `NOTION_US_STOCKS_DB`, `NOTION_TW_STOCKS_DB`, `NOTION_OPTIONS_DB`, `NOTION_BONDS_DB`, `NOTION_LOANS_DB`, `NOTION_TRADES_DB`, `FINMIND_TOKEN` (optional, for TW financial analysis)

## Production URL

https://stock.cwithb.com

## Investment Strategy

- Full strategy doc: `docs/INVESTMENT_STRATEGY.md`
- Stop-loss: 投機 -10%, 投資 -20%
- Sell put targets: screened 4/4 stocks (V, MA, AAPL, META, AMZN)
- Covered call pipeline: CCJ, GOOG, TSM, MU, NVDA, AMD
- Position cleanup: exit 台塑/中鋼/春雨/POOL/HIMS/GRAB, redeploy into 0050/VOO
- Run `python3 scripts/stock_screen.py --us` monthly to refresh targets

## Spec & BDD

- Full system spec: `docs/SPEC.md`
- BDD features: `tests/features/*.feature` (7 files)
- BDD step definitions: `tests/steps/test_*_bdd.py`

## Development Rules (from TIP)

### Development Workflow (7 Steps)

For features involving more than 3 files, follow this flow:
1. **Plan** — Use Plan Mode (Shift+Tab x2) to clarify requirements, let AI ask 5 questions, produce a plan
2. **Behavior Specs** — Write Given-When-Then scenarios covering happy paths and edge cases
3. **Tests** — Generate tests from behavior specs before writing implementation
4. **Implement** — Write code, auto-run tests after each sub-feature, commit when green
5. **Review** — Explain changes in plain language, check for unnecessary code
6. **Refactor** — Clean up duplication and complexity, run tests to verify
7. **Commit** — Use conventional commit format: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`

### Testing Discipline

- Write unit tests for every new function or module
- Run existing tests BEFORE and AFTER making changes
- After completing each sub-feature, automatically run tests and commit if all pass
- Test both happy paths and edge cases (empty input, invalid data, boundary values)

### Error Handling

- Every external call (API, database, file system) must have proper error handling
- Error messages must be descriptive and actionable — never `except: pass`
- Never silently swallow errors — all errors must be logged or reported

### Code Quality

- Keep functions small and focused: one function, one job
- Use clear, descriptive names — no vague abbreviations
- After completing a feature, review for duplication and unnecessary complexity
- All code and comments in English; discussion with user in Chinese

### Secrets Management

- NEVER hard-code API keys, passwords, tokens in source code
- ALL secrets through environment variables from `.env`
- Before every commit, verify no sensitive data in staged changes
- Run `/security-check` before every `git push`
