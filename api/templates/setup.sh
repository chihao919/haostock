#!/bin/bash
# Investment Dashboard — MCP Server Setup
# Usage: curl -sL https://stock.cwithb.com/setup.sh | bash
set -e

echo "================================================"
echo "  投資寶庫 MCP Server 安裝程式"
echo "  讓 Claude Code 直接讀寫你的投資資料"
echo "================================================"
echo ""

# Check Node.js
if ! command -v node &> /dev/null; then
  echo "❌ 需要 Node.js (v18+)。請先安裝: https://nodejs.org"
  exit 1
fi

# Check Claude Code
if ! command -v claude &> /dev/null; then
  echo "❌ 需要 Claude Code CLI。安裝方式："
  echo "   npm install -g @anthropic-ai/claude-code"
  exit 1
fi

# Choose install directory
INSTALL_DIR="${HOME}/.local/share/portfolio-mcp"
echo "📁 安裝目錄: ${INSTALL_DIR}"
mkdir -p "${INSTALL_DIR}"

# Download MCP server files
echo "📥 下載 MCP Server..."
REPO_URL="https://raw.githubusercontent.com/chihao919/stock-api/main/mcp-server"
curl -sL "${REPO_URL}/index.js" -o "${INSTALL_DIR}/index.js"
curl -sL "${REPO_URL}/package.json" -o "${INSTALL_DIR}/package.json"

# Install dependencies
echo "📦 安裝依賴套件..."
cd "${INSTALL_DIR}" && npm install --silent 2>/dev/null

# Setup credentials directory
CREDS_DIR="${HOME}/.config/claude-sheets"
mkdir -p "${CREDS_DIR}"

# Check for existing credentials
if [ ! -f "${CREDS_DIR}/credentials.json" ]; then
  echo ""
  echo "⚠️  需要 Google Service Account 金鑰"
  echo "   1. 到 Google Cloud Console 建立 Service Account"
  echo "   2. 下載 JSON 金鑰檔"
  echo "   3. 複製到: ${CREDS_DIR}/credentials.json"
  echo "   4. 在 Google Sheets 中將 Service Account Email 加為編輯者"
  echo ""
  read -p "📄 如果你已有金鑰檔，請輸入路徑（或 Enter 跳過）: " KEY_PATH
  if [ -n "${KEY_PATH}" ] && [ -f "${KEY_PATH}" ]; then
    cp "${KEY_PATH}" "${CREDS_DIR}/credentials.json"
    echo "✅ 金鑰已複製"
  fi
fi

# Get Spreadsheet ID
echo ""
read -p "📊 請輸入你的 Google Sheets ID（或 Enter 使用預設）: " SHEET_ID
if [ -z "${SHEET_ID}" ]; then
  SHEET_ID="1wtFrdco3yNf2cXGUvyDKUPR0B5ENP9OSl0ci1jwk-mE"
fi

# Register MCP server with Claude Code
echo ""
echo "🔧 註冊 MCP Server 到 Claude Code..."
claude mcp add portfolio \
  -e PORTFOLIO_SHEET_ID="${SHEET_ID}" \
  -e GOOGLE_SA_KEY="${CREDS_DIR}/credentials.json" \
  -- node "${INSTALL_DIR}/index.js" 2>/dev/null || true

echo ""
echo "================================================"
echo "  ✅ 安裝完成！"
echo "================================================"
echo ""
echo "使用方式："
echo "  claude                          # 啟動 Claude Code"
echo "  > 查詢我的美股持倉              # 讀取 Google Sheets"
echo "  > 建議 Covered Call 策略        # 投資策略分析"
echo "  > 分析 NVDA 基本面             # 個股分析"
echo "  > 新增交易紀錄                  # 寫入交易記錄"
echo ""
echo "可用工具："
echo "  get_us_stocks    — 美股持倉及損益"
echo "  get_tw_stocks    — 台股持倉及損益"
echo "  get_options      — 選擇權倉位及建議動作"
echo "  get_networth     — 淨資產總覽"
echo "  get_quote        — 即時報價"
echo "  get_trades       — 交易歷史紀錄"
echo "  add_trade        — 新增交易紀錄"
echo "  sheets_read_all  — 讀取所有工作表"
echo ""
