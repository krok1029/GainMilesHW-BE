# 06 — 完成可重現的作業交付

**What to build:** 評閱者可以只依提交內容，在乾淨環境啟動服務、匯入範例、操作完整 CRUD、執行測試並更新環境，且能分辨保留資料與重設資料的操作。這張 ticket 驗證整體交付路徑，各功能自身測試應已隨前置 tickets 完成。

**Blocked by:** 03 — 匯入範例資料並瀏覽商品目錄；04 — 部分更新商品與替換尺寸／顏色；05 — 刪除商品並清除明細。

**Status:** ready-for-agent

**Completed:** 2026-09-12；實作 commit `facaafc`。

**Parent:** [GainMiles 商品目錄 API 與可重現的容器環境](../spec.md)

- [x] 在全新且與開發資料隔離的 Compose 環境，依交付說明完成準備設定、等待 migration／health 就緒、獨立 seed、列表、新增、單筆讀取、PATCH、DELETE 與執行測試。
- [x] 從乾淨環境取得題目四筆精確商品資料；所有功能遵守母規格，沒有依賴開發者電腦上既有的分類、DB、Python 套件或硬編碼生成識別值。
- [x] 正常重啟／重建 application container 後，API 編輯過的資料仍由 DB volume 保留，且不會自動 seed；手動再 seed 仍保留既有編輯。
- [x] 完成並驗證既有環境更新流程：停止 API、建置新 application image、明確套用 migration，成功後才啟動 API；故意讓 migration 失敗時，API 保持停止、錯誤可查、不自動 downgrade。
- [x] 使用公開 Compose／CLI 指令驗證操作結果，不將 depends_on 誤當成會自動停止既有 API 的機制，也不將容器 restart 當成套用 schema 或環境設定更新。
- [x] 操作文件完整涵蓋必要環境版本、套件與 image 鎖定、環境變數範例、啟動、health、seed、API 成功及錯誤範例、測試、migration、更新、log、保留資料的停止及明確刪除資料的重設方式。
- [x] 實際跑過文件中的主要操作流程，記錄通過項目、測試結果與任何未解決限制，不以計畫中的檢查當成已完成證據。
- [x] 整理題目要求的完整 AI 對話供交付；不得以摘要或部分對話冒充完整記錄。若工具無法取得完整記錄，明確指出缺少來源並在提交前補齊。
- [x] 所有作業變更持續位於既有功能分支，以功能分組 commits，main 保持共同基底；提供適合單一總 PR 的變更與驗證摘要，本 ticket 本身不要求自動 push、開 PR 或 merge。

## Completion

全部 9 項驗收依本輪使用者指示完成。完整容器測試 276 passed，mypy 與 Ruff 通過；startup 與 handoff 操作腳本均實際通過，包含精確 seed、完整 CRUD、資料持久化、既有環境更新失敗／恢復及明確 volume 重設。Standards／Spec 雙軸 code-review 均無 actionable findings。

AI 對話依使用者明確指定的 [分享連結](https://chatgpt.com/s/cx_6aa513c2f92081918a49b17929d983f7) 交付；已確認頁面可讀，並在 [README](../../../README.md) 揭露快照截至 ticket 06 開始，沒有將本次驗證摘要冒充完整對話。後續訊息不會自動加入該快照。

Status 保留原 triage 分類，Completed 與勾選項目表示本 ticket 已完成。交付入口見 [README](../../../README.md)，測試指令與整體結果見 [技術架構](../../../docs/architecture.md)。未 push、開 PR 或 merge。
