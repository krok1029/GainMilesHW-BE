# GainMiles 商品目錄 API

使用 Flask、SQLAlchemy 與 PostgreSQL 實作商品 CRUD，以 `code` 識別商品，管理分類、尺寸、顏色、單價與總庫存。Docker Compose 負責啟動資料庫、套用 migration，再啟動 Gunicorn API。

## 啟動

需要 Docker 與 Compose v2（已驗證 Docker 28.4.0、Compose 2.39.2）。不需要在主機安裝 Python 或 PostgreSQL。

在專案根目錄執行：

```bash
cp .env.example .env
docker compose up --build --wait --wait-timeout 90
curl --fail http://localhost:8000/health
```

健康檢查應回傳 `{"status":"ok"}`。`migrate` 容器完成後以 exit code 0 結束是正常狀態。API 預設為 `http://localhost:8000`；若 port 被占用，可在啟動前修改 `.env` 的 `API_PORT`，並同步調整下方網址。

## 匯入範例資料

資料表建好後，獨立匯入題目的四筆商品：

```bash
docker compose exec api flask --app app seed-demo
curl --fail http://localhost:8000/api/products
```

可重複執行 seed；已存在的 `code` 會跳過，保留現有資料。API 重啟不會自動 seed。

## 停止

```bash
docker compose down
```

資料保留在 PostgreSQL volume，下次啟動可繼續使用。

## 文件

- [技術架構](docs/architecture.md)：分層、交易、容器流程、環境更新與測試指令。
- [DB schema](docs/db-schema.md)：Mermaid 關聯圖與資料限制。
- [API 文件](docs/api-contract.md)：路由、欄位驗證、錯誤格式與操作範例。

[原始作業題目](<docs/GainMiles Python Online Test (2026).docx>) · [AI 對話連結](https://chatgpt.com/s/cx_6aa63d38bc788191b8d2697ad819a7c0)（依提交者指定，分享快照截至 ticket 06 開始；後續訊息不會自動加入）。
