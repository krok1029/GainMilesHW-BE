# 01 — 啟動容器環境並確認資料庫就緒

**What to build:** 評閱者可以從乾淨環境啟動 PostgreSQL 與 Flask API，由啟動流程套用 migration 建好商品目錄資料表，並透過 health endpoint 確認資料庫可用。這張 ticket 交付可獨立驗證的容器到 HTTP、資料庫完整路徑。

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

**Completed:** 2026-09-12；實作 commit `3c1d18b`。

**Parent:** [GainMiles 商品目錄 API 與可重現的容器環境](../spec.md)

- [x] 使用 Flask Application Factory、Flask-SQLAlchemy／SQLAlchemy 2.x、PostgreSQL、Flask-Migrate／Alembic 與 Gunicorn，選定相容版本並鎖定依賴及 container image 版本。
- [x] Compose 提供 DB、一次性 migration、API 三個服務；migration 與 API 共用 application image 與 DB 設定，migration 完成或失敗後退出，不自動重啟。
- [x] 全新資料庫透過已提交的 migration 建立商品、分類、商品尺寸、商品顏色四張表，包含母規格的主鍵、複合主鍵、唯一限制、外鍵、CHECK、數值型別、索引與級聯行為。
- [x] migration 經人工檢查後納入版本控制；啟動只套用現有版本，不產生 migration 或透過 ORM 建表捷徑取代 migration。重複 upgrade 不重複建立表或破壞資料。
- [x] 啟動等待 DB healthcheck 成功，再等待 migration exit code 為零，最後啟動 API；初次 migration 失敗時 API 不啟動，指令回報失敗且能取得診斷 log。
- [x] GET `/health` 在 DB 查詢成功時回傳 200 與 status ok，DB 不可用時回傳 503 與 status unavailable；不要求存在商品或 seed 資料。
- [x] API healthcheck 與等待就緒的啟動指令搭配正常，確認選定 Compose 版本能處理一次性 migration 服務，成功返回後 API 確實可呼叫。
- [x] 容器透過 DB service hostname 連線，API 綁定容器外可存取的介面，PostgreSQL 使用符合 image 版本的 named volume；環境設定可透過文件中的範例準備。
- [x] 建立以 pytest、Flask test client 及獨立 PostgreSQL 測試資料庫為核心的測試入口；測試資料庫由實際 migration 建立，cleanup 與設定隔離不影響開發或 demo 資料。
- [x] 經 HTTP 與公開操作指令驗證健康／不健康狀態、空 DB 啟動、重複 migration 與初次 migration 失敗情境，不以私有函式呼叫順序作斷言。
- [x] 補上實際可執行的初次啟動、health 檢查、測試、migration 與 log 操作說明，記錄驗證結果。

## Completion

全部 11 項驗收已完成。完整容器測試 23 passed，mypy 與 Ruff 通過；實際 Compose 驗證涵蓋成功啟動、重複 migration、DB 中斷／恢復與 migration 失敗阻止 API 啟動。Standards／Spec 雙軸 code-review 皆無 actionable findings。Status 保留原 triage 分類，Completed 與已勾選驗收項目表示本 ticket 已完成。

詳細證據見 [驗證紀錄](../../../docs/verification.md)。
