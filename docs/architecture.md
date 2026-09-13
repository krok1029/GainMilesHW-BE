# 技術架構

## 元件與分層

| 元件 | 用途 |
| --- | --- |
| Python 3.13／Flask | Application factory `create_app()` 與商品 Blueprint |
| Flask-SQLAlchemy／SQLAlchemy 2.x | ORM、查詢與交易；以 psycopg 3 連接 PostgreSQL 18 |
| Flask-Migrate／Alembic | 套用納入版本控制的 schema migration |
| Gunicorn | 容器內的 HTTP application server |
| Docker Compose | 管理 API、migration 與資料庫的啟動順序 |
| pytest／mypy／Ruff | PostgreSQL 整合測試、型別及程式碼檢查 |

Python 套件由 [uv.lock](../uv.lock) 鎖定，容器 image 以 digest 固定。設定入口為 [.env.example](../.env.example)，包含 `POSTGRES_USER`、`POSTGRES_PASSWORD`、`POSTGRES_DB` 與 `API_PORT`。

```text
HTTP → Routes → Schemas（驗證）→ Service → SQLAlchemy Models → PostgreSQL
            ← Schemas（序列化）←
```

- `app/products/routes.py`：處理 HTTP request、response 與 status code。
- `app/products/schemas.py`：驗證欄位、以 Decimal 處理金額並序列化回應，不查 DB 或 commit。
- `app/products/service.py`：查詢與商品操作，管理一次操作的交易；直接使用 SQLAlchemy。
- `app/models.py`：四張表的關聯與 constraints，見 [DB schema](db-schema.md)。
- `app/errors.py`：統一 JSON 錯誤，未知錯誤寫入 log，對外隱藏 SQL 與 traceback。

## 資料一致性

新增與更新的分類、商品、尺寸及顏色在同一筆交易內完成；成功 commit 後才回傳，失敗全部 rollback。共用 helper 不自行 commit。

分類依名稱取得或建立，以唯一限制與 `INSERT ... ON CONFLICT DO NOTHING RETURNING` 處理競爭；未新增時再以獨立 SELECT 取得既有分類。只有商品主鍵的唯一限制衝突轉為 409。修改分類只改商品引用，不改共用分類名稱。

PATCH 先以 `SELECT FOR UPDATE` 鎖住商品，再載入分類與選項，確保等待鎖後讀取到已提交的關聯。傳入的選項集合整組替換，未傳欄位保留；同一欄位採最後成功寫入的值。庫存代表每個商品的總量，沒有訂單、預留或扣庫存流程。

DELETE 使用 `DELETE ... RETURNING` 判斷商品是否存在，由外鍵級聯刪除尺寸與顏色，保留分類。列表以 joinedload 載入分類、selectinload 批次載入選項，避免每筆各查明細；回應排序與驗證規則見 [API 文件](api-contract.md)。

## 容器、migration 與 seed

```mermaid
flowchart LR
    db[PostgreSQL healthy] --> migrate[Migration exit 0]
    migrate --> api[Gunicorn API healthy]
```

`migrate` 與 `api` 共用 application image 與 DB 設定。初次啟動依 `service_healthy`、`service_completed_successfully` 等待前置服務；migration 失敗時 API 不啟動。migration 只套用已提交版本，不在啟動時 autogenerate 或呼叫 `create_all()`。

容器以 hostname `db` 連線，資料庫不發布主機 port；PostgreSQL named volume 掛載於 `/var/lib/postgresql`。API 在容器內綁定 `0.0.0.0:8000`，主機只發布至 loopback。

`GET /health` 在 DB 可查詢時回傳 200 與 `{"status":"ok"}`，不可用時回傳 503 與 `{"status":"unavailable"}`。空表可正常啟動。

`seed-demo` 是獨立 Flask CLI，在單一交易中新增缺少的四筆範例商品，分類依名稱解析。已存在的 code 整筆跳過，不覆蓋或修補；刪除範例後再 seed 會重建該筆。CLI 回報新增／跳過數，失敗 rollback 並以非零狀態結束。啟動與 seed 指令見 [README](../README.md)。

## 更新與排查

既有環境更新時執行：

```bash
sh scripts/update-environment.sh
```

腳本依序停止 API、build、執行 migration，成功才啟動 API 並等待 health。任一步驟失敗皆停止流程，API 保持停止；migration 錯誤直接顯示在指令輸出，不自動 downgrade。可附加 Compose 選項，例如 `sh scripts/update-environment.sh --env-file .env -p gainmiles`。

`depends_on` 不會因 DB 後續故障而自動停止既有 API；`docker compose restart` 不會套用新的 schema 或環境設定。

```bash
docker compose ps -a
docker compose logs api db migrate
docker compose run --rm migrate flask --app app db current
```

需要清空資料重新開始時，執行 `docker compose down --volumes`；此指令會刪除專案的 PostgreSQL volume 與全部資料。之後依 README 重新啟動及 seed。

## 測試

在獨立 Compose 專案執行，不使用開發資料庫：

```bash
docker compose -p gainmiles-tests -f compose.test.yaml run --build --rm tests
docker compose -p gainmiles-tests -f compose.test.yaml run --rm tests mypy
docker compose -p gainmiles-tests -f compose.test.yaml run --rm tests ruff check app tests migrations
docker compose -p gainmiles-tests -f compose.test.yaml run --rm tests ruff format --check app tests migrations
docker compose -p gainmiles-tests -f compose.test.yaml down --volumes
sh tests/verify-startup.sh
sh tests/verify-handoff.sh
```

pytest 使用真實 PostgreSQL，每個測試以 migration 建立獨立資料庫。startup 腳本驗證啟動順序、重跑 migration、DB 中斷及 migration 失敗；handoff 腳本經實際 HTTP 驗證 seed、CRUD、資料持久化、更新失敗／恢復與資料重設。兩支腳本建立並清理各自的 Compose 專案與 volumes。

2026-09-12 完整驗收結果：276 tests passed，mypy、Ruff 與兩支操作腳本皆通過。
