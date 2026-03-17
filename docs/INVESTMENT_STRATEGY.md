# Investment Strategy — 2026-2028

## Portfolio Snapshot (2026-03-12)

| Category | Value | % of Assets |
|----------|-------|-------------|
| US Stocks | $372K | 12% |
| TW Stocks | $723K (2,300萬) | 23% |
| Bonds | $2,028K | 65% |
| **Total Assets** | **$3,123K** | |
| Loans | -$1,856K (5,905萬) | |
| **Net Worth** | **$1,267K (4,030萬)** | |

Bond monthly income: $6,909 (net after 24% tax)
Loan monthly payments: $3,131 (99,657 TWD)
**Bond surplus: +$3,778/month** (covers loans + extra)

---

## Core Principles

1. **Bonds = untouchable** — Core income, covers loan payments. Do not sell or rebalance.
2. **ETFs for compounding** — 0050, VOO, VTI, QQQ as long-term DCA base.
3. **Covered calls for income** — Weekly calls on all 100+ share positions.
4. **Sell puts to enter** — Use screened stocks as sell-put targets. Get paid to wait.
5. **Gradual cleanup** — Trim losing positions, redeploy into quality.
6. **Stop-loss discipline** — 投機 -10%, 投資 -20%, no exceptions.
7. **Tax optimization** — All covered call income in TW-opened overseas accounts (Firstrade_TW, IBKR_TW). Stay under 海外所得 750 萬 TWD threshold.

---

## Stop-Loss Rules

| Type | Threshold | Action |
|------|-----------|--------|
| Speculative (投機) | -10% | Exit immediately, no averaging down |
| Investment (投資) | -20% | Review fundamentals; exit if thesis broken |

- Speculative = short-term trades, sell puts, momentum plays
- Investment = core positions with strong fundamentals (screened stocks)
- Stop-loss is measured from entry price (or assignment price for puts)
- If stopped out, do not re-enter the same position for at least 30 days

### Current Stop-Loss Violations (action needed)
| Ticker | Account | P&L | Category | Action |
|--------|---------|-----|----------|--------|
| POOL | Firstrade_US | -46% | 投資 | **EXIT NOW** — sell immediately |
| HIMS | Firstrade_TW | -47% | 投機 | **EXIT NOW** — let $20 call be assigned 3/21 |
| GRAB | Firstrade_TW | -37% | 投機 | **EXIT NOW** — sell immediately ($390 position) |
| 1301 台塑 | Yongfeng_B (4000sh) | -39% | 投資 | **EXIT** — sell all |
| 1301 台塑 | Yongfeng_A (1000sh) | -53% | 投資 | **EXIT** — sell all |
| 2002 中鋼 | Yongfeng_B (4000sh) | -45% | 投資 | **EXIT** — sell all |
| 2012 春雨 | Yongfeng_B (2000sh) | -36% | 投機 | **EXIT** — sell all |
| 8499 鼎炫 | Yongfeng_B (73sh) | -16% | 投機 | **EXIT** — sell all |
| SHOP | Firstrade_US | -12% | 投機 | **EXIT** — sell after 3/21 call expires |
| MSFT | IBKR_TW | -17% | 投資 | **WATCH** — approaching -20%, review at $390 |

---

## Account Roles & Tax Strategy

| Account | Can Trade Options? | Role | Tax Treatment |
|---------|-------------------|------|---------------|
| **Firstrade_US** ($138K) | YES | Active: Covered calls + Sell puts | US-based, 1099 reporting |
| **Firstrade_TW** ($131K) | YES | Active: Covered calls + Sell puts | **海外所得，免稅** (< 750萬) |
| **IBKR_TW** ($26K) | YES | Growth: Covered calls after migration | **海外所得，免稅** (< 750萬) |
| **Cathay_US** ($78K) | NO (複委託) | Passive: Gradually transfer out | 複委託自動申報 |
| **Yongfeng_B** (1,446萬) | NO | TW stocks: Hold winners, trim losers | 台股免證所稅 |
| **Yongfeng_A** (388萬) | NO | TW stocks: 0050 + 聯發科 core | 台股免證所稅 |
| **Cathay_TW** (465萬) | NO | TW stocks: 台積電 + ETF core | 台股免證所稅 |

### Cathay_US (複委託) Migration Plan

Sub-custody = no options = wasted covered call potential. Transfer to IBKR_TW for options.

| Stock | Shares | Current Value | Action |
|-------|--------|--------------|--------|
| **NVDA** | 75.3 | ~$14.1K | → IBKR_TW (merge with 27sh = 102sh, sell 1 call) |
| **AMD** | 45.8 | ~$9.5K | → IBKR_TW (merge with 21sh = 67sh, buy 33 more) |
| MSFT | 22.6 | ~$9.1K | → IBKR_TW (merge with 5sh = 28sh, too far from 100) |
| BRK-B | 41.5 | ~$20.4K | Stay — no options needed |
| VOO | 17.6 | ~$10.9K | Stay — ETF, no options needed |
| VTI | 15.3 | ~$5.1K | Stay — ETF |
| QQQ | 3.4 | ~$2.1K | Stay — ETF |
| BND | 90.3 | ~$6.7K | Stay — bond ETF |
| TSLA | 2.4 | ~$1.0K | Sell — tiny position |

**Migration priority: NVDA first (immediately 100+ shares), then AMD (need to buy 33 more).**

---

## Covered Call Strategy — Weekly Selling

### Philosophy
- **All positions with 100+ shares sell weekly covered calls**
- Sell every Friday evening (Taiwan time 21:30) for next Friday expiry
- Strike = current price + 5~8% OTM
- If assigned, sell put to re-enter
- Close at 75%+ profit mid-week if opportunity arises

### Weekly SOP (每週五晚上 9:30)
```
1. Confirm all expiring calls expired OTM ✅
2. CCJ  × 7 calls → current price + 5~8%
3. GOOG × 3 calls → current price + 5~7%
4. MU   × 1 call  → current price + 5~8%
5. TSM  × 1 call  → current price + 5~7%
6. NVDA × 1 call  → current price + 5~7% (after migration)
7. AMD  × 1 call  → current price + 5~7% (after accumulation to 100sh)
Total: ~15 minutes
```

### Covered Call Income Projection

| Ticker | Shares | Account | Calls/wk | Est. Weekly | Est. Monthly |
|--------|--------|---------|----------|-------------|-------------|
| CCJ | 700 | Firstrade_US + TW | 7 | $210-420 | $840-1,680 |
| GOOG | 300 | Firstrade_US + TW | 3 | $150-300 | $600-1,200 |
| MU | 100 | Firstrade_US | 1 | $75-125 | $300-500 |
| TSM | 100 | Firstrade_TW | 1 | $60-100 | $240-400 |
| NVDA | 102 | IBKR_TW (after migration) | 1 | $75-125 | $300-500 |
| AMD | 100 | IBKR_TW (after accumulation) | 1 | $50-100 | $200-400 |
| **Total** | | | **14** | **$620-1,170** | **$2,480-4,680** |

**Conservative estimate: $2,500/month from covered calls alone.**

---

## Options Strategy — Sell Put → Covered Call Pipeline

### Step 1: Sell Puts on Quality Stocks
```
Screened stock (4/4) → Sell put (ATM or 5-10% OTM, 30-45 DTE)
→ Collect premium while waiting
→ If assigned: own quality stock at discount → start selling covered calls
→ If expires: repeat, accumulate premium
```

### Active Options Positions (2026-03-12)
| Account | Ticker | Expiry | Strike | Type | Qty | Status |
|---------|--------|--------|--------|------|-----|--------|
| Firstrade_US | CCJ | 3/13 | $110 | Put | -1 | OTM $9.5 → expires tomorrow ✅ |
| Firstrade_US | GOOG | 3/21 | $330 | Call | -1 | OTM $20 → will expire ✅ |
| Firstrade_US | SHOP | 3/21 | $150 | Call | -1 | OTM $21 → will expire ✅ |
| Firstrade_US | CCJ | 3/21 | $140 | Call | -1 | OTM $20.5 → will expire ✅ |
| Firstrade_TW | TSM | 3/21 | $400 | Call | -1 | OTM $44 → will expire ✅ |
| Firstrade_TW | MU | 3/21 | $310 | Put | -1 | OTM $107 → will expire ✅ |
| Firstrade_TW | HIMS | 3/21 | $20 | Call | -1 | **ITM $5.9** → let assign, exit HIMS |
| Firstrade_TW | CCJ | 3/27 | $145 | Call | -2 | OTM $25.5 → will expire ✅ |
| Firstrade_US | MU | 4/2 | $440 | Call | -1 | OTM $22.5 → hold |
| Firstrade_TW | AMZN | 4/2 | $190 | Put | -1 | OTM $24.6 → hold |
| Firstrade_US | ONDS | 4/2 | $8 | Put | -1 | hold |
| Firstrade_US | CCJ | 4/17 | $115 | Put | -1 | **OTM only $4.5** ⚠️ watch closely |

### Next Sell Put Candidates (after cleanup frees capital)
| Ticker | Target Strike | Capital Needed | Account |
|--------|--------------|----------------|---------|
| V | ~$310 (5% OTM) | ~$31K | Firstrade_TW |
| MA | ~$540 (5% OTM) | ~$54K | Firstrade_TW |
| AAPL | ~$220 (5% OTM) | ~$22K | Firstrade_TW |
| META | ~$600 (5% OTM) | ~$60K | Firstrade_TW |

**Note: Prioritize sell puts in Firstrade_TW for tax optimization.**

---

## Position Cleanup — Execution Plan

### Phase 1: This Week (2026-03-12~14)
1. **Sell POOL** (Firstrade_US) — market order, $2.1K → buy VOO
2. **Sell GRAB** (Firstrade_TW) — market order, $390 → sell put capital
3. **Sell 2012 春雨** (Yongfeng_B) — 2000 shares → buy 0050
4. **Sell 8499 鼎炫** (Yongfeng_B) — 73 shares → buy 0050
5. **Sell 2002 中鋼** (Yongfeng_B) — 4000 shares → buy 0050

### Phase 2: After 3/21 Options Expiry
6. **HIMS** — $20 call assigned, shares called away at $20, done
7. **Sell SHOP** (Firstrade_US) — exit after call expires
8. **Sell 1301 台塑** — Yongfeng_B 4000sh + Yongfeng_A 1000sh → buy 0050

### Phase 3: Cathay_US Migration (March-April 2026)
9. **Transfer NVDA 75sh** → IBKR_TW (combine with 27sh = 102sh → sell call)
10. **Transfer AMD 46sh** → IBKR_TW (combine with 21sh = 67sh)
11. **Buy AMD 33sh** in IBKR_TW (total 100sh → sell call)
12. **Transfer MSFT 23sh** → IBKR_TW (combine with 5sh = 28sh, long-term hold)
13. Sell TSLA 2.4sh (tiny position)

### Redeployment Summary
| From | Amount | To | Account |
|------|--------|----|---------|
| POOL | $2.1K | VOO | Firstrade_US |
| GRAB + HIMS | ~$2.4K | Sell put capital | Firstrade_TW |
| SHOP | ~$12.9K | Sell put capital | Firstrade_US |
| 中鋼+春雨+鼎炫+台塑 | ~$443K TWD (~$14K) | 0050 DCA | Yongfeng_B/A |
| Cathay NVDA+AMD+MSFT | ~$32.7K | Covered call base | IBKR_TW |

---

## Screened Quality Stocks (S&P 500, 4/4 score)

From `stock_screen.py --us` results. These are sell-put and accumulation targets:

### Tier 1 — Mega Cap, Strong Moat (sell put priority)
| Ticker | Sector | Why |
|--------|--------|-----|
| AAPL | Tech | FCF machine, negative CCC, ROIC 60%+ |
| MSFT | Tech | Cloud growth, ROIC 30%+, IC 40x+ |
| GOOG | Tech | Ad monopoly, massive FCF, already own |
| AMZN | Consumer | AWS + retail, improving margins (already selling puts) |
| META | Tech | Ad duopoly, ROIC 25%+, buybacks |
| V | Financial | Payment moat, 50%+ net margin, asset-light |
| MA | Financial | Same as V, duopoly |

### Tier 2 — Growth + Quality (covered call + hold)
| Ticker | Sector | Why |
|--------|--------|-----|
| NVDA | Tech | AI leader, already own, covered call candidate |
| TSM | Tech | Foundry monopoly, already own + doing covered calls |
| CCJ | Energy | Uranium thesis, already own + doing covered calls |
| MU | Tech | Memory cycle play, already own + doing covered calls |
| AMD | Tech | Migrating from Cathay_US, accumulate to 100sh |

### Tier 3 — Watchlist (accumulate on dips)
| Ticker | Sector | Why |
|--------|--------|-----|
| LLY | Healthcare | GLP-1 leader |
| COST | Consumer | Membership moat |
| AVGO | Tech | Broadcom, AI networking |
| CRM | Tech | Enterprise SaaS leader |
| UBER | Tech | Ride-sharing + delivery moat |

---

## Hold & Grow (core positions)

| Ticker | Account | P&L | Strategy |
|--------|---------|-----|----------|
| 2330 台積電 | Yongfeng_B (5000sh) + Cathay_TW (2023sh) | +127% | Core hold. TSM ADR covered calls |
| 2454 聯發科 | Yongfeng_A (1000sh) | +122% | Core hold |
| 0050 | All TW (44,857sh) | +25~75% | Core ETF, DCA monthly + redeployment |
| 006208 | Cathay_TW (2,898sh) | +93% | Core ETF |
| 2317 鴻海 | Yongfeng_B (8,406sh) | +9% | Hold, AI server growth thesis |
| 1303 南亞 | Yongfeng_B (7,161sh) | +25% | Hold, cyclical recovery |
| CCJ | Firstrade_US + Firstrade_TW (700sh) | +29~35% | Weekly covered calls |
| GOOG | Firstrade_US + Firstrade_TW (300sh) | +1~28% | Weekly covered calls |
| MU | Firstrade_US (100sh) | +13% | Weekly covered calls |
| TSM | Firstrade_TW (100sh) | +20% | Weekly covered calls |
| NVDA | IBKR_TW (102sh after migration) | +57% | Weekly covered calls |
| AMD | IBKR_TW (100sh after migration + buy) | +50% | Weekly covered calls |
| BRK-B | Cathay_US (41sh) + IBKR_TW (9sh) | +7% | Long-term hold, no options needed |
| VOO/VTI/QQQ | Multiple | -1~14% | Core ETF, DCA monthly |

---

## Passive Income Summary (target state)

| Source | Monthly Income | Tax |
|--------|---------------|-----|
| Bond interest (net) | $6,909 | 24% already withheld |
| Covered calls (14 contracts/week) | $2,500-4,700 | **Free** (海外所得 < 750萬) |
| **Total** | **$9,400-11,600/month** | |
| Loan payments | -$3,131 | |
| **Net passive income** | **$6,300-8,500/month** | |

---

## Target Allocation (2028 goal)

| Category | Current | Target | Action |
|----------|---------|--------|--------|
| Bonds | 65% | 60% | Natural shift as stocks grow |
| US ETFs (VOO/VTI/QQQ) | 3% | 10% | DCA monthly + POOL redeployment |
| US Quality Stocks | 9% | 10% | Sell put → covered call pipeline |
| TW ETFs (0050/006208) | 5% | 8% | DCA + redeploy from losers (~$14K) |
| TW Quality Stocks | 18% | 12% | Trim losers (台塑/中鋼/春雨), keep 台積電+聯發科 |

---

## Rebalance Schedule

- **Weekly (Friday 21:30 TW time)**: Sell covered calls on all positions. Check stop-losses.
- **Monthly**: DCA into ETFs (VOO, 0050), run `stock_screen.py`, sell new puts
- **Quarterly**: Review allocation %, trim losers, adjust targets, re-screen

---

## Screening & Monitoring

- `python3 scripts/stock_screen.py --us` — S&P 500 fundamental screen
- `python3 scripts/stock_screen.py --tw` — TW stocks (Huang Kuo-Hua method)
- API: `GET /api/financial/analyze/{ticker}` (with API key)
- MCP: `get_us_stocks`, `get_options`, `get_networth` for portfolio data
- Google Sheets: Single source of truth for all positions

Screening results feed into sell-put target list.
