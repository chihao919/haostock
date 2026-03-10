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

async function apiCall(path, options = {}) {
  const url = `${API_URL}${path}`;
  const resp = await fetch(url, options);
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`API error ${resp.status}: ${text}`);
  }
  return resp.json();
}

const server = new McpServer({
  name: "portfolio",
  version: "1.0.0",
});

// --- Tools ---

server.tool("get_us_stocks", "查詢所有美股持倉及損益（按帳戶分組）", {}, async () => {
  const data = await apiCall("/api/stocks/us");
  return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
});

server.tool("get_tw_stocks", "查詢所有台股持倉及損益（TWD/USD 雙幣）", {}, async () => {
  const data = await apiCall("/api/stocks/tw");
  return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
});

server.tool("get_options", "查詢所有選擇權倉位、損益、及建議動作", {}, async () => {
  const data = await apiCall("/api/options");
  return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
});

server.tool(
  "get_quote",
  "查詢單一股票即時報價",
  { ticker: z.string().describe("股票代碼，例如 NVDA, 2330.TW") },
  async ({ ticker }) => {
    const data = await apiCall(`/api/quote/${encodeURIComponent(ticker)}`);
    return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
  }
);

server.tool("get_networth", "查詢完整淨資產總覽（資產、負債、收入）", {}, async () => {
  const data = await apiCall("/api/networth");
  return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
});

server.tool("get_fx_rate", "查詢 USD/TWD 即時匯率", {}, async () => {
  const data = await apiCall("/api/fx");
  return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
});

server.tool(
  "get_trades",
  "查詢交易歷史紀錄，支援篩選",
  {
    ticker: z.string().optional().describe("篩選特定股票代碼"),
    result: z.enum(["Win", "Loss", "Breakeven"]).optional().describe("篩選交易結果"),
    asset_type: z.enum(["Stock", "Option"]).optional().describe("篩選資產類型"),
    limit: z.number().optional().describe("回傳筆數上限，預設 50"),
  },
  async ({ ticker, result, asset_type, limit }) => {
    const params = new URLSearchParams();
    if (ticker) params.set("ticker", ticker);
    if (result) params.set("result", result);
    if (asset_type) params.set("asset_type", asset_type);
    if (limit) params.set("limit", String(limit));
    const query = params.toString();
    const data = await apiCall(`/api/trades${query ? "?" + query : ""}`);
    return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
  }
);

server.tool(
  "add_trade",
  "新增一筆交易紀錄到 Notion",
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
    const data = await apiCall("/api/trades", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params),
    });
    return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
  }
);

server.tool(
  "save_snapshot",
  "抓取所有持倉資料並存入 claude-project-instructions.md，方便手機 Claude App 使用",
  {},
  async () => {
    const [us, tw, options, networth, fx, trades] = await Promise.all([
      apiCall("/api/stocks/us"),
      apiCall("/api/stocks/tw"),
      apiCall("/api/options"),
      apiCall("/api/networth"),
      apiCall("/api/fx"),
      apiCall("/api/trades?limit=20"),
    ]);

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

### US Stocks
\`\`\`json
${JSON.stringify(us, null, 2)}
\`\`\`

### TW Stocks
\`\`\`json
${JSON.stringify(tw, null, 2)}
\`\`\`

### Options
\`\`\`json
${JSON.stringify(options, null, 2)}
\`\`\`

### Net Worth
\`\`\`json
${JSON.stringify(networth, null, 2)}
\`\`\`

### FX Rate
\`\`\`json
${JSON.stringify(fx, null, 2)}
\`\`\`

### Recent Trades
\`\`\`json
${JSON.stringify(trades, null, 2)}
\`\`\`
`;

    writeFileSync(filePath, content + snapshot, "utf-8");
    return { content: [{ type: "text", text: `Snapshot saved at ${now}\nFile: ${filePath}` }] };
  }
);

// --- Google Sheets (Service Account) ---

const CREDENTIALS_PATH = process.env.GOOGLE_SA_KEY || resolve(process.env.HOME, ".config/claude-sheets/credentials.json");
const SPREADSHEET_ID = process.env.PORTFOLIO_SHEET_ID || "158xqbXsAIC5NCe_k5CR8JHkZT7MruXrIJMSecYGzZ7c";

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

server.tool(
  "sheets_read",
  "讀取 Google Sheets 指定工作表的資料（US_Stocks, TW_Stocks, Options, Bonds, Loans, Income, Settings）",
  { sheet: z.string().describe("工作表名稱，例如 US_Stocks, TW_Stocks, Options, Bonds, Loans, Income") },
  async ({ sheet }) => {
    const sheets = getSheets();
    const res = await sheets.spreadsheets.values.get({
      spreadsheetId: SPREADSHEET_ID,
      range: `${sheet}!A1:Z1000`,
    });
    const rows = res.data.values || [];
    if (rows.length <= 1) return { content: [{ type: "text", text: `${sheet}: empty (headers only)` }] };
    const headers = rows[0];
    const data = rows.slice(1).map(row => {
      const obj = {};
      headers.forEach((h, i) => { obj[h] = row[i] || ""; });
      return obj;
    });
    return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
  }
);

server.tool(
  "sheets_read_all",
  "一次讀取 Google Sheets 所有工作表的資料",
  {},
  async () => {
    const sheets = getSheets();
    const sheetNames = ["US_Stocks", "TW_Stocks", "Options", "Bonds", "Loans", "Income", "Settings"];
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
    // Get headers first
    const headerRes = await sheets.spreadsheets.values.get({
      spreadsheetId: SPREADSHEET_ID,
      range: `${sheet}!A1:Z1`,
    });
    const headers = headerRes.data.values?.[0] || [];
    // Clear existing data (keep headers)
    await sheets.spreadsheets.values.clear({
      spreadsheetId: SPREADSHEET_ID,
      range: `${sheet}!A2:Z1000`,
    });
    // Write new data
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
    // Clear and rewrite
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
