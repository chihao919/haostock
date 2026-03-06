# Portfolio Quotes API

即時股票、期權報價 API，供 Claude 查詢使用。

## 本地測試
```bash
pip install -r requirements.txt
uvicorn main:app --reload
# 開啟 http://localhost:8000/docs 查看所有 endpoints
```

## Endpoints

| Endpoint | 說明 |
|----------|------|
| `GET /health` | 健康檢查 |
| `GET /fx` | USD/TWD 即時匯率 |
| `GET /quote/{ticker}` | 單一股票報價，例如 `/quote/CCJ` |
| `GET /stocks/us` | 所有美股持倉 + P&L |
| `GET /stocks/tw` | 所有台股持倉 + P&L |
| `GET /options` | 所有期權倉位 + P&L + 建議動作 |
| `GET /networth` | 完整淨資產總覽 |

## 部署到 Railway（推薦）

1. 到 https://railway.app 建立帳號
2. New Project → Deploy from GitHub Repo
3. 把這個資料夾 push 到你的 GitHub
4. Railway 自動偵測 Procfile 並部署
5. 取得 URL，格式類似 `https://portfolio-api-xxxx.railway.app`

## 部署到 Render

1. 到 https://render.com 建立帳號
2. New → Web Service → 連接 GitHub
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`

## 部署到 Fly.io

```bash
brew install flyctl
flyctl auth login
flyctl launch
flyctl deploy
```

## 告訴 Claude 你的 API URL

部署完成後，把 URL 告訴我，例如：
「我的 Portfolio API 網址是 https://xxx.railway.app」

之後我就能直接呼叫 `https://xxx.railway.app/options` 來查詢報價了！

## 安全性注意

這個 API 沒有認證（任何人都能查詢）。
如果要加保護，可以加一個 API key header，告訴我我來幫你加上去。
