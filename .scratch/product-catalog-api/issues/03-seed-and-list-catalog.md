# 03 — 匯入範例資料並瀏覽商品目錄

**What to build:** 評閱者可以獨立執行 seed 指令匯入題目四筆商品，接著透過列表 API 瀏覽完整商品目錄；重複匯入保留已存在商品的所有內容，失敗匯入完整回滾。

**Blocked by:** 02 — 新增商品並依 code 讀取。

**Status:** ready-for-agent

**Completed:** 2026-09-12；實作 commit `a0468e1`。

**Parent:** [GainMiles 商品目錄 API 與可重現的容器環境](../spec.md)

- [x] GET `/api/products` 回傳 200 與 data 陣列，每個元素包含母規格完整七個商品欄位；空目錄回傳空 data 陣列。
- [x] 商品以 code 的 Unicode code point 升冪排列，尺寸、顏色遵守同一字串排序原則，價格固定兩位小數字串；不依賴 DB 預設 collation 或插入順序。
- [x] 列表不提供分頁或篩選；集合採批次載入，避免每個商品額外查詢明細及尺寸／顏色交叉乘積，不重複回傳選項或錯誤累計 inventory。
- [x] 獨立 seed 邏輯註冊為 seed-demo Flask CLI，透過應用程式設定連 DB，僅在明確呼叫時執行，不隨 API 啟動或重啟自動執行。
- [x] 依母規格原始值匯入 Star A-001、Moon A-002、Eagle B-001、Bird B-002；乾淨匯入後有兩個分類、四個商品、九筆尺寸、六筆顏色，單價與庫存皆正確。
- [x] 分類依名稱取得，不依賴固定 generated identifier；同次 seed 中所有新增商品與明細使用單一交易。
- [x] code 已存在就跳過整個商品，完整保留其名稱、分類、單價、庫存、尺寸與顏色，不嘗試修復或合併明細；重複執行不重複資料。
- [x] seed 印出新增與跳過商品筆數。中途失敗時所有該次寫入 rollback 並回傳非零 exit code；已有資料不受失敗匯入影響。
- [x] 驗證既有已編輯商品被保留、已刪除的範例商品在下次 seed 重新建立；測試以 fixture 準備既有及缺少資料，不依賴 tickets 04 或 05 的 API。
- [x] 透過公開 CLI、列表及單筆 GET 驗證清空目錄、完整 seed、重複 seed、排序與輸出格式，必要時用窄範圍 DB 觀察驗證明細筆數；seed 回滾測試包含真正的中途寫入失敗。
- [x] 補上 seed 與列表操作說明，清楚描述跳過策略及刪除後再 seed 會重建範例商品的行為。

## Completion

全部 11 項驗收已完成。完整容器測試 153 passed，mypy 與 Ruff 通過；獨立 Compose 環境實測空目錄、CLI 匯入四筆商品、HTTP 列表與重複 seed。Standards／Spec 雙軸 code-review 均無 actionable findings。Status 保留原 triage 分類，Completed 與已勾選驗收項目表示本 ticket 已完成。

操作範例見 [API 文件](../../../docs/api-contract.md)，測試指令與整體結果見 [技術架構](../../../docs/architecture.md)。
