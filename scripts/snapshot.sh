#!/bin/bash
# Fetch portfolio data and write into claude-project-instructions.md
# Replaces previous snapshot section, keeps instructions intact
# Usage: ./scripts/snapshot.sh

API="https://stock.cwithb.com"
FILE="docs/claude-project-instructions.md"
MARKER="<!-- SNAPSHOT START -->"

cd "$(dirname "$0")/.." || exit 1

echo "Fetching portfolio snapshot..."

# Remove previous snapshot (everything from MARKER to end of file)
if grep -q "$MARKER" "$FILE"; then
  sed -i '' "/$MARKER/,\$d" "$FILE"
fi

# Fetch all data
US=$(curl -s "$API/api/stocks/us")
TW=$(curl -s "$API/api/stocks/tw")
OPTIONS=$(curl -s "$API/api/options")
NW=$(curl -s "$API/api/networth")
FX=$(curl -s "$API/api/fx")
TRADES=$(curl -s "$API/api/trades?limit=20")

# Format snapshot as readable text (not raw JSON)
python3 -c "
import json, sys

us = json.loads('''$US''')
tw = json.loads('''$TW''')
opts = json.loads('''$OPTIONS''')
nw = json.loads('''$NW''')
fx = json.loads('''$FX''')
trades = json.loads('''$TRADES''')

print('## Portfolio Snapshot ($(date "+%Y-%m-%d %H:%M"))')
print()

# Net Worth
print('### Net Worth')
print(f\"- Net Worth: \\\${nw['net_worth_usd']:,.0f} USD / {nw['net_worth_twd']:,.0f} TWD\")
print(f\"- Total Assets: \\\${nw['assets']['total_assets_usd']:,.0f} USD\")
print(f\"- Total Loans: \\\${nw['liabilities']['total_loans_usd']:,.0f} USD ({nw['liabilities']['total_loans_twd']:,.0f} TWD)\")
print(f\"- Bond Income: \\\${nw['income']['bonds_monthly_net_usd']:,.0f}/mo net\")
print(f\"- FX Rate: {fx['USDTWD']}\")
print()

# US Stocks
print('### US Stocks')
s = us['summary']
print(f\"Total: \\\${s['total_market_value']:,.0f} | P&L: \\\${s['total_pl']:,.0f} ({s['total_pl_pct']}%)\")
print()
for acct, data in us['accounts'].items():
    t = data
    print(f\"**{acct}**: \\\${t['total_market_value']:,.0f} | P&L: \\\${t['total_pl']:,.0f} ({t['total_pl_pct']}%)\")
    for p in data['positions']:
        price = p.get('current_price') or 'N/A'
        pl = p.get('unrealized_pl', 'N/A')
        pct = p.get('pl_pct', 'N/A')
        sign = '+' if isinstance(pl, (int,float)) and pl > 0 else ''
        print(f\"  {p['ticker']}: {p['shares']} shares @ \\\${p['avg_cost']:.2f} → \\\${price} | P&L: {sign}\\\${pl} ({pct}%)\")
    print()

# TW Stocks
print('### TW Stocks')
s = tw['summary']
print(f\"Total: {s['total_market_value_twd']:,.0f} TWD (\\\${s['total_market_value_usd']:,.0f}) | P&L: {s['total_pl_twd']:,.0f} TWD ({s['total_pl_pct']}%)\")
print()
for acct, data in tw['accounts'].items():
    t = data
    print(f\"**{acct}**: {t['total_market_value_twd']:,.0f} TWD | P&L: {t['total_pl_twd']:,.0f} TWD ({t['total_pl_pct']}%)\")
    for p in data['positions']:
        price = p.get('current_price_twd') or 'N/A'
        pl = p.get('unrealized_pl_twd', 'N/A')
        pct = p.get('pl_pct', 'N/A')
        print(f\"  {p['ticker']} {p['name']}: {p['shares']} shares @ {p['avg_cost_twd']} → {price} | P&L: {pl} TWD ({pct}%)\")
    print()

# Options
print('### Options')
for o in opts['positions']:
    status = '🔴' if o['urgency'] == 'red' else '🟡' if o['urgency'] == 'yellow' else '🟢'
    print(f\"{status} {o['ticker']} {o['expiry']} \\\${o['strike']}{o['type'][0].upper()} x{o['qty']} | DTE:{o['dte']} {o['itm_otm']} | Premium: \\\${o['cost_basis']:.0f} | {o['action']}\")
print()

# Trades
print('### Recent Trades')
ts = trades['summary']
print(f\"Total: {ts['total_trades']} | Win: {ts['wins']} Loss: {ts['losses']} | Win Rate: {ts['win_rate']}% | Total P&L: \\\${ts['total_realized_pl']:,.0f}\")
for t in trades.get('trades', []):
    print(f\"  {t.get('date','')} {t.get('ticker','')} {t.get('action','')} {t.get('asset_type','')} x{t.get('qty','')} @ \\\${t.get('price','')} → {t.get('result','')}\")
" >> "$FILE" 2>/dev/null

# Add marker before the snapshot
TEMP=$(mktemp)
sed "s/^## Portfolio Snapshot/${MARKER}\n## Portfolio Snapshot/" "$FILE" > "$TEMP" && mv "$TEMP" "$FILE"

echo "Updated $FILE at $(date '+%Y-%m-%d %H:%M')"
