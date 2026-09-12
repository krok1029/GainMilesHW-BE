# 單一總 PR 草稿

建議標題：`Complete Flask product catalog API and reproducible Docker setup`

Base：`main`；Head：`feat/flask-crud`。下列內容可作為整份作業的 PR description；本文件不會 push、建立或合併 PR。

## 變更

完成題目商品表的 JSON CRUD API 與可重現執行環境。商品以 code 識別，分類、尺寸與顏色正規化為四張表；價格使用 Decimal 與固定兩位小數字串，庫存維持每個商品一個總數。

- 提供新增、單筆讀取、完整列表、PATCH 部分更新與 DELETE。統一欄位驗證及 JSON 錯誤，集合固定排序；code 建立後不可修改。
- 商品、分類與明細在同一交易提交，涵蓋競爭分類建立、重複 code、選項替換與刪除回滾。
- Compose 依序等待 PostgreSQL、執行 versioned migration，再啟動 Gunicorn；獨立 seed-demo 匯入四筆原始資料，重跑跳過整個既有商品。
- 提供更新腳本與公開 CLI／HTTP 驗收流程，驗證重啟／重建／停止後資料保留，以及 migration 失敗保持 API 停止。

## 驗證

2026-09-12 最終驗證：

- 完整容器 pytest：**276 passed**，真實 PostgreSQL，每個情境使用獨立暫存 DB。
- 容器 mypy：22 個 source files 無錯誤；Ruff 全部通過。
- `verify-startup.sh`：migration／health 順序、DB 中斷恢復及首次 migration 失敗阻止啟動均通過。
- `verify-handoff.sh`：精確 seed、實際 HTTP CRUD、持久化、更新失敗保持 API 停止、明確恢復與 volume 重設均通過。
- Ticket 06 Standards／Spec 雙軸 review 均無待修問題；各功能的 review 與已修正事項見紀錄。

詳細結果見 [驗證紀錄](verification.md)。主要可重跑指令：

```bash
sh tests/verify-startup.sh
sh tests/verify-handoff.sh
docker compose -p gainmiles-tests -f compose.test.yaml run --build --rm tests
docker compose -p gainmiles-tests -f compose.test.yaml run --rm tests mypy
docker compose -p gainmiles-tests -f compose.test.yaml run --rm tests ruff check app tests migrations
docker compose -p gainmiles-tests -f compose.test.yaml down --volumes
```

## 審核入口

- [README](../README.md)：設定、啟動、API 範例、seed、更新、測試與資料重設。
- [DB schema](db-schema.md)、[架構](architecture.md)、[API contract](api-contract.md)。
- [母規格](../.scratch/product-catalog-api/spec.md) 與各功能 ticket 的完成紀錄。
- [AI 對話分享來源](ai-conversation.md)：使用提交者指定的對話連結，保留分享快照的範圍說明。

作業範圍未包含身分驗證、訂單／扣庫存、分頁或 production 部署。各功能與驗證紀錄以獨立 commits 累積於同一功能分支，main 保持原始共同基底。
