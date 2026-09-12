# 後端技術架構

本文件記錄已確認的技術與執行流程。ticket 01 已實作 Flask health、Docker Compose、四張表的 migration 與測試入口；ticket 02 已實作新增商品、依 code 讀取與共用錯誤處理。ticket 03 已提供商品列表與 seed-demo。ticket 04 已提供 PATCH 部分更新與選項替換。刪除尚待後續 ticket 完成。目前可用的指令見 [README](../README.md)，本文保留整體目標架構。

## 技術與分工

| 元件 | 決定 |
| --- | --- |
| HTTP application | Flask，使用 `create_app()` 與商品 Blueprint |
| ORM | Flask-SQLAlchemy 整合 SQLAlchemy 2.x |
| Database | PostgreSQL；表結構見 [DB schema](db-schema.md) |
| Migration | Flask-Migrate／Alembic，migration 檔案納入版本控制 |
| Container application server | Gunicorn |
| 環境啟動 | Docker Compose，同時執行 API 與 PostgreSQL |
| 測試 | pytest，DB 整合測試使用獨立 PostgreSQL 測試資料庫 |

套件由 uv.lock 鎖定，Python／PostgreSQL image 以 digest 固定；PostgreSQL driver 採 psycopg 3。確切版本見 README。request validation 使用標準函式庫的明確欄位檢查、regex、Decimal 與 frozen dataclass；目前七欄位不需要額外驗證套件。

## 程式分層

```text
Routes → Schemas → Service → SQLAlchemy Models → PostgreSQL
```

- Routes：讀取 HTTP 請求，呼叫驗證與 Service，轉成 response/status code。
- Schemas：驗證 request，產生固定 JSON 結構；不查資料庫、不 commit。
- Service：完成商品操作，執行查詢並管理一次操作的交易。
- Models：定義四張表、relationship、主鍵、外鍵、唯一與 CHECK constraints。
- Errors：將已知錯誤轉為一致 JSON；未知錯誤記錄到容器 log，回傳一般化的 500 訊息。

目前 Service 直接使用 SQLAlchemy，未拆 Repository。使用 SQLAlchemy 2.x 的 `select()` 與 session API。

## 預計目錄

```text
app/
├── __init__.py
├── config.py
├── extensions.py
├── errors.py
├── models.py
├── seed.py
└── products/
    ├── routes.py
    ├── schemas.py
    └── service.py
migrations/
tests/
Dockerfile
compose.yaml
.env.example
pyproject.toml
README.md
```

## 交易與查詢

新增與更新商品時，分類的取得或建立、商品欄位、尺寸與顏色異動都在同一筆交易完成。Service 在成功時 commit，失敗時 rollback；helper 不自行 commit。JSON response 在 commit 成功後回傳。

查不到分類時建立分類；同時有兩個請求建立同名分類，需由唯一限制及衝突處理保證最終共用同一分類。重複商品 code 的判斷也要涵蓋 DB 寫入時的唯一限制衝突，不只在新增前查詢。

ticket 02 以 PostgreSQL `INSERT ... ON CONFLICT DO NOTHING RETURNING` 取得新分類物件；若分類已存在，再以獨立 SELECT 讀取。Service 建立商品時指定已載入的 Category；單筆查詢時明確載入分類、尺寸及顏色，避免 Schema 序列化時隱含查詢。READ COMMITTED 下，第二個 statement 能看見等待結束後已提交的同名分類。只有 `pk_products` 的唯一限制衝突轉成 409，其他 DB 錯誤保留為 500。Service 在交易內產生商品回應資料，離開交易區塊、commit 成功後才交回 route，避免提交後為了序列化再次查詢。

修改商品分類時只改商品的 `category_id`，不修改共用分類名稱。刪除商品清除其尺寸、顏色，保留分類。ORM relationship 的刪除設定需配合 DB cascade，並以整合測試驗證。

商品列表批次載入分類、尺寸、顏色，避免每筆商品各查明細。兩個集合不直接展開後加總庫存，避免交叉乘積。列表以 joinedload 載入單一分類，使用 `selectinload()` 批次載入兩種集合，再於 Python 依 code 排序。

PATCH 使用與新增相同的欄位驗證，明確區分欄位未傳入與非法 null。交易內先以 `SELECT FOR UPDATE` 鎖住商品，再分別載入分類、尺寸與顏色；關聯查詢在取得鎖後執行，避免等待前的 JOIN snapshot 看不到前一筆交易剛建立的分類。選項替換保留交集中的既有 ORM 明細、移除其餘明細並新增缺少值。分類解析沿用新增與 seed 使用的 `resolve_category`，helper 不自行 commit。

本作業 inventory 是總數的直接編輯，不包含訂單、預留或扣庫存流程。若兩個請求同時修改同一欄位，本版採最後成功寫入的值，不增加版本鎖。

## Compose 與啟動流程

| Service | 工作 | 生命週期 |
| --- | --- | --- |
| `db` | PostgreSQL，named volume 保存資料 | 持續執行 |
| `migrate` | `flask --app app db upgrade` | 成功或失敗後退出，不自動重啟 |
| `api` | Gunicorn 執行 `app:create_app()` | 持續執行 |

`migrate` 與 `api` 共用同一份 application image，使用相同 DB 設定。

啟動順序：`db` healthcheck 成功 → `migrate` 完成且 exit code 為 0 → `api` 啟動。Compose 分別使用 `service_healthy` 與 `service_completed_successfully`。

容器連 PostgreSQL 使用 service hostname `db`，而非 `localhost`。DB volume 掛載位置依選定的 PostgreSQL image 版本設定。API 綁定 `0.0.0.0`；環境設定由 Compose 傳入。

API 提供 `GET /health`：可查詢 DB 時回傳 200 與 `{"status":"ok"}`，DB 不可用時回傳 503 與 `{"status":"unavailable"}`。healthcheck 不要求存在 seed 資料。空表是合法啟動狀態。

首次啟動與 seed 指令：

```bash
docker compose up --build --wait
docker compose exec api flask --app app seed-demo
```

Compose 的 `--wait`、一次性 migration service 與 healthcheck 配合已於 ticket 01 驗證；seed 可在 schema 就緒後獨立執行。

更新既有環境的流程為：停止 API → 建置新 application image → 明確執行 migration → 成功後啟動新 API。失敗時保留 API 停止狀態並查閱 migration log；不自動執行 downgrade。

`depends_on` 管理啟動順序，不會因後續 migration 或 DB 失敗，自動停止原本已執行的 API。`docker compose restart` 也不作為 schema 或設定更新流程。

## Migration 與 seed

開發時產生 migration，人工檢查主外鍵、CHECK、索引與級聯行為後提交。執行環境只套用已提交的 migration；不在啟動時自動產生版本，不使用 `create_all()` 取代 migration。

`app/seed.py` 實作獨立 seed 邏輯，註冊為 `seed-demo` Flask CLI，沿用 app configuration 與 SQLAlchemy models。HTTP 建立與 seed 共用 Service 的 `add_product`，該 helper 只加入並 flush 分類、商品及明細，不自行 commit。HTTP 的 create operation 與 seed 各自管理外層交易。

- 資料來源為題目四筆商品；分類依名稱取得，不假設固定的 category_id。
- 在一筆交易中寫入所有缺少的範例商品與其明細。
- 商品 code 已存在時，整個商品跳過；不覆蓋名稱、分類、單價、庫存或明細。
- 印出新增及跳過商品筆數。失敗 rollback 並以非零 exit code 結束。
- 刪除範例商品後再 seed，會重新建立該商品；seed 不代表同步或重設所有現有資料。
- seed 不會隨 API 容器重啟自動執行。

## 實作驗收

- 全新獨立 DB 能從 migration 建出四張表並完成 CRUD；測試不依賴 demo seed。
- 重複 upgrade 無額外 schema 變動；重複 seed 不重複或覆蓋資料。
- API 錯誤格式與驗證符合 [API contract](api-contract.md)。
- 商品與明細更新失敗時全部回滾；刪除後無殘留明細。
- migration 失敗時初次啟動的 API 不啟動；healthcheck 就緒後才能視為啟動完成。
- 重建 application container 後，DB volume 中的資料仍存在。

README 應包含環境準備、啟動、seed、API 範例、測試、migration、查看 log、保留資料的停止方式及會刪除資料的重設方式。提交時附題目要求的 AI 完整對話。

## 參考

- [Flask Application Factories](https://flask.palletsprojects.com/en/stable/patterns/appfactories/)
- [Flask-SQLAlchemy Quick Start](https://flask-sqlalchemy.palletsprojects.com/en/stable/quickstart/)
- [SQLAlchemy Session Basics](https://docs.sqlalchemy.org/en/20/orm/session_basics.html)
- [Docker Compose startup order](https://docs.docker.com/compose/how-tos/startup-order/)
- [Docker Compose up](https://docs.docker.com/reference/cli/docker/compose/up/)
- [Alembic autogenerate](https://alembic.sqlalchemy.org/en/latest/autogenerate.html)
