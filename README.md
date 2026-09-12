# GainMiles 後端作業

Flask／PostgreSQL 商品目錄 API，提供完整 CRUD、欄位驗證、統一 JSON 錯誤與獨立 seed-demo。Docker Compose 負責資料庫、migration 與 Gunicorn；下方提供從乾淨環境執行與驗收的完整步驟。

## 啟動

需要 Docker Engine／Docker Desktop 與 Docker Compose v2。已驗證 Docker 28.4.0、Compose 2.39.2。以下指令均在專案根目錄執行，不需要在主機安裝 Python 或 PostgreSQL。

```bash
cp .env.example .env
docker compose up --build --wait --wait-timeout 90
curl --fail http://localhost:8000/health
```

預期 HTTP 200 與 `{"status":"ok"}`。若 8000 已被占用，修改 `.env` 的 `API_PORT`，並使用該 port 查詢。首次下載 images 和 Python 依賴需要網路。

Compose 依序等待 PostgreSQL healthy、執行 migration，再啟動 Gunicorn。migration 成功後停留在 exited 0 是正常狀態；失敗則不啟動 API。health 不依賴 seed，空商品目錄也是健康狀態。DB 查詢失敗回傳 HTTP 503 與 `{"status":"unavailable"}`。

| 服務 | 用途 |
| --- | --- |
| `db` | PostgreSQL，資料保存在 named volume |
| `migrate` | 共用 API image，執行既有 Alembic revisions 後退出 |
| `api` | Gunicorn／Flask，僅將 API port 發布到主機 loopback |

PostgreSQL 不發布主機 port。容器間使用 hostname `db`；`POSTGRES_USER`、`POSTGRES_PASSWORD`、`POSTGRES_DB` 由環境變數傳入，程式建立連線 URL 時會處理密碼特殊字元。範例帳密供本機作業使用。已有 DB volume 時，修改環境變數不會自動修改既有資料庫帳密。

## 新增與讀取商品

啟動後即可建立商品，不需要 seed 或先建立分類：

```bash
curl -i -X POST http://localhost:8000/api/products \
  -H 'Content-Type: application/json' \
  -d '{"code":"A-001","name":"Star","category":"cloth","sizes":["S","M"],"unit_price":"200","inventory":20,"colors":["Red","Blue"]}'
curl -i http://localhost:8000/api/products/A-001
```

POST 回傳 201 與 `Location: /api/products/A-001`；GET 回傳 200。兩者 body 相同：

```json
{"code":"A-001","name":"Star","category":"cloth","sizes":["M","S"],"unit_price":"200.00","inventory":20,"colors":["Blue","Red"]}
```

價格必須使用字串，庫存使用 JSON 整數；尺寸與顏色輸出依 Unicode code point 排序。再次送出同一商品的 POST 回傳 409：

```json
{"error":{"code":"PRODUCT_CODE_EXISTS","message":"Product code already exists.","fields":{}}}
```

將 POST 範例的 inventory 改為 `true`，會先回傳 422，即使 code 已經存在：

```json
{"error":{"code":"VALIDATION_ERROR","message":"Request validation failed.","fields":{"inventory":["Must be an integer from 0 to 2147483647."]}}}
```

查詢 `/api/products/missing` 回傳 404 與 `PRODUCT_NOT_FOUND`。完整欄位及錯誤規則見 [API contract](docs/api-contract.md)。一次新增中的分類、商品與兩種明細共同提交；DB 寫入或 commit 失敗會 rollback，回傳一般化的 500，詳細錯誤保留在 API log。

## 匯入範例資料與列表

在 migration 完成、API 就緒後明確執行 seed：

```bash
docker compose exec api flask --app app seed-demo
curl --fail http://localhost:8000/api/products
```

乾淨環境的 seed 輸出為 `Created: 4; skipped: 0.`；再執行一次為 `Created: 0; skipped: 4.`。列表回傳 200 與完整商品物件：

```json
{
  "data": [
    {"code":"A-001","name":"Star","category":"cloth","sizes":["M","S"],"unit_price":"200.00","inventory":20,"colors":["Blue","Red"]},
    {"code":"A-002","name":"Moon","category":"cloth","sizes":["L","M"],"unit_price":"300.00","inventory":10,"colors":["Red","White"]},
    {"code":"B-001","name":"Eagle","category":"pants","sizes":["L","M"],"unit_price":"100.00","inventory":23,"colors":["Green"]},
    {"code":"B-002","name":"Bird","category":"pants","sizes":["L","M","S"],"unit_price":"50.00","inventory":12,"colors":["Black"]}
  ]
}
```

未匯入且沒有自行建立商品時，列表為 `{"data":[]}`。商品按 code 的 Unicode code point 排序；列表回傳全部商品，不提供分頁或篩選。

seed 只補上缺少的範例 code，既有商品的名稱、分類、價格、庫存與尺寸／顏色全部保留，缺少的明細也不修復或合併。因此若先執行上方新增範例，第一次 seed 會是新增 3、跳過 1。刪除範例商品後再 seed，該商品會依原始值重建。非範例商品不受影響。

一次 seed 的所有新增商品與明細共用單一交易；中途失敗或 commit 失敗，整次 rollback，CLI 以非零 exit code 結束，既有資料保留。成功筆數在 commit 後才輸出。seed 不會隨 API 啟動或重啟自動執行，也不會清空資料。

## 部分更新商品

先依上方範例新增 A-001，或執行 seed，再送出 PATCH：

```bash
curl -i -X PATCH http://localhost:8000/api/products/A-001 \
  -H 'Content-Type: application/json' \
  -d '{"inventory":12,"sizes":["M","L"]}'
curl --fail http://localhost:8000/api/products/A-001
```

PATCH 回傳 200 與完整商品。若商品仍為原始範例值，回應為：

```json
{"code":"A-001","name":"Star","category":"cloth","sizes":["L","M"],"unit_price":"200.00","inventory":12,"colors":["Blue","Red"]}
```

只有傳入欄位會更新。sizes 從 S、M 改為 L、M，S 明細被移除、M 保留、L 新增；colors 未傳入，因此不變。colors 同樣採整組取代，不是追加或聯集。兩者回應皆以 Unicode code point 排序。

可以同時修改 name、category、unit_price、inventory、sizes 與 colors。category 改為新名稱時，在同一交易建立新分類；其他引用舊分類的商品不受影響。價格使用十進位字串，庫存為商品總數。

商品 code 建立後不可修改；即使提交相同值也回傳 422：

```bash
curl -i -X PATCH http://localhost:8000/api/products/A-001 \
  -H 'Content-Type: application/json' -d '{"code":"A-001"}'
```

```json
{"error":{"code":"VALIDATION_ERROR","message":"Request validation failed.","fields":{"code":["Product code cannot be changed."]}}}
```

空 object、null、未知欄位、空集合及其他不合法欄位也回傳 422。媒體類型及 JSON 解析、欄位驗證都在商品存在性檢查之前；合法更新請求找不到商品則回傳 404 PRODUCT_NOT_FOUND。

屬性、選項替換與新分類一起提交，寫入或 commit 失敗時全部 rollback。同一商品的重疊更新會依序讀取最新狀態，保留未提供欄位；同欄位採最後成功寫入的值。

## 刪除商品

先建立或 seed 商品，再依 code 刪除；DELETE 不需要 request body：

```bash
curl -i -X DELETE http://localhost:8000/api/products/A-001
curl -i http://localhost:8000/api/products/A-001
```

刪除成功回傳 **204 No Content**，body 為空。商品及其所有尺寸、顏色在同一交易刪除；分類保留，即使已無商品引用也不移除。同分類其他商品與明細不受影響。

後續 GET、再次 DELETE，或刪除未知 code 都回傳 404：

```json
{"error":{"code":"PRODUCT_NOT_FOUND","message":"Product not found.","fields":{}}}
```

未預期的刪除或 commit 失敗會回傳共用 500，整筆交易 rollback，原商品及明細仍完整可讀。若刪除的是四筆範例商品之一，之後再執行 seed-demo 會依原始值重建該商品。

## 版本與設定

Python image 內版本為 3.13.15，PostgreSQL image 內版本為 18.6；兩者以 manifest digest 固定。PostgreSQL 18 的 volume 掛在 `/var/lib/postgresql`。

Python 依賴由 `pyproject.toml` 宣告並在 `uv.lock` 鎖定全部解析版本及雜湊。容器使用 uv 0.6.16 與 locked sync，runtime 不安裝測試依賴；test image 則包含 pytest、mypy、Ruff。主要版本：Flask 3.1.3、Flask-SQLAlchemy 3.1.1、SQLAlchemy 2.0.52、Flask-Migrate 4.1.0、Alembic 1.20.0、psycopg 3.3.5、Gunicorn 23.0.0。

## Migration 與 log

```bash
docker compose ps --all
docker compose logs --tail=100 migrate api db
docker compose exec api flask --app app db current
docker compose run --rm migrate
```

最後一個指令重跑 upgrade；已在最新版本時不重建資料表。不在 API 啟動時產生新 migration，也不使用 `create_all()`。

需要調整 schema 時，先修改 models，再於可連線的開發環境產生 migration，檢查其 CHECK、外鍵、索引及刪除行為後納入版本控制。可用下方主機 Python 環境和對應 DB 環境變數執行：

```bash
uv run --locked flask --app app db migrate -m "Describe the schema change"
uv run --locked flask --app app db upgrade
uv run --locked flask --app app db check
```

主機執行時須提供可連線的 `DB_HOST`、`DB_PORT`、`POSTGRES_USER`、`POSTGRES_PASSWORD`、`POSTGRES_DB`；目前 Compose 的 DB 不對外發布 port，請在自己的開發 override 中明確設定，勿直接指向測試以外的資料庫跑測試。migration 生成後需重新 build application image。

既有環境套用新程式及 migration 時，執行：

```bash
sh scripts/update-environment.sh
```

腳本依序執行 `stop api` → `build` → `run --rm migrate` → `up --no-deps --wait api`。任何一步失敗立即以非零結束，migration 失敗時 API 保持停止，不自動 downgrade。可在腳本後提供 Compose 選項，例如 `sh scripts/update-environment.sh --env-file .env -p gainmiles`；務必沿用啟動時的 project 與設定，才能更新同一環境。

更新 migration 使用 `run --rm`，其 log 直接出現在更新指令輸出，不是舊的 startup migrate service log。需要留存時可使用 `sh scripts/update-environment.sh > update.log 2>&1`。失敗後檢查輸出、修正程式或設定，再明確重跑更新腳本；已停止的 API 不會自行恢復。

`depends_on` 控制啟動順序，不會在 DB 或 migration 後續失敗時自動停止已執行的 API。`docker compose restart` 不會套用修改後的 image 或環境設定，不作為 schema 更新流程。成功更新、migration 失敗保持停止及明確恢復已納入下方交付驗收。

## 測試與型別檢查

測試服務使用獨立 Compose project、獨立 PostgreSQL container 及 tmpfs，不掛載開發資料 volume。每個需要 DB 的測試再建立隨機名稱的空資料庫，透過真實 migration 建表，結束只刪除該測試自己建立的資料庫。

```bash
docker compose -p gainmiles-tests -f compose.test.yaml run --build --rm tests
docker compose -p gainmiles-tests -f compose.test.yaml run --rm tests mypy
docker compose -p gainmiles-tests -f compose.test.yaml run --rm tests ruff check app tests migrations
docker compose -p gainmiles-tests -f compose.test.yaml down --volumes
```

可在 `tests` 後指定單一測試，例如 `pytest -q tests/test_products.py`。health 透過 Flask test client 驗證；migration 使用 Flask CLI 及窄範圍 DB 完整性檢查，涵蓋必填、數值範圍、唯一限制、外鍵、cascade、重複 upgrade、schema 與 models 一致及空測試 DB 的 downgrade。

商品測試透過 Flask test client 與真實 PostgreSQL 驗證：

```bash
docker compose -p gainmiles-tests -f compose.test.yaml run --rm tests pytest -q tests/test_products.py
docker compose -p gainmiles-tests -f compose.test.yaml run --rm tests pytest -q tests/test_product_transactions.py
```

第一個檔案涵蓋新增讀回、欄位邊界與錯誤格式；第二個涵蓋共用分類、重複 code、重疊請求及交易回滾。競爭測試透過 PostgreSQL advisory lock 與 `pg_locks` 確認兩個獨立連線都正在等待後才釋放；回滾測試只在當次暫存 DB 安裝 trigger，分別於明細寫入及 commit 階段製造失敗。測試不需要 demo seed，也不在正式程式加入測試用 hook。

列表與 seed 的單一測試入口：

```bash
docker compose -p gainmiles-tests -f compose.test.yaml run --rm tests pytest -q tests/test_catalog.py
docker compose -p gainmiles-tests -f compose.test.yaml run --rm tests pytest -q tests/test_seed.py
```

列表測試包含排序、完整商品欄位及批次讀取預算。seed 測試透過公開 Flask CLI 與列表／單筆 API 驗證原始資料、筆數、重跑、保留已編輯內容、不修復選項、刪除後重建及不同分類識別值。中途失敗測試在暫存 DB 安裝 trigger，以不隨 rollback 還原的 sequence 確認已到達多筆寫入途中，再驗證整次新增回滾且既有資料保留。

PATCH 的單一測試入口：

```bash
docker compose -p gainmiles-tests -f compose.test.yaml run --rm tests pytest -q tests/test_patch_product.py
docker compose -p gainmiles-tests -f compose.test.yaml run --rm tests pytest -q tests/test_patch_transactions.py
```

測試使用 POST 準備商品，再以 PATCH 與單筆 GET 驗證，不依賴 seed、列表或刪除 API。交易測試在選項刪除途中與 commit 階段注入故障，確認原屬性、明細及分類保留；競爭測試確認新分類共用、同商品最後寫入值，以及等待中的更新能看見前一交易新建的分類。

DELETE 的單一測試入口：

```bash
docker compose -p gainmiles-tests -f compose.test.yaml run --rm tests pytest -q tests/test_delete_product.py
```

測試以 POST 建立商品，再經 DELETE／單筆 GET 驗證。窄範圍 DB 檢查確認目標明細已清除、分類仍存在；測試用 trigger 分別在明細 cascade 途中與 commit 階段製造失敗，驗證原商品及其他共用分類商品保留。這些測試不依賴列表、seed 或 PATCH。

Compose 啟動驗收從主機執行，不需要主機 Python：

```bash
sh tests/verify-startup.sh
```

此指令使用自動產生的專案名稱和隨機 API port，驗證首次啟動、共用 image、重複 migration、DB 中斷／恢復，以及 migration 失敗阻止 API 啟動。結束僅清除本次建立的驗收容器與 volumes，失敗時列出 log。

## 完整交付驗收

只需 Docker 與 POSIX shell，不需要主機 Python。從專案根目錄執行：

```bash
sh tests/verify-startup.sh
sh tests/verify-handoff.sh
```

第一個腳本驗證 migration／health 啟動順序及 DB 故障恢復。第二個腳本複製 `.env.example` 到暫存位置，以自動產生的 Compose project 與隨機 API port，依序驗證：

- 空 DB 建表並就緒；獨立 seed 得到四筆精確原始商品。
- 實際 Gunicorn HTTP 的列表、新增、單筆讀取、PATCH、DELETE 及主要錯誤回應。
- 編輯範例商品、刪除另一範例後，重啟與重建 API container、`down` 後重開都保留狀態，不自動 seed。
- 手動再 seed 只補回刪掉的範例，既有編輯不變。
- 既有環境更新成功；指定不存在的 migration revision 時更新失敗，API 保持停止、revision 不變，診斷 log 可查；移除故障後明確恢復。
- 在該驗收專案執行 `down --volumes` 後重開，得到全新空目錄。

兩個腳本都只清除自己建立的測試專案與 volumes。失敗會以非零結束並列出診斷。Python HTTP 驗證程式經 stdin 送入 API container 執行，無須主機依賴，也不在 application 啟動路徑插入驗收邏輯。完整 pytest、mypy 與 Ruff 請依上一節的獨立測試容器指令執行。實際結果見 [驗證紀錄](docs/verification.md)。

## AI 對話與總 PR

依提交者指定，AI 對話使用 [設計 PostgreSQL 正規化 Schema 分享頁](https://chatgpt.com/s/cx_6aa513c2f92081918a49b17929d983f7)。這是分享時點的快照，已確認可讀；涵蓋範圍見 [AI 對話交付來源](docs/ai-conversation.md)，驗證紀錄不作為對話逐字稿的替代。

整份作業維持在 `feat/flask-crud`，由功能 commits 累積，`main` 保持原始共同基底。[單一總 PR 草稿](docs/pr-summary.md) 整理變更、驗證與審核入口；目前不會自動 push、建立 PR 或 merge。

## 選用的主機 Python 開發環境

主機開發需 Python 3.13 與 uv。先啟動專用測試 PostgreSQL：

```bash
uv sync --locked
docker compose -p gainmiles-tests -f compose.test.yaml up --wait test-db
docker compose -p gainmiles-tests -f compose.test.yaml port test-db 5432
```

最後一個指令會顯示隨機分配的 loopback port。將下列 `<port>` 換成該值：

```bash
export TEST_DATABASE_URL='postgresql+psycopg://gainmiles_test:test-only@127.0.0.1:<port>/gainmiles_test'
uv run --locked pytest -q tests/test_health.py
uv run --locked mypy
uv run --locked ruff check app tests migrations
```

未提供 `TEST_DATABASE_URL`，或其資料庫名稱不是 `gainmiles_test` 時，需要 DB 的測試會失敗並提示設定；不會偷偷改用開發 DB 或 SQLite。

## 停止與重設

保留資料的停止方式：

```bash
docker compose down
```

以下指令會刪除本 Compose project 的 PostgreSQL volume 和其中所有資料，只在確定要重設本機作業資料時執行：

```bash
docker compose down --volumes
```

## 文件

- [資料模型](docs/db-schema.md)
- [技術架構](docs/architecture.md)
- [API contract](docs/api-contract.md)
- [母規格](.scratch/product-catalog-api/spec.md)
- [Ticket 01](.scratch/product-catalog-api/issues/01-container-startup-and-health.md)
- [Ticket 02](.scratch/product-catalog-api/issues/02-create-and-read-product.md)
- [Ticket 03](.scratch/product-catalog-api/issues/03-seed-and-list-catalog.md)
- [Ticket 04](.scratch/product-catalog-api/issues/04-patch-product-and-options.md)
- [Ticket 05](.scratch/product-catalog-api/issues/05-delete-product-and-details.md)
- [Ticket 06](.scratch/product-catalog-api/issues/06-reproducible-assignment-handoff.md)
- [單一總 PR 草稿](docs/pr-summary.md)
- [AI 對話來源](docs/ai-conversation.md)
- [驗證紀錄](docs/verification.md)
