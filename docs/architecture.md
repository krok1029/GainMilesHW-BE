# 後端技術架構

本文件記錄已確認的技術與執行流程。ticket 01 已實作 Flask health、Docker Compose、四張表的 migration 與測試入口；商品 CRUD 及 seed 尚待後續 tickets 完成。目前可用的指令見 [README](../README.md)，本文保留整體目標架構。

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

套件由 uv.lock 鎖定，Python／PostgreSQL image 以 digest 固定；PostgreSQL driver 採 psycopg 3。確切版本見 README。request validation 套件留待 ticket 02 選定。

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

修改商品分類時只改商品的 `category_id`，不修改共用分類名稱。刪除商品清除其尺寸、顏色，保留分類。ORM relationship 的刪除設定需配合 DB cascade，並以整合測試驗證。

商品列表批次載入分類、尺寸、顏色，避免每筆商品各查明細。兩個集合不直接展開後加總庫存，避免交叉乘積。實作可採 `selectinload()` 載入集合。

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

預計首次啟動與 seed 指令：

```bash
docker compose up --build --wait
docker compose exec api flask --app app seed-demo
```

實作完成後需驗證選定 Compose 版本的 `--wait`、一次性 migration service 與 healthcheck 配合，確保回傳成功時可以直接執行 seed。

更新既有環境的流程為：停止 API → 建置新 application image → 明確執行 migration → 成功後啟動新 API。失敗時保留 API 停止狀態並查閱 migration log；不自動執行 downgrade。

`depends_on` 管理啟動順序，不會因後續 migration 或 DB 失敗，自動停止原本已執行的 API。`docker compose restart` 也不作為 schema 或設定更新流程。

## Migration 與 seed

開發時產生 migration，人工檢查主外鍵、CHECK、索引與級聯行為後提交。執行環境只套用已提交的 migration；不在啟動時自動產生版本，不使用 `create_all()` 取代 migration。

`app/seed.py` 實作獨立 seed 邏輯，註冊為 `seed-demo` Flask CLI，沿用 app configuration 與 SQLAlchemy models。

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
