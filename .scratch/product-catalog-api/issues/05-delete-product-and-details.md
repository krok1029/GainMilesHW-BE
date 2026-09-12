# 05 — 刪除商品並清除明細

**What to build:** API 使用者可以依 code 刪除商品，相關尺寸與顏色同步移除，共用分類及其他商品保留；刪除結果與不存在的商品都透過明確 HTTP 回應呈現。

**Blocked by:** 02 — 新增商品並依 code 讀取。

**Status:** ready-for-agent

**Completed:** 2026-09-12；實作 commit `ca3e930`。

**Parent:** [GainMiles 商品目錄 API 與可重現的容器環境](../spec.md)

- [x] DELETE `/api/products/{code}` 成功時回傳 204，response body 為空；後續單筆 GET 回傳 404 PRODUCT_NOT_FOUND。
- [x] 刪除未知 code 或再次刪除同一商品都回傳 404 PRODUCT_NOT_FOUND，沿用母規格 JSON 錯誤結構。
- [x] 商品及其尺寸、顏色明細在同一交易刪除，配合 ORM relationship 與 DB 外鍵 cascade，不留下 orphan rows；成功回應在 commit 成功後回傳。
- [x] 刪除商品不刪除分類，即使該分類已無商品也保留；同分類其他商品及其明細不受影響。
- [x] 未預期刪除失敗回傳共用 500 錯誤並 rollback，原商品與明細仍完整可讀。
- [x] 使用 HTTP 及真實 PostgreSQL 驗證成功、重複刪除、未知 code、共用分類保留與失敗回滾；僅在確認 orphan rows 等 API 不可直接觀察的完整性承諾時使用窄範圍 DB 查詢。
- [x] 測試透過 ticket 02 的新增／讀取或獨立 fixture 準備資料，不依賴列表、seed 或 PATCH；補上刪除與不存在回應的操作說明。

## Completion

全部 7 項驗收已完成。完整容器測試 276 passed，mypy 與 Ruff 通過；涵蓋空 body 的 204、重複／未知 code 的 404、明細 cascade、分類與其他商品保留，以及刪除途中和 commit 失敗的完整回滾。Standards／Spec 雙軸 code-review 均無 actionable findings。Status 保留原 triage 分類，Completed 與已勾選驗收項目表示本 ticket 已完成。

操作範例見 [README](../../../README.md)，詳細證據見 [驗證紀錄](../../../docs/verification.md)。
