# Investment Strategy — 2026-2028

## Portfolio Snapshot (2026-03-07)

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
3. **Covered calls for income** — On stocks held in Firstrade & TW_Brokerage (options-enabled accounts).
4. **Sell puts to enter** — Use screened stocks as sell-put targets. Get paid to wait.
5. **Gradual cleanup** — Trim losing positions, redeploy into quality.
6. **Stop-loss discipline** — 投機 -10%, 投資 -20%, no exceptions.

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
| POOL | Firstrade | -45% | 投資 | **EXIT NOW** — sell immediately |
| HIMS | TW_Brokerage | -68% | 投機 | **EXIT NOW** — let covered call expire 3/21, then sell |
| GRAB | TW_Brokerage | -35% | 投機 | **EXIT NOW** — sell immediately ($398 position) |
| 1301 台塑 | Yongfeng_B | -35% | 投資 | **EXIT** — sell all 4000 shares |
| 1301 台塑 | Yongfeng_A | -50% | 投資 | **EXIT** — sell all 1000 shares |
| 2002 中鋼 | Yongfeng_B | -44% | 投資 | **EXIT** — sell all 4000 shares |
| 2012 春雨 | Yongfeng_B | -36% | 投機 | **EXIT** — sell all 2000 shares |
| 8499 鼎炫 | Yongfeng_B | -16% | 投機 | **EXIT** — sell 73 shares |
| SHOP | Firstrade | -11% | 投機 | **WATCH** — let covered call expire 3/21, reassess |
| MSFT | IBKR | -16% | 投資 | **WATCH** — approaching -20%, review at $390 |

---

## Account Roles

| Account | Can Trade Options? | Role |
|---------|-------------------|------|
| **Firstrade** ($138K) | YES | Active: Covered calls + Sell puts |
| **TW_Brokerage** ($131K) | YES | Active: Covered calls + Sell puts |
| **IBKR** ($26K) | YES | Growth: ETF DCA + small positions |
| **Cathay_US** ($78K) | NO (sub-custody) | Passive: ETF hold only, gradual transfer out |
| **Yongfeng_B** (1,446萬) | NO | TW stocks: Hold winners, trim losers |
| **Yongfeng_A** (388萬) | NO | TW stocks: 0050 + 聯發科 core |
| **Cathay_TW** (465萬) | NO | TW stocks: 台積電 + ETF core |

### Cathay_US Migration Plan
- Sub-custody = no options = wasted covered call potential
- Priority: Move AMD (46sh, +40%), NVDA (75sh, +49%), MSFT (23sh) to Firstrade/IBKR
- AMD + NVDA combined = $22K, enough for covered calls after transfer
- Keep BND ($6.7K) and BRK-B ($20.7K) in Cathay (no options needed)
- VOO ($10.9K) can stay — no covered calls needed on ETF

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
| AMD | Tech | Already own in Cathay_US, migrate for options |

### Tier 3 — Watchlist (accumulate on dips)
| Ticker | Sector | Why |
|--------|--------|-----|
| LLY | Healthcare | GLP-1 leader |
| COST | Consumer | Membership moat |
| AVGO | Tech | Broadcom, AI networking |
| CRM | Tech | Enterprise SaaS leader |
| UBER | Tech | Ride-sharing + delivery moat |

---

## Options Strategy — Sell Put → Covered Call Pipeline

### Step 1: Sell Puts on Quality Stocks
```
Screened stock (4/4) → Sell put (ATM or 5-10% OTM, 30-45 DTE)
→ Collect premium while waiting
→ If assigned: own quality stock at discount
→ If expires: repeat, accumulate premium
```

### Current Sell Put Targets
| Ticker | Account | Strike | DTE | Status |
|--------|---------|--------|-----|--------|
| AMZN | TW_Brokerage | $190 | 26d | Active (OTM $23) |
| CCJ | Firstrade | $110 | 6d | Active (ITM $0.3!) — may be assigned |
| CCJ | Firstrade | $115 | 41d | Active (ITM $5.3) — monitor |

### Next Sell Put Candidates (after cleanup frees capital)
| Ticker | Target Strike | Capital Needed | Account |
|--------|--------------|----------------|---------|
| V | ~$310 (5% OTM) | ~$31K | Firstrade (after POOL exit frees $2.1K) |
| MA | ~$540 (5% OTM) | ~$54K | TW_Brokerage (after HIMS/GRAB exit) |
| META | ~$600 (5% OTM) | ~$60K | Firstrade (needs capital) |
| AAPL | ~$220 (5% OTM) | ~$22K | TW_Brokerage |

### Step 2: Covered Calls on Holdings
```
Own 100+ shares → Sell covered call (15-20% OTM, 30-45 DTE)
→ Roll if ITM at 7 DTE
→ Close at 75%+ profit
→ Monthly income target: $500-1000/month
```

### Active Covered Calls
| Ticker | Account | Strike | DTE | Status |
|--------|---------|--------|-----|--------|
| TSM | TW_Brokerage | $400 | 14d | OTM $61 — will expire worthless |
| GOOG | Firstrade | $330 | 14d | OTM $32 — will expire worthless |
| SHOP | Firstrade | $150 | 14d | OTM $20 — will expire worthless |
| CCJ | TW_Brokerage | $145 | 20d | OTM $35 — will expire worthless |
| CCJ | Firstrade | $140 | 14d | OTM $30 — will expire worthless |
| MU | Firstrade | $440 | 26d | OTM $70 — will expire worthless |
| HIMS | TW_Brokerage | $20 | 14d | OTM $4 — last call before exit |

### Covered Call Pipeline (after cleanup + migration)
| Ticker | Shares | Account | Monthly Premium Est. |
|--------|--------|---------|---------------------|
| CCJ | 700 | Firstrade + TW_Brokerage | ~$400-600 |
| GOOG | 200 | Firstrade | ~$300-500 |
| TSM | 100 | TW_Brokerage | ~$200-400 |
| MU | 100 | Firstrade | ~$200-400 |
| AMD | 100 | After migration from Cathay_US | ~$200-300 |
| NVDA | 75→100 | After migration + accumulate | ~$300-500 |

**Estimated monthly covered call income: $1,500-2,700**

---

## Position Cleanup — Immediate Actions

### Week of 2026-03-10 (Priority)
1. **Sell POOL** (Firstrade) — market order, redeploy $2.1K into VOO
2. **Sell GRAB** (TW_Brokerage) — market order, $398 → add to AMZN put capital
3. **Sell 2012 春雨** (Yongfeng_B) — market order, redeploy $33.5K TWD into 0050
4. **Sell 8499 鼎炫** (Yongfeng_B) — market order, $19.4K TWD into 0050
5. **Sell 2002 中鋼** (Yongfeng_B) — market order, $79.6K TWD into 0050

### Week of 2026-03-17 (After options expire 3/21)
6. **Sell HIMS** (TW_Brokerage) — after HIMS $20 call expires 3/21
7. **Reassess SHOP** (Firstrade) — if still -10%+, exit after call expires

### March 2026
8. **Sell 1301 台塑** (Yongfeng_B, 4000sh + Yongfeng_A, 1000sh) — redeploy $251K TWD into 0050

### Redeployment Summary
| From | Amount | To | Account |
|------|--------|----|---------|
| POOL | $2.1K | VOO | Firstrade |
| GRAB + HIMS | $2.0K | Sell put capital | TW_Brokerage |
| 中鋼+春雨+鼎炫+台塑 | ~$443K TWD (~$14K) | 0050 DCA | Yongfeng_B/A |

---

## Hold & Grow (core positions)

| Ticker | Account | P&L | Strategy |
|--------|---------|-----|----------|
| 2330 台積電 | Yongfeng_B (5000sh) + Cathay_TW (2023sh) | +98~121% | Core hold. TSM ADR covered calls |
| 2454 聯發科 | Yongfeng_A (1000sh) | +122% | Core hold |
| 0050 | All TW (44,857sh) | +25~75% | Core ETF, DCA monthly + redeployment |
| 006208 | Cathay_TW (2,898sh) | +90% | Core ETF |
| 2317 鴻海 | Yongfeng_B (8,406sh) | +11% | Hold, AI server growth thesis |
| 1303 南亞 | Yongfeng_B (7,161sh) | +25% | Hold, cyclical recovery |
| CCJ | Firstrade + TW_Brokerage (700sh) | +19~24% | Covered calls + sell puts |
| GOOG | Firstrade + TW_Brokerage (300sh) | -3~23% | Covered calls, long-term hold |
| MU | Firstrade (100sh) | 0% | Covered calls |
| TSM | TW_Brokerage (100sh) | +14% | Covered calls |
| NVDA | Cathay_US (75sh) + IBKR (27sh) | -4~49% | Migrate to options account |
| AMD | Cathay_US (46sh) + IBKR (21sh) | -15~40% | Migrate, accumulate to 100sh |
| BRK-B | Cathay_US (41sh) + IBKR (9sh) | 0~9% | Long-term hold, no options needed |
| VOO/VTI/QQQ | Multiple | -4~13% | Core ETF, DCA monthly |

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

- **Weekly**: Review options positions, roll/close as needed. Check stop-losses.
- **Monthly**: DCA into ETFs (VOO, 0050), run `stock_screen.py`, sell new puts
- **Quarterly**: Review allocation %, trim losers, adjust targets, re-screen

---

## Screening & Monitoring

- `python3 scripts/stock_screen.py --us` — S&P 500 fundamental screen
- `python3 scripts/stock_screen.py --tw` — TW stocks (Huang Kuo-Hua method)
- API: `GET /api/financial/analyze/{ticker}` (with API key)
- MCP: `analyze_stock(ticker="NVDA")` for on-demand analysis

Screening results feed into sell-put target list.
