/**
 * Portfolio Calculator — frontend calculation engine.
 * Ported from lib/calculator.py
 */

const Calculator = {
  /**
   * Calculate stock position P&L.
   */
  calcStockPL(shares, avgCost, currentPrice) {
    const marketValue = Math.round(currentPrice * shares * 100) / 100;
    const costBasis = Math.round(avgCost * shares * 100) / 100;
    const pl = Math.round((marketValue - costBasis) * 100) / 100;
    const plPct = costBasis ? Math.round((pl / costBasis) * 10000) / 100 : 0;
    return { market_value: marketValue, cost_basis: costBasis, unrealized_pl: pl, pl_pct: plPct };
  },

  /**
   * Sum up totals for positions that have prices.
   */
  calcAccountTotals(positions) {
    let totalValue = 0, totalCost = 0;
    for (const p of positions) {
      if (p.current_price != null) {
        totalValue += p.market_value || 0;
        totalCost += p.cost_basis || 0;
      }
    }
    const totalPl = Math.round((totalValue - totalCost) * 100) / 100;
    const totalPlPct = totalCost ? Math.round((totalPl / totalCost) * 10000) / 100 : 0;
    return {
      total_market_value: Math.round(totalValue * 100) / 100,
      total_cost_basis: Math.round(totalCost * 100) / 100,
      total_pl: totalPl,
      total_pl_pct: totalPlPct,
    };
  },

  /**
   * Calculate days to expiry.
   */
  calcDTE(expiryStr) {
    const exp = new Date(expiryStr + 'T00:00:00');
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    return Math.round((exp - today) / 86400000);
  },

  /**
   * Determine urgency level based on DTE.
   */
  calcUrgency(days) {
    if (days <= 7) return 'red';
    if (days <= 21) return 'yellow';
    return 'green';
  },

  /**
   * Determine ITM/OTM status and distance.
   */
  calcITMOTM(underlyingPrice, strike, optType) {
    const diff = optType === 'put'
      ? underlyingPrice - strike
      : strike - underlyingPrice;
    if (diff > 0) return `OTM $${diff.toFixed(1)}`;
    return `ITM $${Math.abs(diff).toFixed(1)}`;
  },

  /**
   * Suggest action for an options position.
   */
  suggestAction(days, plPct, itmOtmStr) {
    if (days <= 0) return 'EXPIRED';
    if (days <= 7 && itmOtmStr.includes('OTM')) return 'Let expire';
    if (days <= 7 && itmOtmStr.includes('ITM')) return 'Close/Roll URGENT';
    if (plPct >= 75) return 'Close (75%+ profit)';
    if (days <= 21) return 'Monitor';
    return 'Hold';
  },

  /**
   * Calculate P&L for a short option position.
   * cost = premium received, currentValue = cost to buy back.
   */
  calcOptionPL(cost, currentValue) {
    if (currentValue == null) return { unrealized_pl: null, pl_pct: null };
    const pl = Math.round((cost - currentValue) * 100) / 100;
    const plPct = cost ? Math.round((pl / cost) * 1000) / 10 : null;
    return { unrealized_pl: pl, pl_pct: plPct };
  },

  /**
   * Calculate annual bond income (gross and net after tax).
   */
  calcBondIncome(bonds, taxRate = 0.24) {
    const gross = bonds.reduce((sum, b) => sum + b.face_value * b.coupon_rate, 0);
    const net = Math.round(gross * (1 - taxRate) * 100) / 100;
    return {
      annual_gross: Math.round(gross * 100) / 100,
      annual_net: net,
      monthly_net: Math.round(net / 12 * 100) / 100,
      withholding_tax_rate: `${Math.round(taxRate * 100)}%`,
    };
  },

  /**
   * Calculate total net worth.
   */
  calcNetWorth(usValueUSD, twValueTWD, bondsCostUSD, loansTWD, fxRate) {
    const twUSD = twValueTWD / fxRate;
    const loansUSD = loansTWD / fxRate;
    const totalAssets = usValueUSD + twUSD + bondsCostUSD;
    const netWorth = totalAssets - loansUSD;
    return {
      us_stocks_usd: Math.round(usValueUSD * 100) / 100,
      tw_stocks_twd: Math.round(twValueTWD * 100) / 100,
      tw_stocks_usd: Math.round(twUSD * 100) / 100,
      bonds_cost_usd: bondsCostUSD,
      total_assets_usd: Math.round(totalAssets * 100) / 100,
      total_loans_twd: loansTWD,
      total_loans_usd: Math.round(loansUSD * 100) / 100,
      net_worth_usd: Math.round(netWorth * 100) / 100,
      net_worth_twd: Math.round(netWorth * fxRate),
    };
  },
};
