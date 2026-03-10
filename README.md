# Portfolio Quotes API & 樂活五線譜

Real-time US/TW stock quotes, options P&L, net worth tracking, and Happy Five Lines technical analysis.

**Production:** https://stock.cwithb.com

## Features

- **Portfolio Dashboard** — US/TW stocks, options positions with P&L, bonds, loans
- **Net Worth** — Full asset/liability overview in USD and TWD
- **樂活五線譜** — Linear regression ± σ bands with buy/sell signals
- **樂活通道** — 20-week Bollinger channel (SMA ± 1σ)
- **Financial Analysis** — Huang Kuo-Hua method (TW) / Fundamental analysis (US)
- **Trade Journal** — Record and review trades with win/loss tracking
- **MCP Server** — Remote MCP endpoint for Claude integration (OAuth 2.1 + PKCE)
- **Stock Screener** — Batch screening for TW/US markets

## Architecture

```
Notion (portfolio data) → FastAPI on Vercel → MCP Server → Claude
                                ↕
                    Yahoo Finance (pricing)
                    FinMind API (TW financials)
```

## Quick Start

```bash
pip install -r requirements.txt

# Run tests (unit + BDD)
python3 -m pytest tests/ -v

# Deploy
vercel --prod
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/health` | Health check |
| `GET /api/fx` | USD/TWD exchange rate |
| `GET /api/quote/{ticker}` | Single stock quote |
| `GET /api/stocks/us` | US stock positions + P&L |
| `GET /api/stocks/tw` | TW stock positions + P&L |
| `GET /api/options` | Options positions + actions |
| `GET /api/networth` | Net worth overview |
| `GET /api/bonds` | Bond holdings |
| `GET /api/loans` | Loan balances |
| `GET /api/trades` | Trade journal (filterable) |
| `POST /api/trades` | Add trade record |
| `GET /api/financial/analyze/{ticker}` | Financial analysis |
| `GET /api/fivelines/{ticker}` | Five lines analysis |
| `POST /mcp` | Remote MCP endpoint |

## Web Pages

| Path | Description |
|------|-------------|
| `/` | Portfolio dashboard |
| `/fivelines` | 樂活五線譜 interactive chart |
| `/portfolio` | Google-auth portfolio view |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `NOTION_API_KEY` | Notion integration token |
| `NOTION_US_STOCKS_DB` | Notion US stocks database ID |
| `NOTION_TW_STOCKS_DB` | Notion TW stocks database ID |
| `NOTION_OPTIONS_DB` | Notion options database ID |
| `NOTION_BONDS_DB` | Notion bonds database ID |
| `NOTION_LOANS_DB` | Notion loans database ID |
| `NOTION_TRADES_DB` | Notion trades database ID |
| `FINANCIAL_API_KEY` | API key for protected endpoints |
| `OAUTH_CLIENT_SECRET` | OAuth client secret for MCP |
| `FINMIND_TOKEN` | FinMind API token (TW financials) |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID |

## Tech Stack

- **Backend:** Python, FastAPI, httpx, numpy
- **Frontend:** Chart.js + chartjs-plugin-zoom
- **Data:** Notion API, Yahoo Finance, FinMind
- **Deploy:** Vercel (serverless)
- **Integration:** MCP Server (OAuth 2.1 + PKCE)
