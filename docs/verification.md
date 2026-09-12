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
