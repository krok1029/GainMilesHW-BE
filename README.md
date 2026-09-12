# GainMiles 後端作業

目前完成 ticket 01：Flask health endpoint、PostgreSQL 四張商品目錄資料表、migration、Docker Compose 啟動流程及測試入口。商品 CRUD 與 seed-demo 分別由後續 tickets 實作，目前尚未提供。

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

既有環境套用新程式及 migration 時，依序執行，migration 失敗就停止，不執行下一步：

```bash
docker compose stop api
docker compose build
docker compose run --rm migrate
docker compose up --no-deps --wait api
```

`depends_on` 控制啟動順序，不會在 DB 或 migration 後續失敗時自動停止已執行的 API。`docker compose restart` 不會套用修改後的 image 或環境設定，不作為 schema 更新流程。此 ticket 尚未驗收既有環境更新的完整故障流程，該整合驗收屬 ticket 06。

## 測試與型別檢查

測試服務使用獨立 Compose project、獨立 PostgreSQL container 及 tmpfs，不掛載開發資料 volume。每個需要 DB 的測試再建立隨機名稱的空資料庫，透過真實 migration 建表，結束只刪除該測試自己建立的資料庫。

```bash
docker compose -p gainmiles-tests -f compose.test.yaml run --build --rm tests
docker compose -p gainmiles-tests -f compose.test.yaml run --rm tests mypy
docker compose -p gainmiles-tests -f compose.test.yaml run --rm tests ruff check app tests migrations
docker compose -p gainmiles-tests -f compose.test.yaml down --volumes
```

可在 `tests` 後指定單一測試，例如 `pytest -q tests/test_health.py`。health 透過 Flask test client 驗證；migration 使用 Flask CLI 及窄範圍 DB 完整性檢查，涵蓋必填、數值範圍、唯一限制、外鍵、cascade、重複 upgrade、schema 與 models 一致及空測試 DB 的 downgrade。

Compose 啟動驗收從主機執行，不需要主機 Python：

```bash
sh tests/verify-startup.sh
```

此指令使用自動產生的專案名稱和隨機 API port，驗證首次啟動、共用 image、重複 migration、DB 中斷／恢復，以及 migration 失敗阻止 API 啟動。結束僅清除本次建立的驗收容器與 volumes，失敗時列出 log。

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
- [驗證紀錄](docs/verification.md)

原作業要求使用 AI 時提供完整對話，提交前需一併附上。完整 CRUD、seed 與最終交付驗收仍屬後續 tickets。
