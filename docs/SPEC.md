# Portfolio Quotes API — System Specification

## 1. 系統概覽

一個投資組合即時報價系統，讓使用者透過 Claude（Code / Desktop / Project）查詢持倉損益、取得投資建議。

### 1.1 核心原則

- **Notion 是唯一資料來源（Single Source of Truth）**：所有持倉、選擇權、債券、貸款資料都在 Notion 維護
- **API 是資料處理層**：從 Notion 讀取持倉，從 yfinance 取得即時報價，計算損益後回傳
- **MCP Server 是存取介面**：Claude Code / Desktop 透過 MCP 協議直接呼叫工具

### 1.2 系統架構圖

```
┌─────────────────┐     MCP Protocol      ┌──────────────────┐
│  Claude Code /  │ ◄──────────────────►   │   MCP Server     │
│  Claude Desktop │                        │  (Local Process)  │
└─────────────────┘                        └────────┬─────────┘
                                                    │
                                           ┌────────▼─────────┐
                                           │   FastAPI Server  │
                                           │   (Vercel Edge)   │
                                           └──┬────────────┬───┘
                                              │            │
                                    ┌─────────▼──┐   ┌─────▼──────┐
                                    │  Notion API │   │  yfinance  │
                                    │ (持倉資料)   │   │ (即時報價)  │
                                    └────────────┘   └────────────┘
```

---

## 2. 資料模型（Notion Database Schema）

### 2.1 US Stocks（美股持倉）

| 欄位 | 類型 | 說明 | 範例 |
|------|------|------|------|
| Ticker | Title | 股票代碼 | `NVDA` |
| Account | Select | 券商帳戶 | `Firstrade`, `IBKR`, `Cathay_US`, `TW_Brokerage` |
| Shares | Number | 持有股數 | `100.15563` |
| Avg Cost | Number | 平均成本 (USD) | `92.34` |

### 2.2 TW Stocks（台股持倉）

| 欄位 | 類型 | 說明 | 範例 |
|------|------|------|------|
| Ticker | Title | 股票代碼（含 .TW） | `2330.TW` |
| Name | Rich Text | 中文名稱 | `台積電` |
| Account | Select | 券商帳戶 | `Yongfeng_A`, `Yongfeng_B`, `Cathay_TW` |
| Shares | Number | 持有股數 | `5000` |
| Avg Cost | Number | 平均成本 (TWD) | `854.56` |

### 2.3 Options（選擇權倉位）

| 欄位 | 類型 | 說明 | 範例 |
|------|------|------|------|
| Ticker | Title | 標的代碼 | `CCJ` |
| Account | Select | 券商帳戶 | `Firstrade` |
| Expiry | Date | 到期日 | `2026-03-13` |
| Strike | Number | 履約價 | `110` |
| Type | Select | 類型 | `put`, `call` |
| Qty | Number | 數量（負數=賣方） | `-1` |
| Cost | Number | 成本基礎 (USD) | `479.98` |

### 2.4 Bonds（債券）

| 欄位 | 類型 | 說明 | 範例 |
|------|------|------|------|
| Name | Title | 債券名稱 | `UBS 5.699%` |
| Face Value | Number | 面額 (USD) | `280000` |
| Coupon Rate | Number | 票面利率 | `0.05699` |
| Maturity | Date | 到期日 | `2035-02-08` |
| Cost | Number | 購入成本 (USD) | `299040` |

### 2.5 Loans（貸款）

| 欄位 | 類型 | 說明 | 範例 |
|------|------|------|------|
| Name | Title | 貸款名稱 | `房屋貸款` |
| Rate | Number | 年利率 | `0.022` |
| Balance | Number | 餘額 (TWD) | `19600000` |
| Monthly Payment | Number | 月付金 (TWD) | `33078` |
| Periods Done | Number | 已繳期數 | `37` |
| Total Periods | Number | 總期數 | `360` |

### 2.6 Trade Journal（交易日誌）

| 欄位 | 類型 | 說明 | 範例 |
|------|------|------|------|
| Date | Date | 交易日期 | `2026-03-06` |
| Ticker | Title | 股票/選擇權代碼 | `CCJ` |
| Action | Select | 交易動作 | `Buy`, `Sell`, `Open`, `Close`, `Roll` |
| Asset Type | Select | 資產類型 | `Stock`, `Option` |
| Qty | Number | 數量 | `100` |
| Price | Number | 成交價格 | `92.34` |
| Total Amount | Number | 總金額 (USD) | `9234.00` |
| P&L | Number | 已實現損益（平倉時填寫） | `500.00` |
| Result | Select | 結果 | `Win`, `Loss`, `Breakeven` |
| Reason | Rich Text | 為什麼做這筆交易 | `技術面突破年線，基本面鈾礦供需缺口擴大` |
| Lesson | Rich Text | 事後檢討/改進方法 | `應該分批進場，一次All-in風險太高` |
| Tags | Multi-select | 標籤分類 | `Momentum`, `Value`, `Earnings Play`, `Covered Call` |
| Account | Select | 券商帳戶 | `Firstrade` |
| Screenshot | Files | 進場時的技術圖 | (optional) |

---

## 3. API Endpoints 規格

Base URL: `https://<project>.vercel.app/api`

### 3.1 GET /api/health

健康檢查。

**Response 200:**
```json
{
  "status": "ok",
  "timestamp": "2026-03-06T10:00:00"
}
```

### 3.2 GET /api/fx

取得 USD/TWD 即時匯率。

**Response 200:**
```json
{
  "USDTWD": 32.15,
  "timestamp": "2026-03-06T10:00:00"
}
```

### 3.3 GET /api/quote/{ticker}

查詢單一股票即時報價。

**Parameters:**
- `ticker` (path, required): 股票代碼，例如 `NVDA`, `2330.TW`

**Response 200:**
```json
{
  "ticker": "NVDA",
  "price": 185.26,
  "timestamp": "2026-03-06T10:00:00"
}
```

**Response 404:** 找不到該股票報價

### 3.4 GET /api/stocks/us

查詢所有美股持倉及損益。從 Notion 讀取持倉，從 yfinance 取得報價。

**Response 200:**
```json
{
  "accounts": {
    "Firstrade": {
      "positions": [
        {
          "ticker": "CCJ",
          "shares": 100.15563,
          "avg_cost": 92.34,
          "current_price": 95.00,
          "market_value": 9514.78,
          "cost_basis": 9248.37,
          "unrealized_pl": 266.41,
          "pl_pct": 2.88
        }
      ],
      "total_market_value": 50000.00,
      "total_cost_basis": 45000.00,
      "total_pl": 5000.00,
      "total_pl_pct": 11.11
    }
  },
  "summary": {
    "total_market_value": 200000.00,
    "total_cost_basis": 180000.00,
    "total_pl": 20000.00,
    "total_pl_pct": 11.11
  },
  "timestamp": "2026-03-06T10:00:00"
}
```

### 3.5 GET /api/stocks/tw

查詢所有台股持倉及損益。金額同時以 TWD 和 USD 表示。

**Response 200:**
```json
{
  "usdtwd_rate": 32.15,
  "accounts": {
    "Yongfeng_A": {
      "positions": [
        {
          "ticker": "2330.TW",
          "name": "台積電",
          "shares": 5000,
          "avg_cost_twd": 854.56,
          "current_price_twd": 900.00,
          "market_value_twd": 4500000,
          "market_value_usd": 139969.52,
          "cost_basis_twd": 4272800,
          "unrealized_pl_twd": 227200,
          "pl_pct": 5.32
        }
      ],
      "total_market_value_twd": 5000000,
      "total_market_value_usd": 155521.00,
      "total_pl_twd": 300000,
      "total_pl_pct": 6.38
    }
  },
  "summary": {
    "total_market_value_twd": 20000000,
    "total_market_value_usd": 622084.00,
    "total_pl_twd": 1500000,
    "total_pl_pct": 8.11
  },
  "timestamp": "2026-03-06T10:00:00"
}
```

### 3.6 GET /api/options

查詢所有選擇權倉位、損益、及建議動作。

**Action 判斷規則：**
- DTE ≤ 0 → `EXPIRED`
- DTE ≤ 7 且 OTM → `Let expire`
- DTE ≤ 7 且 ITM → `Close/Roll URGENT`
- P&L% ≥ 75% → `Close (75%+ profit)`
- DTE ≤ 21 → `Monitor`
- 其他 → `Hold`

**Urgency 判斷：**
- DTE ≤ 7 → `red`
- DTE ≤ 21 → `yellow`
- DTE > 21 → `green`

**Response 200:**
```json
{
  "positions": [
    {
      "account": "Firstrade",
      "ticker": "CCJ",
      "expiry": "2026-03-13",
      "strike": 110,
      "type": "put",
      "qty": -1,
      "underlying_price": 95.00,
      "itm_otm": "OTM $15.0",
      "dte": 7,
      "urgency": "red",
      "cost_basis": 479.98,
      "current_value": 120.00,
      "unrealized_pl": 359.98,
      "pl_pct": 75.0,
      "action": "Close (75%+ profit)"
    }
  ],
  "summary": {
    "total_cost_basis": 5000.00,
    "total_current_value": 2000.00,
    "total_pl": 3000.00,
    "total_pl_pct": 60.0
  },
  "timestamp": "2026-03-06T10:00:00"
}
```

### 3.7 GET /api/networth

完整淨資產總覽，包含所有資產類別和負債。

**Response 200:**
```json
{
  "usdtwd_rate": 32.15,
  "assets": {
    "us_stocks_usd": 200000.00,
    "tw_stocks_twd": 20000000,
    "tw_stocks_usd": 622084.00,
    "bonds_cost_usd": 2027690,
    "total_assets_usd": 2849774.00
  },
  "liabilities": {
    "total_loans_twd": 59050000,
    "total_loans_usd": 1836703.89,
    "monthly_payments_twd": 99657
  },
  "income": {
    "bonds_annual_gross_usd": 107058.70,
    "bonds_annual_net_usd": 74941.09,
    "bonds_monthly_net_usd": 6245.09,
    "withholding_tax_rate": "30%"
  },
  "net_worth_usd": 1013070.11,
  "net_worth_twd": 32570203,
  "timestamp": "2026-03-06T10:00:00"
}
```

### 3.8 GET /api/trades

查詢交易歷史紀錄。支援篩選。

**Query Parameters:**
- `ticker` (optional): 篩選特定股票
- `result` (optional): 篩選結果 `Win`, `Loss`, `Breakeven`
- `asset_type` (optional): 篩選類型 `Stock`, `Option`
- `limit` (optional, default=50): 回傳筆數

**Response 200:**
```json
{
  "trades": [
    {
      "date": "2026-03-01",
      "ticker": "CCJ",
      "action": "Sell",
      "asset_type": "Option",
      "qty": 1,
      "price": 4.80,
      "total_amount": 480.00,
      "pl": 350.00,
      "result": "Win",
      "reason": "賣 put 收取權利金，CCJ 基本面強勁",
      "lesson": "到期前 7 天獲利已達 75%，應該提前平倉鎖利",
      "tags": ["Covered Put", "Commodity"],
      "account": "Firstrade"
    }
  ],
  "summary": {
    "total_trades": 25,
    "wins": 18,
    "losses": 5,
    "breakeven": 2,
    "win_rate": 72.0,
    "total_realized_pl": 12500.00,
    "avg_win": 850.00,
    "avg_loss": -320.00
  },
  "timestamp": "2026-03-06T10:00:00"
}
```

### 3.9 POST /api/trades

新增一筆交易紀錄到 Notion。

**Request Body:**
```json
{
  "date": "2026-03-06",
  "ticker": "CCJ",
  "action": "Close",
  "asset_type": "Option",
  "qty": 1,
  "price": 1.20,
  "total_amount": 120.00,
  "pl": 359.98,
  "result": "Win",
  "reason": "CCJ put 到期前平倉，OTM 且獲利 75%+",
  "lesson": "按照規則在 75% 獲利時平倉是正確的",
  "tags": ["Covered Put"],
  "account": "Firstrade"
}
```

**Response 201:**
```json
{
  "id": "notion-page-id",
  "status": "created",
  "timestamp": "2026-03-06T10:00:00"
}
```

---

## 4. MCP Server 規格

MCP Server 以 local process 形式運行，透過 stdio 與 Claude 通訊。

### 4.1 Tools 定義

| Tool Name | 說明 | 參數 |
|-----------|------|------|
| `get_us_stocks` | 查詢美股持倉及損益 | 無 |
| `get_tw_stocks` | 查詢台股持倉及損益 | 無 |
| `get_options` | 查詢選擇權倉位及建議 | 無 |
| `get_quote` | 查詢單一股票報價 | `ticker: string` |
| `get_networth` | 查詢淨資產總覽 | 無 |
| `get_fx_rate` | 查詢 USD/TWD 匯率 | 無 |
| `get_trades` | 查詢交易歷史紀錄 | `ticker?: string`, `result?: string`, `limit?: number` |
| `add_trade` | 新增交易紀錄 | `date, ticker, action, asset_type, qty, price, total_amount, pl?, result?, reason, lesson?, tags?, account` |

### 4.2 MCP Server 配置

```json
// ~/.claude/claude_desktop_config.json 或 Claude Code 的 MCP 設定
{
  "mcpServers": {
    "portfolio": {
      "command": "node",
      "args": ["path/to/mcp-server/index.js"],
      "env": {
        "PORTFOLIO_API_URL": "https://<project>.vercel.app"
      }
    }
  }
}
```

---

## 5. 技術架構決策

### 5.1 專案結構

```
stock-api/
├── api/                    # Vercel Serverless Functions
│   ├── health.py
│   ├── fx.py
│   ├── quote/
│   │   └── [ticker].py
│   ├── stocks/
│   │   ├── us.py
│   │   └── tw.py
│   ├── options.py
│   ├── networth.py
│   └── trades.py
├── lib/                    # 共用邏輯
│   ├── notion.py           # Notion API client
│   ├── pricing.py          # yfinance 報價邏輯
│   └── calculator.py       # P&L 計算邏輯
├── mcp-server/             # MCP Server (Node.js)
│   ├── index.js
│   └── package.json
├── tests/                  # 測試
│   ├── unit/
│   │   ├── test_notion.py
│   │   ├── test_pricing.py
│   │   └── test_calculator.py
│   ├── features/           # BDD feature files
│   │   ├── us_stocks.feature
│   │   ├── tw_stocks.feature
│   │   ├── options.feature
│   │   ├── networth.feature
│   │   ├── notion_sync.feature
│   │   └── trade_journal.feature
│   └── steps/              # BDD step definitions
│       ├── stock_steps.py
│       ├── option_steps.py
│       ├── trade_steps.py
│       └── common_steps.py
├── docs/
│   └── SPEC.md
├── requirements.txt
├── vercel.json
├── CLAUDE.md
└── README.md
```

### 5.2 技術選擇

| 項目 | 選擇 | 原因 |
|------|------|------|
| API Framework | FastAPI | 已在使用，支援 async，自動 OpenAPI 文件 |
| 部署 | Vercel Serverless Functions (Python) | 已有 Vercel 設定，免費額度夠用 |
| 資料來源 | Notion API | 使用者已有 API Key，方便在 Notion UI 維護持倉 |
| 即時報價 | yfinance | 免費，支援美股/台股/匯率/選擇權鏈 |
| MCP Server | @modelcontextprotocol/sdk (Node.js) | 官方 SDK，Claude Code 原生支援 |
| 測試框架 | pytest + pytest-bdd | BDD feature files + unit tests |
| BDD 語法 | Gherkin (.feature) | 業界標準，可讀性高 |

### 5.3 環境變數

| 變數名 | 說明 | 用於 |
|--------|------|------|
| `NOTION_API_KEY` | Notion Integration Token | API Server |
| `NOTION_US_STOCKS_DB` | 美股持倉 Database ID | API Server |
| `NOTION_TW_STOCKS_DB` | 台股持倉 Database ID | API Server |
| `NOTION_OPTIONS_DB` | 選擇權 Database ID | API Server |
| `NOTION_BONDS_DB` | 債券 Database ID | API Server |
| `NOTION_LOANS_DB` | 貸款 Database ID | API Server |
| `NOTION_TRADES_DB` | 交易日誌 Database ID | API Server |
| `PORTFOLIO_API_URL` | API Server URL | MCP Server |

---

## 6. 非功能需求

- **回應時間**：yfinance 為外部依賴，單一股票查詢 < 2s，批次查詢（全部持倉）< 15s
- **可用性**：Vercel Serverless 自動擴展，無需自行管理
- **安全性**：初期無認證（個人使用）；未來可加 API Key header
- **CORS**：允許所有 origin、GET + POST 方法（POST 用於新增交易紀錄）
