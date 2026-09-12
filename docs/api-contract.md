# 商品 API contract

本文件記錄整體商品操作契約。ticket 02 至 05 已提供 POST 新增、單筆 GET、商品列表、PATCH、DELETE 與共用錯誤處理。可執行範例見 [README](../README.md)。

## 共通格式

Base path 為 `/api/products`。request/response 使用 JSON；POST、PATCH 必須使用 `Content-Type: application/json`。商品代碼是唯一且建立後固定的 URL 識別值。

DB 的尺寸、顏色明細在 JSON 中分別輸出 `sizes`、`colors` 陣列；`category` 輸出分類名稱。`category_id` 是內部關聯，不要求呼叫端提供。

金額本版選擇十進位字串作為輸入及輸出，避免 JSON 浮點數轉換。輸入可為 `"200"`、`"200.0"` 或 `"200.00"`，輸出統一為 `"200.00"`。不接受 JSON number、自動四捨五入或科學記號。

## 路由

| Method | Path | 行為 | 成功狀態 |
| --- | --- | --- | --- |
| POST | `/api/products` | 新增商品與明細 | 201，回傳商品及 Location header |
| GET | `/api/products` | 列出商品 | 200，回傳 data 陣列 |
| GET | `/api/products/{code}` | 讀取商品 | 200，回傳商品 |
| PATCH | `/api/products/{code}` | 部分更新商品 | 200，回傳更新後商品 |
| DELETE | `/api/products/{code}` | 刪除商品與明細 | 204，無 response body |

本版列表以 code 升冪回傳全部商品，不提供篩選或分頁；適用於本作業的小型資料集。單筆不存在時 GET、PATCH、DELETE 都回傳 404。

## 新增與商品回應

POST 範例：

```json
{
  "code": "A-001",
  "name": "Star",
  "category": "cloth",
  "sizes": ["S", "M"],
  "unit_price": "200.00",
  "inventory": 20,
  "colors": ["Red", "Blue"]
}
```

POST、單筆 GET、PATCH 的成功 response 都直接回傳上述七個欄位的商品物件，不包在 `data` 中。POST 的 Location 為 `/api/products/A-001`。

列表回應為 `{"data": [...]}`，其中每個元素為商品物件；無資料時為 `{"data": []}`。

尺寸與顏色是集合，不保留 request 順序。輸出 sizes、colors 各自依字串 Unicode code point 升冪排列，商品 code 同樣採此排序規則；例如 A-001 的 sizes 回傳 `["M", "S"]`，colors 回傳 `["Blue", "Red"]`。這不是衣服尺寸大小排序，測試不依賴插入順序或 DB 預設 collation。

## 欄位驗證

| 欄位 | 規則 |
| --- | --- |
| `code` | 必填字串；本版 URL 代碼格式採英數字、`-`、`_`，至少一字元；保留大小寫，全域唯一 |
| `name` | 必填字串，移除前後空白後不可為空 |
| `category` | 必填字串，移除前後空白後不可為空；區分大小寫 |
| `sizes` | 必填非空陣列，元素為去除前後空白後的非空字串，不可重複；區分大小寫 |
| `colors` | 同 sizes |
| `unit_price` | 必填十進位字串，0 至 9999999999.99，最多兩位小數；拒絕負號、正號、空白、NaN、Infinity、指數格式 |
| `inventory` | 必填 JSON 整數，0 至 2147483647；拒絕 boolean、字串及小數型輸入 |

POST 必須包含全部七個欄位。未知欄位、`null`、非 object JSON body 均回傳 422。code 不自動去空白或變更大小寫；其 API 格式限制不改變 DB `text` 欄位，也不從代碼推導分類。

文字欄位與集合元素須為 PostgreSQL 可儲存的 Unicode 文字；NUL 與未配對 surrogate 回傳 422。

分類以修整後的名稱查找，不存在時在商品操作的交易內建立。更新分類是修改商品引用，不修改共用分類的名稱。

## PATCH 規則

只修改有傳入的欄位；沒傳的欄位及明細維持不變。至少提供一個可更新欄位，空 object 回傳 422。

`code` 不是可更新欄位；即使傳入值與原代碼相同，也回傳 422。其餘欄位沿用新增驗證。

陣列採整組取代，不做合併或局部元素更新。例如：

```json
{
  "sizes": ["L"],
  "inventory": 12
}
```

會使商品只提供 L，總庫存改為 12；其他欄位維持不變。空陣列及 null 均拒絕。全部驗證通過後才寫入，商品與明細在同一交易內更新。

## 錯誤格式

所有 API 錯誤採固定結構，`fields` 沒有欄位資訊時為空 object。message 使用英文，呼叫端以穩定的 error.code 判斷錯誤。

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed.",
    "fields": {
      "inventory": ["Must be a non-negative integer."]
    }
  }
}
```

| HTTP status | error.code | 情況 |
| --- | --- | --- |
| 400 | `INVALID_JSON` | JSON 語法錯誤或 JSON body 為空 |
| 404 | `PRODUCT_NOT_FOUND` | 單筆商品不存在 |
| 404 | `NOT_FOUND` | 不存在的路由 |
| 405 | `METHOD_NOT_ALLOWED` | 路由不支援該 method |
| 409 | `PRODUCT_CODE_EXISTS` | 新增的 code 已存在，含競爭寫入導致的唯一限制衝突 |
| 415 | `UNSUPPORTED_MEDIA_TYPE` | POST/PATCH 未使用 application/json |
| 422 | `VALIDATION_ERROR` | 欄位缺少、值不合法、未知欄位或修改 code |
| 500 | `INTERNAL_ERROR` | 未預期錯誤，不回傳 SQL 或 traceback |

未加引號的 `NaN`、`Infinity` 與 `-Infinity` 不是合法 JSON，回傳 400；價格字串 `"NaN"` 等則是 JSON 可解析但欄位不合法，回傳 422。

處理順序：確認媒體類型與 JSON 可解析 → 驗證 body → 執行商品操作。只有通過 request 驗證後，才進行商品存在性與 DB 衝突判斷。

## 最小驗收案例

- 空資料庫新增含新分類的商品可成功，不必先 seed。
- POST 後 GET 可完整讀回商品；金額固定兩位小數字串、集合按規則排序。
- PATCH 只改 inventory 不影響其他欄位；替換 sizes 會移除舊尺寸。
- 修改某商品的 category 不影響同分類其他商品。
- 拒絕重複 code、修改 code、空集合、重複集合值、null、負庫存及 boolean 庫存。
- 拒絕價格超過兩位小數，且原資料保持不變。
- DELETE 後商品與兩種明細都不存在；再次 DELETE 回傳 404。
- DB 更新中途失敗時，商品、分類建立及明細異動全部 rollback。
