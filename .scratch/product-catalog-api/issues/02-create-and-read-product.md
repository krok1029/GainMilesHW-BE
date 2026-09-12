# 02 — 新增商品並依 code 讀取

**What to build:** API 使用者可以在沒有 seed 資料的環境，建立包含分類、尺寸、顏色、單價與商品庫存的商品，隨即依 code 讀回；錯誤輸入、重複代碼或寫入失敗都能得到一致回應且不留下部分資料。

**Blocked by:** 01 — 啟動容器環境並確認資料庫就緒。

**Status:** ready-for-agent

**Completed:** 2026-09-12；實作 commit `22fcbb3`，review 修正 `66c6c16`。

**Parent:** [GainMiles 商品目錄 API 與可重現的容器環境](../spec.md)

- [x] POST `/api/products` 接受母規格七個必填欄位，成功回傳 201、Location header 及完整商品物件；GET `/api/products/{code}` 回傳 200 與同一商品的持久化結果，不使用 data wrapper。
- [x] code 採母規格的非空 ASCII 英數字、hyphen、underscore 格式，保留大小寫且拒絕前後空白，不從前綴推導分類。
- [x] name、category 與集合元素依規格修整空白，維持大小寫；sizes、colors 必須為非空字串陣列且修整後無重複值。拒絕缺少欄位、未知欄位、null 與非 object body。
- [x] unit_price 僅接受母規格範圍內、最多兩位小數的十進位字串，以 Decimal 處理並輸出兩位小數；拒絕 number、符號、空白、指數、特殊數值及過多小數位。inventory 僅接受範圍內 JSON 整數，拒絕 boolean、字串與小數。
- [x] 回應含分類名稱，不暴露或要求內部分類識別值；sizes、colors 依 Unicode code point 升冪排序，不重複商品庫存、不推導規格組合庫存。
- [x] 建立商品時能取得既有分類或建立新分類，不依賴預先匯入分類；所有商品與明細、分類新增在同一交易提交，helper 不自行 commit。
- [x] 重複商品 code 回傳 409 PRODUCT_CODE_EXISTS，涵蓋寫入前已存在與競爭寫入觸發的唯一限制；兩個重疊請求建立同名分類時，共用單一分類且有效商品皆可成功建立。
- [x] 建立共用 JSON 錯誤處理，涵蓋 400 INVALID_JSON、404 NOT_FOUND／PRODUCT_NOT_FOUND、405 METHOD_NOT_ALLOWED、409 PRODUCT_CODE_EXISTS、415 UNSUPPORTED_MEDIA_TYPE、422 VALIDATION_ERROR、500 INTERNAL_ERROR；包含穩定 code、英文 message 與 fields mapping。
- [x] 媒體類型／JSON 解析、body 驗證、存在性／DB 衝突依母規格順序處理；未知錯誤記錄 log，response 不含 SQL 或 traceback。
- [x] 使用真實 PostgreSQL 的 HTTP 整合測試覆蓋新增讀回、既有／新分類、數值上下界、字串修整、大小寫、集合驗證、排序、missing product 與錯誤格式；測試不依賴 demo seed。
- [x] 使用獨立 session 及確定的同步方式驗證重疊分類建立及重複 code 競爭，不以固定 sleep 假設競爭已發生。
- [x] 透過 API 驅動多表寫入並在寫入途中製造可控制的失敗，驗證商品、明細及新分類全部 rollback；單純驗證失敗不算交易回滾證據。回應成功必須發生在 commit 成功後。
- [x] 補上新增、讀取與失敗回應範例及對應測試操作說明；每項測試斷言外部行為或持久化結果，避免綁定私有實作細節。

## Completion

全部 13 項驗收已完成。最終完整容器測試 141 passed，mypy 與 Ruff 通過；涵蓋真實 PostgreSQL 的 HTTP 新增讀回、欄位邊界、確定重疊的分類／code 競爭，以及明細寫入與 commit 失敗的整筆 rollback。Standards／Spec review 各提出一項 P2，修正並經原 reviewer 複查結案；無待修 findings。Status 保留原 triage 分類，Completed 與已勾選驗收項目表示本 ticket 已完成。

操作範例見 [README](../../../README.md)，詳細證據見 [驗證紀錄](../../../docs/verification.md)。
