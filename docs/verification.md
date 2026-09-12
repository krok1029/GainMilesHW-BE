# 實作驗證紀錄

## Ticket 01 啟動容器環境並確認資料庫就緒

完成日期：2026-09-12。實作 commit：`3c1d18b`，分支：`feat/flask-crud`。

### 環境

| 項目 | 實際版本 |
| --- | --- |
| Docker Engine | 28.4.0 |
| Docker Compose | 2.39.2-desktop.1 |
| Runtime／test image Python | 3.13.15 |
| PostgreSQL | 18.6，Debian bookworm image |
| 主機開發 Python | 3.13.5 |

Python／PostgreSQL images 以 digest 固定，應用與測試依賴由 uv.lock 鎖定。容器內測試環境與開發 DB 分離。

### TDD 與測試結果

| 檢查 | 結果 |
| --- | --- |
| 第一個 health 測試 | 先因沒有 application module 而失敗；實作後 DB 無法連線回傳 503 |
| 空目錄 health 測試 | 先因沒有 migration CLI 而失敗；整合 migration 後通過 |
| 四張表 migration 測試 | 先只找到 Alembic 版本表而失敗；實作初始 revision 後通過 |
| Compose 首次啟動驗收 | 先因缺少 Compose 設定而失敗；加入容器設定後通過 |
| Migration 單一測試檔 | 21 passed，含 constraints、cascade、重跑 upgrade、models 一致性及空測試 DB downgrade |
| 完整容器測試套件 | 23 passed，真實 PostgreSQL，每個 DB 測試使用獨立暫存資料庫 |
| 容器內 mypy | 7 個 source files，無錯誤 |
| 容器內 Ruff | app、tests、migrations 全部通過 |
| 格式與文件 | Ruff format 檢查、Git whitespace 檢查與本機文件連結檢查通過 |

PostgreSQL 對 `ON DELETE RESTRICT` 回傳的 SQLSTATE 為 23001；測試曾錯誤預期一般外鍵違反的 23503，已修正測試預期，沒有放寬 DB 約束。

### Compose 操作驗收

以 `sh tests/verify-startup.sh` 建立獨立 Compose 專案及隨機 API port，實際驗證：

- PostgreSQL healthcheck 成功後執行 migration；migration exit code 為零後 API 才啟動。
- `up --build --wait` 能處理一次性 migration 工作，成功返回後 HTTP health 為 200，不需 seed。
- migration 與 API container 的 image ID 相同；migration 可再次執行成功。
- 停止 DB 後，仍執行中的 API health 回傳 503；啟動 DB 後，不重啟 API 即恢復 200。
- 另一個全新專案指定不存在的 migration revision，啟動指令回傳失敗；migration 非零退出，API 沒有啟動過，log 保留找不到 revision 的錯誤。
- 操作腳本僅清除本次建立的容器及 volumes；常規測試使用的專用 PostgreSQL 專案亦於驗證後清除。

### Standards

獨立 reviewer 以 `1878e26...3c1d18b` 檢查文件標準與 code-smell baseline，沒有 actionable findings。領域詞彙、Flask factory、正規化 schema、啟動順序、測試隔離及操作文件符合專案規則。Migration 與 models 的對應定義屬於獨立版本化的 schema 歷史，不列為需要抽象化的重複程式。

### Spec

另一位獨立 reviewer 以同一範圍對照 ticket 01、母規格及 DB schema，沒有 actionable findings。必要的容器、migration、health、資料限制、隔離測試與指令已實作，沒有實質 scope creep。商品 CRUD、seed 及既有環境更新失敗的完整交付驗收仍屬後續 tickets。

兩軸 reviewer 皆為唯讀檢查，未自行重跑測試；上方 runtime 結果由主代理實際執行取得。Standards：0 項；Spec：0 項，各軸均無最嚴重待修問題。

### 範圍界線

本 ticket 完成 health 與容器／資料庫基礎行為。CRUD、seed 與最終完整 AI 對話交付仍未完成，不以這次通過的檢查代表整份作業已完成。`main` 保持空初始化基底，未 push 或建立 PR。


## Ticket 02 新增商品並依 code 讀取

完成日期：2026-09-12。實作 commit：`22fcbb3`；review 修正：`66c6c16`。分支：`feat/flask-crud`。

### 功能與測試入口

實作 POST `/api/products`、GET `/api/products/{code}`、七欄位驗證、固定商品回應及共用 JSON 錯誤處理。資料表沿用 ticket 01，沒有新 migration 或依賴。測試透過 Flask test client 與真實 PostgreSQL，不依賴 seed；僅在驗證資料完整性、同步交易及製造故障時使用窄範圍 DB 操作。

### TDD 與最終結果

| 檢查 | 結果 |
| --- | --- |
| 新增後讀回 | 先收到 404；實作 route、service 與序列化後通過 |
| boolean 庫存 | 先誤回 201；新增明確整數驗證後回傳 422 |
| 重複 code／媒體類型／missing product | 先分別得到 500、422、NOT_FOUND；修正後符合 409、415、PRODUCT_NOT_FOUND |
| JSON 數值常數 | 未加引號的 NaN／Infinity 原被解析而回 422；嚴格 JSON provider 修正為 400 |
| GET 不合法 URL code | `%00` 先觸發 PostgreSQL DataError 而回 500；共用格式檢查後回 404 |
| 商品 API 單一測試檔 | 最終 111 passed，含必填／未知欄位、null、非 object、價格與庫存邊界、Unicode、大小寫、修整及排序 |
| 交易單一測試檔 | 7 passed，含共用分類、重疊請求、重複 code 回滾及未知 DB 錯誤 |
| 最終完整容器測試 | **141 passed**，含既有 23 個 health／migration 測試；review 改碼後重新 build 驗證 |
| 最終容器 mypy | 15 個 source files，無錯誤 |
| 最終容器 Ruff | app、tests、migrations 全部通過 |
| 主機格式檢查 | 17 個 Python 檔案已符合 Ruff format |

本次使用獨立 Compose project `gainmiles-ticket02-tests`，Docker 與鎖定的 runtime／DB 版本沿用 ticket 01。完整測試指令：

```bash
docker compose -p gainmiles-ticket02-tests -f compose.test.yaml run --build --rm tests
docker compose -p gainmiles-ticket02-tests -f compose.test.yaml run --rm tests mypy
docker compose -p gainmiles-ticket02-tests -f compose.test.yaml run --rm tests ruff check app tests migrations
```

### 競爭與 rollback 證據

- 兩個 worker 各自建立 HTTP 請求及 DB session。測試用 trigger 在 INSERT 暫停，觀察 `pg_locks` 確認兩個不同 PID 同時等待，再釋放 advisory lock。以有期限的狀態輪詢同步，不靠固定 sleep 假設競爭已發生。
- 不同 code、相同新分類：兩個請求皆 201，可讀回完整商品，DB 僅有一筆分類。
- 相同 code、不同新分類：結果一個 201、一個 409，只有成功商品與其分類、明細留下。
- AFTER INSERT trigger 在明細寫入中途丟出錯誤；另一案例使用 deferred constraint trigger，在 commit 階段丟錯。API 都回傳一般化 500，log 保留錯誤，GET 404，四張表均無殘留。移除故障後重試可成功。
- 測試 DB 暫時新增另一個唯一限制，確認其錯誤不被誤認為商品 code 衝突：回傳 500、保留原商品、回滾新分類。只有 `pk_products` 的 UniqueViolation 對應 409。

### Standards

固定初審範圍 `bf3bc1b…22fcbb3`。Reviewer 提出一項 P2：Schema 序列化會隱含觸發關聯查詢，違反文件中 Schema 不查 DB 的分工。`66c6c16` 改由 Service 取得 Category 物件，並在 GET 預先載入分類、尺寸及顏色。原 reviewer 複查 `22fcbb3…66c6c16` 確認結案，無新 actionable findings 或獨立 code-smell 建議。

### Spec

固定初審範圍同上。Reviewer 提出一項 P2：GET 的 `%00` code 會觸發 DB 錯誤而回 500。新增先失敗的 HTTP 回歸測試後，讓 GET 與 POST 共用 code 格式檢查，不合法的單筆 code 回傳 404 PRODUCT_NOT_FOUND。原 reviewer 複查確認結案，其餘新增、讀取、交易、錯誤與範圍符合 ticket。

兩軸 reviewer 皆未修改檔案或執行完整測試；Spec reviewer 額外以既有隔離 DB 唯讀重現 GET 問題。完整測試由主代理執行。Standards：1 項已修、0 項待修；Spec：1 項已修、0 項待修，各軸均無最嚴重待修問題。

### 交付範圍

已更新 README 的可呼叫範例、架構及 API 文件，ticket 02 的 13 項驗收完成。列表、PATCH、DELETE、seed 與整份作業最終交付仍由後續 tickets 完成。`main` 維持 `47fdb4a`，工作提交在功能分支，未 push 或建立 PR。驗證後清除本次專用測試容器。
