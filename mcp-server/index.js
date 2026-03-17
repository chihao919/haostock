#!/usr/bin/env node

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { readFileSync, writeFileSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";
import { google } from "googleapis";

const __dirname = dirname(fileURLToPath(import.meta.url));

const API_URL = process.env.PORTFOLIO_API_URL || "https://stock.cwithb.com";

// --- Price Cache (60s TTL) ---

const _priceCache = {};
const PRICE_TTL = 60_000;

async function fetchPrice(ticker) {
  const now = Date.now();
  if (_priceCache[ticker] && now - _priceCache[ticker].ts < PRICE_TTL) {
    return _priceCache[ticker].price;
  }
  try {
    const resp = await fetch(`${API_URL}/api/quote/${encodeURIComponent(ticker)}`);
    if (!resp.ok) return null;
    const data = await resp.json();
    _priceCache[ticker] = { price: data.price, ts: now };
    return data.price;
  } catch {
    return null;
  }
}

async function fetchFxRate() {
  try {
    const resp = await fetch(`${API_URL}/api/fx`);
    if (!resp.ok) return 31.8;
    const data = await resp.json();
    return data.rate || 31.8;
  } catch {
    return 31.8;
  }
}

// --- Google Sheets ---

const CREDENTIALS_PATH = process.env.GOOGLE_SA_KEY || resolve(process.env.HOME, ".config/claude-sheets/credentials.json");
const SPREADSHEET_ID = process.env.PORTFOLIO_SHEET_ID || "1wtFrdco3yNf2cXGUvyDKUPR0B5ENP9OSl0ci1jwk-mE";

let sheetsApi = null;
function getSheets() {
  if (sheetsApi) return sheetsApi;
  const auth = new google.auth.GoogleAuth({
    keyFile: CREDENTIALS_PATH,
    scopes: ["https://www.googleapis.com/auth/spreadsheets"],
  });
  sheetsApi = google.sheets({ version: "v4", auth });
  return sheetsApi;
}

async function readSheet(name) {
  const sheets = getSheets();
  const res = await sheets.spreadsheets.values.get({
    spreadsheetId: SPREADSHEET_ID,
    range: `${name}!A1:Z1000`,
  });
  const rows = res.data.values || [];
  if (rows.length <= 1) return [];
  const headers = rows[0];
  return rows.slice(1).map(row => {
    const obj = {};
    headers.forEach((h, i) => { obj[h] = row[i] || ""; });
    return obj;
  });
}

async function readAllSheets() {
  const sheetNames = ["US_Stocks", "TW_Stocks", "Options", "Bonds", "Loans", "Income", "Settings"];
  const sheets = getSheets();
  const ranges = sheetNames.map(s => `${s}!A1:Z1000`);
  const res = await sheets.spreadsheets.values.batchGet({
    spreadsheetId: SPREADSHEET_ID,
    ranges,
  });
  const result = {};
  for (const vr of (res.data.valueRanges || [])) {
    const name = vr.range.split("!")[0].replace(/'/g, "");
    const rows = vr.values || [];
    if (rows.length <= 1) { result[name] = []; continue; }
    const headers = rows[0];
    result[name] = rows.slice(1).map(row => {
      const obj = {};
      headers.forEach((h, i) => { obj[h] = row[i] || ""; });
      return obj;
    });
  }
  return result;
}

// --- Calculation Helpers ---

function calcStockPL(shares, avgCost, currentPrice) {
  const marketValue = Math.round(currentPrice * shares * 100) / 100;
  const costBasis = Math.round(avgCost * shares * 100) / 100;
  const pl = Math.round((marketValue - costBasis) * 100) / 100;
  const plPct = costBasis ? Math.round((pl / costBasis) * 10000) / 100 : 0;
  return { market_value: marketValue, cost_basis: costBasis, unrealized_pl: pl, pl_pct: plPct };
}

function calcAccountTotals(positions) {
  const priced = positions.filter(p => p.current_price);
  const totalValue = priced.reduce((s, p) => s + (p.market_value || 0), 0);
  const totalCost = priced.reduce((s, p) => s + (p.cost_basis || 0), 0);
  const totalPL = Math.round((totalValue - totalCost) * 100) / 100;
  const totalPLPct = totalCost ? Math.round((totalPL / totalCost) * 10000) / 100 : 0;
  return {
    total_market_value: Math.round(totalValue * 100) / 100,
    total_cost_basis: Math.round(totalCost * 100) / 100,
    total_pl: totalPL,
    total_pl_pct: totalPLPct,
  };
}

function calcDTE(expiryStr) {
  const exp = new Date(expiryStr + "T00:00:00");
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.round((exp - today) / 86400000);
}

function calcUrgency(days) {
  if (days <= 7) return "red";
  if (days <= 21) return "yellow";
  return "green";
}

function calcItmOtm(underlyingPrice, strike, optType) {
  const diff = optType.toLowerCase() === "put"
    ? underlyingPrice - strike
    : strike - underlyingPrice;
  return diff > 0 ? `OTM $${diff.toFixed(1)}` : `ITM $${Math.abs(diff).toFixed(1)}`;
}

function suggestAction(days, plPct, itmOtmStr) {
  if (days <= 0) return "EXPIRED";
  if (days <= 7 && itmOtmStr.includes("OTM")) return "Let expire";
  if (days <= 7 && itmOtmStr.includes("ITM")) return "Close/Roll URGENT";
  if (plPct >= 75) return "Close (75%+ profit)";
  if (days <= 21) return "Monitor";
  return "Hold";
}

// --- MCP Server ---

const server = new McpServer({
  name: "portfolio",
  version: "2.0.0",
});

// --- Portfolio Tools (Google Sheets + Yahoo Finance) ---

server.tool("get_us_stocks", "查詢所有美股持倉及損益（按帳戶分組，資料來源：Google Sheets）", {}, async () => {
  const rows = await readSheet("US_Stocks");
  // Collect unique tickers and fetch prices in parallel
  const tickers = [...new Set(rows.map(r => r.ticker))];
  const prices = {};
  await Promise.all(tickers.map(async t => { prices[t] = await fetchPrice(t); }));

  // Group by account
  const accounts = {};
  for (const row of rows) {
    const acct = row.account || "Unknown";
    if (!accounts[acct]) accounts[acct] = { positions: [] };
    const shares = parseFloat(row.shares) || 0;
    const avgCost = parseFloat(row.avg_cost) || 0;
    const price = prices[row.ticker];
    const pos = { ticker: row.ticker, shares, avg_cost: avgCost, current_price: price };
    if (price) Object.assign(pos, calcStockPL(shares, avgCost, price));
    accounts[acct].positions.push(pos);
  }
  // Account and overall totals
  let allPositions = [];
  for (const [name, acct] of Object.entries(accounts)) {
    Object.assign(acct, calcAccountTotals(acct.positions));
    allPositions = allPositions.concat(acct.positions);
  }
  const summary = calcAccountTotals(allPositions);
  const result = { accounts, summary, timestamp: new Date().toISOString() };
  return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
});

server.tool("get_tw_stocks", "查詢所有台股持倉及損益（TWD/USD 雙幣，資料來源：Google Sheets）", {}, async () => {
  const [rows, fxRate] = await Promise.all([readSheet("TW_Stocks"), fetchFxRate()]);
  const tickers = [...new Set(rows.map(r => r.ticker))];
  const prices = {};
  await Promise.all(tickers.map(async t => { prices[t] = await fetchPrice(t); }));

  const accounts = {};
  for (const row of rows) {
    const acct = row.account || "Unknown";
    if (!accounts[acct]) accounts[acct] = { positions: [] };
    const shares = parseFloat(row.shares) || 0;
    const avgCost = parseFloat(row.avg_cost_twd) || 0;
    const price = prices[row.ticker];
    const pos = { ticker: row.ticker, name: row.name, shares, avg_cost_twd: avgCost, current_price_twd: price };
    if (price) {
      const pl = calcStockPL(shares, avgCost, price);
      pos.market_value_twd = pl.market_value;
      pos.market_value_usd = Math.round(pl.market_value / fxRate * 100) / 100;
      pos.cost_basis_twd = pl.cost_basis;
      pos.unrealized_pl_twd = pl.unrealized_pl;
      pos.pl_pct = pl.pl_pct;
    }
    accounts[acct].positions.push(pos);
  }
  let allPositions = [];
  for (const [name, acct] of Object.entries(accounts)) {
    const priced = acct.positions.filter(p => p.current_price_twd);
    acct.total_market_value_twd = Math.round(priced.reduce((s, p) => s + (p.market_value_twd || 0), 0) * 100) / 100;
    acct.total_market_value_usd = Math.round(acct.total_market_value_twd / fxRate * 100) / 100;
    acct.total_cost_twd = Math.round(priced.reduce((s, p) => s + (p.cost_basis_twd || 0), 0) * 100) / 100;
    acct.total_pl_twd = Math.round((acct.total_market_value_twd - acct.total_cost_twd) * 100) / 100;
    acct.total_pl_pct = acct.total_cost_twd ? Math.round(acct.total_pl_twd / acct.total_cost_twd * 10000) / 100 : 0;
    allPositions = allPositions.concat(acct.positions);
  }
  const priced = allPositions.filter(p => p.current_price_twd);
  const totalMV = priced.reduce((s, p) => s + (p.market_value_twd || 0), 0);
  const totalCost = priced.reduce((s, p) => s + (p.cost_basis_twd || 0), 0);
  const summary = {
    total_market_value_twd: Math.round(totalMV * 100) / 100,
    total_market_value_usd: Math.round(totalMV / fxRate * 100) / 100,
    total_cost_twd: Math.round(totalCost * 100) / 100,
    total_pl_twd: Math.round((totalMV - totalCost) * 100) / 100,
    total_pl_pct: totalCost ? Math.round((totalMV - totalCost) / totalCost * 10000) / 100 : 0,
  };
  return { content: [{ type: "text", text: JSON.stringify({ usdtwd_rate: fxRate, accounts, summary, timestamp: new Date().toISOString() }, null, 2) }] };
});

server.tool("get_options", "查詢所有選擇權倉位、損益、及建議動作（資料來源：Google Sheets）", {}, async () => {
  const rows = await readSheet("Options");
  const tickers = [...new Set(rows.map(r => r.ticker))];
  const prices = {};
  await Promise.all(tickers.map(async t => { prices[t] = await fetchPrice(t); }));

  const positions = [];
  let totalCost = 0, totalValue = 0;
  for (const row of rows) {
    const strike = parseFloat(row.strike) || 0;
    const qty = parseFloat(row.qty) || 0;
    const cost = parseFloat(row.cost) || 0;
    const underlyingPrice = prices[row.ticker];
    const days = row.expiry ? calcDTE(row.expiry) : null;
    const itmOtm = underlyingPrice ? calcItmOtm(underlyingPrice, strike, row.type || "call") : null;

    // Estimate current option value (simple intrinsic for short positions)
    let currentValue = null;
    if (underlyingPrice && row.type) {
      const isCall = row.type.toLowerCase() === "call";
      const intrinsic = isCall ? Math.max(underlyingPrice - strike, 0) : Math.max(strike - underlyingPrice, 0);
      currentValue = Math.round(intrinsic * Math.abs(qty) * 100 * 100) / 100;
    }

    const pl = cost - (currentValue || 0);
    const plPct = cost ? Math.round(pl / cost * 10000) / 100 : 0;
    const action = days !== null && itmOtm ? suggestAction(days, plPct, itmOtm) : "Unknown";

    totalCost += cost;
    if (currentValue !== null) totalValue += currentValue;

    positions.push({
      account: row.account, ticker: row.ticker, expiry: row.expiry,
      strike, type: row.type, qty, underlying_price: underlyingPrice,
      itm_otm: itmOtm, dte: days, urgency: days !== null ? calcUrgency(days) : null,
      cost_basis: cost, current_value: currentValue,
      unrealized_pl: Math.round(pl * 100) / 100, pl_pct: plPct, action,
    });
  }

  const summary = {
    total_cost_basis: Math.round(totalCost * 100) / 100,
    total_current_value: Math.round(totalValue * 100) / 100,
    total_pl: Math.round((totalCost - totalValue) * 100) / 100,
  };
  return { content: [{ type: "text", text: JSON.stringify({ positions, summary, timestamp: new Date().toISOString() }, null, 2) }] };
});

server.tool(
  "get_quote",
  "查詢單一股票即時報價",
  { ticker: z.string().describe("股票代碼，例如 NVDA, 2330.TW") },
  async ({ ticker }) => {
    const resp = await fetch(`${API_URL}/api/quote/${encodeURIComponent(ticker)}`);
    if (!resp.ok) throw new Error(`Quote API error: ${resp.status}`);
    const data = await resp.json();
    return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
  }
);

server.tool("get_networth", "查詢完整淨資產總覽（資產、負債、收入，資料來源：Google Sheets）", {}, async () => {
  const [all, fxRate] = await Promise.all([readAllSheets(), fetchFxRate()]);

  // US stocks value
  const usTickers = [...new Set((all.US_Stocks || []).map(r => r.ticker))];
  const twTickers = [...new Set((all.TW_Stocks || []).map(r => r.ticker))];
  const allTickers = [...usTickers, ...twTickers];
  const prices = {};
  await Promise.all(allTickers.map(async t => { prices[t] = await fetchPrice(t); }));

  let usStocksUsd = 0;
  for (const row of (all.US_Stocks || [])) {
    const price = prices[row.ticker];
    if (price) usStocksUsd += price * (parseFloat(row.shares) || 0);
  }

  let twStocksTwd = 0;
  for (const row of (all.TW_Stocks || [])) {
    const price = prices[row.ticker];
    if (price) twStocksTwd += price * (parseFloat(row.shares) || 0);
  }

  // Bonds
  let bondsCostUsd = 0;
  let bondsAnnualGross = 0;
  for (const row of (all.Bonds || [])) {
    const faceValue = parseFloat(row.face_value) || 0;
    const couponRate = parseFloat(row.coupon_rate) || 0;
    bondsCostUsd += parseFloat(row.cost) || 0;
    bondsAnnualGross += faceValue * couponRate / 100;
  }

  // Tax rate from settings
  const settings = {};
  for (const row of (all.Settings || [])) { settings[row.key] = row.value; }
  const taxRate = parseFloat(settings.tax_rate) || 0.24;
  const bondsAnnualNet = bondsAnnualGross * (1 - taxRate);

  // Loans
  let totalLoansTwd = 0, monthlyPaymentsTwd = 0;
  for (const row of (all.Loans || [])) {
    totalLoansTwd += parseFloat(row.balance_twd) || 0;
    monthlyPaymentsTwd += parseFloat(row.monthly_payment_twd) || 0;
  }

  const totalAssetsUsd = Math.round((usStocksUsd + twStocksTwd / fxRate + bondsCostUsd) * 100) / 100;
  const totalLoansUsd = Math.round(totalLoansTwd / fxRate * 100) / 100;
  const netWorthUsd = Math.round((totalAssetsUsd - totalLoansUsd) * 100) / 100;

  const result = {
    usdtwd_rate: fxRate,
    assets: {
      us_stocks_usd: Math.round(usStocksUsd * 100) / 100,
      tw_stocks_twd: Math.round(twStocksTwd * 100) / 100,
      tw_stocks_usd: Math.round(twStocksTwd / fxRate * 100) / 100,
      bonds_cost_usd: Math.round(bondsCostUsd * 100) / 100,
      total_assets_usd: totalAssetsUsd,
    },
    liabilities: {
      total_loans_twd: Math.round(totalLoansTwd * 100) / 100,
      total_loans_usd: totalLoansUsd,
      monthly_payments_twd: Math.round(monthlyPaymentsTwd * 100) / 100,
    },
    income: {
      bonds_annual_gross_usd: Math.round(bondsAnnualGross * 100) / 100,
      bonds_annual_net_usd: Math.round(bondsAnnualNet * 100) / 100,
      bonds_monthly_net_usd: Math.round(bondsAnnualNet / 12 * 100) / 100,
      withholding_tax_rate: taxRate,
    },
    net_worth_usd: netWorthUsd,
    net_worth_twd: Math.round(netWorthUsd * fxRate * 100) / 100,
    timestamp: new Date().toISOString(),
  };
  return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
});

server.tool("get_fx_rate", "查詢 USD/TWD 即時匯率", {}, async () => {
  const rate = await fetchFxRate();
  return { content: [{ type: "text", text: JSON.stringify({ rate, timestamp: new Date().toISOString() }, null, 2) }] };
});

server.tool(
  "get_trades",
  "查詢交易歷史紀錄（資料來源：Google Sheets Trades 工作表）",
  {
    ticker: z.string().optional().describe("篩選特定股票代碼"),
    result: z.enum(["Win", "Loss", "Breakeven"]).optional().describe("篩選交易結果"),
    asset_type: z.enum(["Stock", "Option"]).optional().describe("篩選資產類型"),
    limit: z.number().optional().describe("回傳筆數上限，預設 50"),
  },
  async ({ ticker, result, asset_type, limit }) => {
    let trades = await readSheet("Trades");
    if (ticker) trades = trades.filter(t => t.ticker === ticker);
    if (result) trades = trades.filter(t => t.result === result);
    if (asset_type) trades = trades.filter(t => t.asset_type === asset_type);
    // Sort by date descending
    trades.sort((a, b) => (b.date || "").localeCompare(a.date || ""));
    if (limit) trades = trades.slice(0, limit);

    // Compute summary stats
    const wins = trades.filter(t => t.result === "Win").length;
    const losses = trades.filter(t => t.result === "Loss").length;
    const totalPL = trades.reduce((s, t) => s + (parseFloat(t.pl) || 0), 0);
    const summary = { total_trades: trades.length, wins, losses, total_pl: Math.round(totalPL * 100) / 100 };

    return { content: [{ type: "text", text: JSON.stringify({ trades, summary, timestamp: new Date().toISOString() }, null, 2) }] };
  }
);

server.tool(
  "add_trade",
  "新增一筆交易紀錄到 Google Sheets",
  {
    date: z.string().describe("交易日期 YYYY-MM-DD"),
    ticker: z.string().describe("股票/選擇權代碼"),
    action: z.enum(["Buy", "Sell", "Open", "Close", "Roll"]).describe("交易動作"),
    asset_type: z.enum(["Stock", "Option"]).describe("資產類型"),
    qty: z.number().describe("數量"),
    price: z.number().describe("成交價格"),
    total_amount: z.number().describe("總金額 USD"),
    reason: z.string().describe("為什麼做這筆交易"),
    account: z.string().describe("券商帳戶"),
    pl: z.number().optional().describe("已實現損益"),
    result: z.enum(["Win", "Loss", "Breakeven"]).optional().describe("交易結果"),
    lesson: z.string().optional().describe("事後檢討/改進方法"),
    tags: z.array(z.string()).optional().describe("標籤分類"),
  },
  async (params) => {
    const sheets = getSheets();
    // Ensure Trades sheet exists with headers
    try {
      await sheets.spreadsheets.values.get({
        spreadsheetId: SPREADSHEET_ID,
        range: "Trades!A1:M1",
      });
    } catch {
      // Create Trades sheet if missing
      try {
        await sheets.spreadsheets.batchUpdate({
          spreadsheetId: SPREADSHEET_ID,
          requestBody: {
            requests: [{ addSheet: { properties: { title: "Trades" } } }],
          },
        });
      } catch { /* sheet might already exist */ }
      const headers = ["date", "ticker", "action", "asset_type", "qty", "price", "total_amount", "account", "pl", "result", "reason", "lesson", "tags"];
      await sheets.spreadsheets.values.update({
        spreadsheetId: SPREADSHEET_ID,
        range: "Trades!A1:M1",
        valueInputOption: "RAW",
        requestBody: { values: [headers] },
      });
    }

    const row = [
      params.date, params.ticker, params.action, params.asset_type,
      String(params.qty), String(params.price), String(params.total_amount),
      params.account, params.pl != null ? String(params.pl) : "",
      params.result || "", params.reason, params.lesson || "",
      params.tags ? params.tags.join(",") : "",
    ];

    await sheets.spreadsheets.values.append({
      spreadsheetId: SPREADSHEET_ID,
      range: "Trades!A1",
      valueInputOption: "RAW",
      insertDataOption: "INSERT_ROWS",
      requestBody: { values: [row] },
    });

    // Non-blocking webhook: notify invest agent of trade completion
    const API_KEY = process.env.FINANCIAL_API_KEY || "";
    if (API_KEY && (params.action === "Close" || params.action === "Sell" || params.action === "Roll")) {
      fetch(`${API_URL}/api/invest/complete`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "x-api-key": API_KEY },
        body: JSON.stringify({ ticker: params.ticker }),
      }).catch(() => { /* non-blocking */ });
    }

    return { content: [{ type: "text", text: JSON.stringify({ status: "ok", trade: params }, null, 2) }] };
  }
);

server.tool(
  "save_snapshot",
  "抓取所有持倉資料並存入 claude-project-instructions.md，方便手機 Claude App 使用",
  {},
  async () => {
    // Use Sheets-based data directly
    const allSheets = await readAllSheets();
    const fxRate = await fetchFxRate();

    // Fetch all prices
    const usTickers = [...new Set((allSheets.US_Stocks || []).map(r => r.ticker))];
    const twTickers = [...new Set((allSheets.TW_Stocks || []).map(r => r.ticker))];
    const optTickers = [...new Set((allSheets.Options || []).map(r => r.ticker))];
    const allTickers = [...new Set([...usTickers, ...twTickers, ...optTickers])];
    const prices = {};
    await Promise.all(allTickers.map(async t => { prices[t] = await fetchPrice(t); }));

    const filePath = resolve(__dirname, "..", "docs", "claude-project-instructions.md");
    let content = readFileSync(filePath, "utf-8");

    const marker = "<!-- SNAPSHOT START -->";
    const markerIdx = content.indexOf(marker);
    if (markerIdx !== -1) {
      content = content.substring(0, markerIdx);
    }

    const now = new Date().toLocaleString("zh-TW", { timeZone: "Asia/Taipei" });
    const snapshot = `${marker}
## Portfolio Snapshot (${now})

### FX Rate
USD/TWD = ${fxRate}

### US Stocks
\`\`\`json
${JSON.stringify(allSheets.US_Stocks, null, 2)}
\`\`\`

### TW Stocks
\`\`\`json
${JSON.stringify(allSheets.TW_Stocks, null, 2)}
\`\`\`

### Options
\`\`\`json
${JSON.stringify(allSheets.Options, null, 2)}
\`\`\`

### Bonds
\`\`\`json
${JSON.stringify(allSheets.Bonds, null, 2)}
\`\`\`

### Loans
\`\`\`json
${JSON.stringify(allSheets.Loans, null, 2)}
\`\`\`

### Live Prices
\`\`\`json
${JSON.stringify(prices, null, 2)}
\`\`\`
`;

    writeFileSync(filePath, content + snapshot, "utf-8");
    return { content: [{ type: "text", text: `Snapshot saved at ${now}\nFile: ${filePath}` }] };
  }
);

// --- Google Sheets CRUD Tools ---

server.tool(
  "sheets_read",
  "讀取 Google Sheets 指定工作表的資料（US_Stocks, TW_Stocks, Options, Bonds, Loans, Income, Settings, Trades）",
  { sheet: z.string().describe("工作表名稱") },
  async ({ sheet }) => {
    const data = await readSheet(sheet);
    if (data.length === 0) return { content: [{ type: "text", text: `${sheet}: empty` }] };
    return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
  }
);

server.tool(
  "sheets_read_all",
  "一次讀取 Google Sheets 所有工作表的資料",
  {},
  async () => {
    const result = await readAllSheets();
    return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
  }
);

server.tool(
  "sheets_update",
  "更新 Google Sheets 工作表的全部資料（覆蓋 header 以下的所有列）",
  {
    sheet: z.string().describe("工作表名稱"),
    rows: z.array(z.array(z.string())).describe("二維陣列，每個子陣列是一列資料（不含 header）"),
  },
  async ({ sheet, rows }) => {
    const sheets = getSheets();
    const headerRes = await sheets.spreadsheets.values.get({
      spreadsheetId: SPREADSHEET_ID,
      range: `${sheet}!A1:Z1`,
    });
    const headers = headerRes.data.values?.[0] || [];
    await sheets.spreadsheets.values.clear({
      spreadsheetId: SPREADSHEET_ID,
      range: `${sheet}!A2:Z1000`,
    });
    if (rows.length > 0) {
      await sheets.spreadsheets.values.update({
        spreadsheetId: SPREADSHEET_ID,
        range: `${sheet}!A2:${String.fromCharCode(64 + Math.max(headers.length, 1))}${rows.length + 1}`,
        valueInputOption: "RAW",
        requestBody: { values: rows },
      });
    }
    return { content: [{ type: "text", text: `${sheet}: updated ${rows.length} rows` }] };
  }
);

server.tool(
  "sheets_append",
  "在 Google Sheets 工作表末尾新增一列或多列資料",
  {
    sheet: z.string().describe("工作表名稱"),
    rows: z.array(z.array(z.string())).describe("要新增的列"),
  },
  async ({ sheet, rows }) => {
    const sheets = getSheets();
    await sheets.spreadsheets.values.append({
      spreadsheetId: SPREADSHEET_ID,
      range: `${sheet}!A1`,
      valueInputOption: "RAW",
      insertDataOption: "INSERT_ROWS",
      requestBody: { values: rows },
    });
    return { content: [{ type: "text", text: `${sheet}: appended ${rows.length} rows` }] };
  }
);

server.tool(
  "sheets_delete_row",
  "刪除 Google Sheets 工作表中符合條件的列",
  {
    sheet: z.string().describe("工作表名稱"),
    column: z.string().describe("用來比對的欄位名稱，例如 ticker"),
    value: z.string().describe("要刪除的值，例如 NVDA"),
  },
  async ({ sheet, column, value }) => {
    const sheets = getSheets();
    const res = await sheets.spreadsheets.values.get({
      spreadsheetId: SPREADSHEET_ID,
      range: `${sheet}!A1:Z1000`,
    });
    const rows = res.data.values || [];
    if (rows.length <= 1) return { content: [{ type: "text", text: `${sheet}: no data to delete` }] };
    const headers = rows[0];
    const colIdx = headers.indexOf(column);
    if (colIdx === -1) return { content: [{ type: "text", text: `Column "${column}" not found in ${sheet}` }] };
    const kept = rows.slice(1).filter(row => row[colIdx] !== value);
    const deleted = rows.length - 1 - kept.length;
    await sheets.spreadsheets.values.clear({
      spreadsheetId: SPREADSHEET_ID,
      range: `${sheet}!A2:Z1000`,
    });
    if (kept.length > 0) {
      await sheets.spreadsheets.values.update({
        spreadsheetId: SPREADSHEET_ID,
        range: `${sheet}!A2:${String.fromCharCode(64 + headers.length)}${kept.length + 1}`,
        valueInputOption: "RAW",
        requestBody: { values: kept },
      });
    }
    return { content: [{ type: "text", text: `${sheet}: deleted ${deleted} row(s) where ${column}=${value}` }] };
  }
);

// --- Start ---

const transport = new StdioServerTransport();
await server.connect(transport);
