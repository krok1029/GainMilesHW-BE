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


## Ticket 03 匯入範例資料並瀏覽商品目錄

完成日期：2026-09-12。實作 commit：`a0468e1`；分支：`feat/flask-crud`。

### 功能與測試

新增 GET `/api/products` 與獨立 Flask CLI `seed-demo`。HTTP 建立與 seed 共用不自行 commit 的商品寫入 helper；seed 為整次匯入管理單一交易。列表明確載入分類及兩種選項集合，使用 Python 字串排序，避免依賴 DB collation。無新增 migration 或依賴。

| 檢查 | 結果 |
| --- | --- |
| 空目錄列表 TDD | 先回傳 405；加入 collection GET 後回傳 200 與空 data 陣列 |
| seed CLI TDD | 先找不到 seed-demo；實作後新增四筆商品並回報 4/0 |
| 重複 seed TDD | 先因重複 code 非零退出；加入整筆跳過後回報 0/4 並保留資料 |
| 列表單一測試檔 | 3 passed，涵蓋完整表示、大小寫／符號排序、30 筆商品的最多四次 SELECT 預算 |
| seed 單一測試檔 | 9 passed，包含原始值與 2/4/9/6 資料列筆數、重跑、保留編輯內容、缺明細不修復、刪除後重建、不同分類 ID、啟動不自動 seed 及失敗回滾 |
| 既有 API 交易單一測試檔 | 7 passed，共用 helper 後仍保有分類／code 競爭與回滾保證 |
| 完整容器測試套件 | **153 passed**，包含 ticket 01、02 的全部案例 |
| 容器內 mypy | 18 個 source files，無錯誤 |
| 容器內 Ruff | app、tests、migrations 全部通過 |
| 格式與文件 | 20 個 Python 檔案符合 Ruff format；Markdown 連結與 Git whitespace 檢查通過 |

完整驗證指令：

```bash
docker compose -p gainmiles-ticket03-tests -f compose.test.yaml run --build --rm tests
docker compose -p gainmiles-ticket03-tests -f compose.test.yaml run --rm tests mypy
docker compose -p gainmiles-ticket03-tests -f compose.test.yaml run --rm tests ruff check app tests migrations
```

### 失敗匯入的證據

測試在當次暫存 DB 的顏色表建立 AFTER INSERT trigger：第二筆範例商品 A-002 寫入時，確認 A-001、其兩種明細、A-002 與新分類已存在，再推進不隨 rollback 還原的測試 sequence 並丟出錯誤。

CLI 非零退出且未印出成功筆數；sequence 證明已到達實際多筆寫入途中。失敗後列表與四張表筆數均等於匯入前，A-001／A-002 查詢皆為 404。兩種情境分別從空 DB 與保有自訂 B-001 的 DB 執行，確認本次新增全部回滾且既有商品不受影響。移除故障後重試成功。

### 實際 Compose 操作

使用獨立 `gainmiles-ticket03-smoke` 專案、新 DB volume 及隨機 API port 執行 `up --build --wait`，實際等待 migration 成功、Gunicorn healthy 後驗證：

1. HTTP 列表回傳空 data，啟動沒有自動 seed。
2. `docker compose exec -T api flask --app app seed-demo` 回報 `Created: 4; skipped: 0.`。
3. Gunicorn HTTP 列表依序回傳 A-001、A-002、B-001、B-002，價格與庫存符合原始資料，尺寸合計 9 筆、顏色合計 6 筆。
4. 同一 CLI 再執行一次回報 `Created: 0; skipped: 4.`，HTTP 列表完全不變。

環境及鎖定版本沿用前兩張 tickets。驗證後僅清除本次測試與 smoke 專案的容器、網路及測試 volume。

### Standards

Reviewer 唯讀檢查 `bb5c5cf…a0468e1`，未發現違反專案文件的變更或有價值的 baseline smell。共用寫入 helper 不自行 commit、外層交易管理、列表載入及排序方式符合既有架構，無需新增抽象。

### Spec

另一位 reviewer 唯讀檢查同一範圍，未發現規格缺漏、範圍擴張或實作錯誤。原始資料、跳過策略、原子匯入、列表格式、排序與測試證據符合 ticket 03。

兩軸 reviewer 未修改檔案或執行測試；上方結果由主代理實際執行。Standards：0 項；Spec：0 項，各軸均無最嚴重待修問題。

### 交付範圍

ticket 03 全部 11 項驗收完成。README、架構與 API 文件已更新；PATCH、DELETE 與作業最終交付仍屬後續 tickets。工作提交在 `feat/flask-crud`，`main` 保持 `47fdb4a`，未 push 或建立 PR。


## Ticket 04 部分更新商品與替換尺寸／顏色

完成日期：2026-09-12。實作 commit：`ecd8877`；分支：`feat/flask-crud`。

### 功能與測試

新增 PATCH `/api/products/{code}`，僅更新提供的六種可寫欄位，禁止 code 出現在 body。選項整組取代並保留交集中的既有明細；未傳欄位不變。共用新增商品的價格、庫存與文字／集合驗證，以及分類解析。商品、明細與分類新增共用一筆交易；無新增 migration 或依賴。

| 檢查 | 結果 |
| --- | --- |
| PATCH 庫存 TDD | 先回傳 405；實作後 200，未提供欄位保持不變，GET 可讀回 |
| PATCH 行為單一測試檔 | 106 passed，包含多欄修改、選項替換與交集、原集合重送、數值邊界、字串修整／大小寫、所有適用欄位驗證、無效 URL 與錯誤優先順序 |
| PATCH 交易單一測試檔 | 5 passed，包含替換途中／commit 故障、新分類競爭、重疊更新保留省略欄位及最後選項替換 |
| 既有新增交易單一測試檔 | 7 passed，共用分類 resolver 與 concurrency fixture 後仍保持既有保證 |
| 完整容器測試套件 | **264 passed**，包含 tickets 01 至 03 全部案例 |
| 容器內 mypy | 20 個 source files，無錯誤 |
| 容器內 Ruff | app、tests、migrations 全部通過 |
| 格式與文件 | 22 個 Python 檔案符合 Ruff format；Markdown 連結與 Git whitespace 檢查通過 |

完整驗證指令：

```bash
docker compose -p gainmiles-ticket04-tests -f compose.test.yaml run --build --rm tests
docker compose -p gainmiles-ticket04-tests -f compose.test.yaml run --rm tests mypy
docker compose -p gainmiles-ticket04-tests -f compose.test.yaml run --rm tests ruff check app tests migrations
```

PATCH 測試僅使用 POST 準備商品，再經 PATCH／單筆 GET 驗證，沒有依賴列表、seed 或刪除 API。沿用鎖定 Docker images 與真實 PostgreSQL；每個情境使用實際 migration 建立獨立暫存資料庫。

### 回滾證據

透過 POST 建立兩個共用分類的商品。在目標商品一次修改名稱、分類、金額、庫存與兩種集合時，測試用 AFTER DELETE trigger 確認新屬性、新分類及兩種新選項已寫入，再推進不隨 rollback 還原的 sequence 並拋錯。另一情境將同一 trigger 設為 deferred constraint，於 commit 時拋錯。

兩者皆回傳一般化 500，sequence 證明已到達寫入途中；目標與另一個商品的 GET 皆保留原內容，新分類不存在，兩種明細筆數維持原值。移除故障後重試成功，確認交易與 session 可正常恢復。

### 重疊更新與鎖等待

- 不同商品同時改為同名新分類：測試用 advisory lock 暫停分類 INSERT，透過 `pg_stat_activity` 確認兩個獨立 writer 都等待鎖後釋放。兩個 PATCH 皆 200，共用一筆新分類，舊分類保留。
- 同一商品先修改名稱、分類、庫存與兩種選項，再讓第二個 PATCH 等待。第一個請求確定到達 UPDATE 中的測試 trigger 後才啟動第二個，並確認兩個 writer 同時等待，再放行第一個。
- 第二個只改庫存時保留前一個請求已更新的分類與選項；第二個亦替換集合時，以第二次集合為完整最終值，不殘留前次新增的選項。

補測曾實際重現：若取得商品鎖的同一 statement 使用分類 JOIN，等待前的 snapshot 看不到前次交易新建的分類，第二個 PATCH 會因 category 為 None 回傳 500。改為先鎖住商品，再以 select-in 載入分類及選項後，兩個重疊案例通過。沒有新增版本欄位或樂觀版本鎖。

### Standards

Reviewer 唯讀檢查 `aead5a2…ecd8877`，無標準違反或需要提出的 baseline smell。驗證、HTTP 與交易分層明確，helper 不自行 commit，序列化前載入關聯。兩種明細替換保持簡短且明確，無需增加泛型抽象。

### Spec

另一位 reviewer 唯讀核對同一範圍，無缺漏、範圍擴張或可疑實作。部分更新、選項替換、不可變 code、驗證優先順序、共用分類、交易與競爭行為符合 ticket；共享解析與 fixture 調整直接支援這次功能。

兩軸 reviewer 未修改檔案或執行測試；上方結果由主代理實際執行。Standards：0 項；Spec：0 項，各軸均無最嚴重待修問題。

### 交付範圍

ticket 04 全部 11 項驗收完成，README、架構與 API 文件已更新。刪除與最終交付仍屬後續 tickets。本次專用測試容器於驗證後清除。工作提交在 `feat/flask-crud`，`main` 保持 `47fdb4a`，未 push 或建立 PR。


## Ticket 05 刪除商品並清除明細

完成日期：2026-09-12。實作 commit：`ca3e930`；分支：`feat/flask-crud`。

### 功能與測試

新增 DELETE `/api/products/{code}`，使用 SQLAlchemy `DELETE ... RETURNING code` 在同一 statement 判斷商品是否存在。尺寸與顏色沿用 PostgreSQL 外鍵 cascade，分類不刪除；外層交易成功提交後回傳空 body 的 204。未知或重複刪除回傳共用 404 PRODUCT_NOT_FOUND。無新 migration、依賴或測試用產品程式 hook。

| 檢查 | 結果 |
| --- | --- |
| DELETE TDD | 先回傳 405；實作後 204 且 body 為空，後續 GET 404 |
| 刪除單一測試檔 | 12 passed，包含成功、重複刪除、未知／大小寫不同／非法 URL code、最後商品與共用分類保留、cascade 及 commit 失敗 |
| 完整容器測試套件 | **276 passed**，包含 tickets 01 至 04 全部案例 |
| 容器內 mypy | 21 個 source files，無錯誤 |
| 容器內 Ruff | app、tests、migrations 全部通過 |
| 格式與文件 | 23 個 Python 檔案符合 Ruff format；Markdown 連結與 Git whitespace 檢查通過 |

完整驗證指令：

```bash
docker compose -p gainmiles-ticket05-tests -f compose.test.yaml run --build --rm tests
docker compose -p gainmiles-ticket05-tests -f compose.test.yaml run --rm tests mypy
docker compose -p gainmiles-ticket05-tests -f compose.test.yaml run --rm tests ruff check app tests migrations
```

測試以 POST 建立商品，DELETE 執行操作，再以單筆 GET 驗證；不依賴列表、seed 或 PATCH。DB 觀察限於分類保留、目標明細清除與回滾證據，使用實際 migration 建立的隔離 PostgreSQL 資料庫。

### 刪除與回滾證據

- 刪除唯一商品後，目標尺寸／顏色筆數皆為零，原分類識別值與名稱仍存在。
- 刪除共用分類中的一個商品後，另一個商品的完整 GET 表示保持不變，分類保留。
- 測試用 AFTER DELETE trigger 在顏色 cascade 階段，確認商品已不存在後推進不隨 rollback 還原的 sequence，再拋出錯誤；另一情境使用 deferred constraint trigger 於 commit 時失敗。
- 兩個失敗情境都回傳一般化 500，log 記錄錯誤。sequence 證明已進入實際刪除；rollback 後原商品、所有尺寸／顏色及同分類其他商品皆完整可讀，明細筆數與分類保持不變。
- 移除故障後重試 DELETE 成功，GET 為 404，另一商品仍不受影響。

### Standards

Reviewer 唯讀檢查 `ca15dfe…ca3e930`，無硬性標準違反或需要提出的 baseline smell。HTTP 與交易分工、共用錯誤格式及 DB cascade 使用符合架構與 schema 文件，沒有增加多餘抽象。

### Spec

另一位 reviewer 唯讀檢查同一範圍，無缺漏、錯誤實作或範圍擴張。204／404、分類保留、明細清除、其他商品不受影響及故障回滾均符合 ticket，測試不依賴尚未要求的其他操作。

兩軸 reviewer 未修改檔案或執行測試；上方結果由主代理實際執行。Standards：0 項；Spec：0 項，各軸均無最嚴重待修問題。

### 交付範圍

ticket 05 全部 7 項驗收完成，商品 CRUD 已實作，README、架構與 API 文件同步更新。整份作業的最終交付驗收仍屬 ticket 06，不能以本次測試代替。本次專用測試容器於驗證後清除。工作提交在 `feat/flask-crud`，`main` 保持 `47fdb4a`，未 push 或建立 PR。
