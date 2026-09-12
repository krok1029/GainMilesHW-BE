# 04 — 部分更新商品與替換尺寸／顏色

**What to build:** API 使用者可以只更新商品指定欄位，也可以整組替換尺寸或顏色；未指定資料保留不變，修改分類只影響該商品，任何寫入失敗都不留下部分更新。

**Blocked by:** 02 — 新增商品並依 code 讀取。

**Status:** ready-for-agent

**Completed:** 2026-09-12；實作 commit `ecd8877`。

**Parent:** [GainMiles 商品目錄 API 與可重現的容器環境](../spec.md)

- [x] PATCH `/api/products/{code}` 只更新提供的可寫欄位，成功回傳 200 與完整更新後商品；單筆 GET 可讀回一致結果。
- [x] 未提供的欄位維持原值；提供 sizes 或 colors 時整組取代，移除舊有但未保留的明細，不採集合聯集或追加語意。
- [x] 即使 code 與原值相同，只要 body 包含 code 就回傳 422；拒絕空 object、unknown fields、null、空集合與非法欄位值，沿用新增的數字、字串與集合驗證及共用錯誤格式。
- [x] 通過 request 驗證後找不到商品回傳 404 PRODUCT_NOT_FOUND；驗證與存在性檢查的順序符合母規格。
- [x] 修改 category 時取得或建立指定分類並更新該商品引用；其他商品及其共用分類名稱維持不變，涵蓋新分類的競爭處理。
- [x] 商品屬性、集合替換及新分類建立以同一筆交易完成；成功回應在 commit 後回傳，任一步失敗完整 rollback。
- [x] 回應沿用完整七欄位物件、固定兩位小數價格、Unicode code point 集合排序，inventory 仍是商品總數。
- [x] 使用 HTTP 與真實 PostgreSQL 測試只更新庫存、同時更新多欄、尺寸／顏色取代、保留未傳值、保留交集選項、禁止 code 修改及所有適用的驗證錯誤。
- [x] 透過 API 在多表更新途中製造可控制的失敗，驗證原商品屬性及所有明細保留，新建立分類也未提交；不以僅在寫入前拒絕輸入代替 rollback 測試。
- [x] 共用分類測試準備兩個商品，證明更新一個商品不改動另一個；使用 ticket 02 的新增及讀取能力，不依賴列表、seed 或刪除 API。
- [x] 補上 PATCH 範例、集合取代語意、不可變商品代碼及錯誤案例的操作說明；同欄位重疊修改沿用母規格的最後成功寫入值，不增加版本鎖。

## Completion

全部 11 項驗收已完成。完整容器測試 264 passed，mypy 與 Ruff 通過；包含部分更新、選項替換與交集保留、共用分類、驗證優先順序、多表更新與 commit 失敗回滾，以及確定重疊請求的最後成功寫入值。Standards／Spec 雙軸 code-review 均無 actionable findings。Status 保留原 triage 分類，Completed 與已勾選驗收項目表示本 ticket 已完成。

操作範例見 [README](../../../README.md)，詳細證據見 [驗證紀錄](../../../docs/verification.md)。
