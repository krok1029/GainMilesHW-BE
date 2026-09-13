# GainMiles 商品目錄 API 與可重現的容器環境

Status: ready-for-agent

Completed: 2026-09-12；tickets 01–06 已完成。原規格保留規劃當時的敘述，實際交付見 [README](../../README.md)，測試指令與整體結果見 [技術架構](../../docs/architecture.md)。AI 對話依 README 中的使用者指定分享連結交付。

## Problem Statement

作業提交者需要根據題目的商品表，完成可透過 JSON 建立、讀取、更新及刪除商品的 Python 後端，並讓評閱者能在自己的電腦重現執行環境。原始資料將多個尺寸及顏色放在同一格，若直接儲存，容易重複商品屬性或錯誤分配庫存。

目前專案已有商品目錄詞彙、正規化資料模型、技術架構與 API contract，但沒有應用程式、資料庫 migration、容器設定或測試。提交者需要依這些已討論的決策實作完整作業，使評閱者可以啟動環境、建立資料表、獨立匯入範例資料並驗證 CRUD，而不依賴開發者電腦中的既有狀態。

## Solution

提供 Flask 商品目錄 API，透過 SQLAlchemy 操作 PostgreSQL。每個商品以固定的商品代碼識別，分類統一管理，尺寸及顏色各自儲存為集合明細，單價與庫存保留在商品層級。

以 Docker Compose 管理 PostgreSQL、一次性 migration 工作及 Gunicorn 執行的 Flask API。啟動時先等待資料庫就緒，再套用已提交的 migration，成功後啟動 API。評閱者另外執行 seed 指令即可匯入題目的四筆商品，重複執行不覆蓋已編輯的資料。

交付包含一致的 API 輸入輸出與錯誤格式、可重現的測試、完整操作說明，以及題目要求的 AI 對話記錄。

## User Stories

1. As an API consumer, I want to create a product with its code, name, category, sizes, price, inventory, and colors, so that I can manage the complete product record in one operation.
2. As an API consumer, I want each product code to be globally unique, so that I can identify a product without ambiguity.
3. As an API consumer, I want product codes to remain fixed after creation, so that existing product references remain stable.
4. As an API consumer, I want to list all products, so that I can inspect the current product catalog.
5. As an API consumer, I want an empty catalog to return an empty list successfully, so that I can use the API before loading demo data.
6. As an API consumer, I want to retrieve one product by its code, so that I can inspect its latest attributes and available options.
7. As an API consumer, I want prices to use an exact decimal representation, so that monetary values remain consistent across requests and responses.
8. As an API consumer, I want products, sizes, and colors to have deterministic output ordering, so that results are predictable.
9. As an API consumer, I want to update only the fields I provide, so that unrelated product information remains unchanged.
10. As an API consumer, I want a submitted size list to replace the previous size list, so that I can explicitly control the available sizes.
11. As an API consumer, I want a submitted color list to replace the previous color list, so that I can explicitly control the available colors.
12. As an API consumer, I want omitted option lists to remain unchanged, so that updating inventory does not alter sizes or colors.
13. As an API consumer, I want invalid, empty, or duplicate product options to be rejected, so that the catalog remains consistent.
14. As an API consumer, I want unknown fields and attempts to modify the product code to be rejected, so that mistakes are visible instead of silently ignored.
15. As an API consumer, I want inventory to be one non-negative integer per product, so that the source data is represented without inventing variant stock counts.
16. As an API consumer, I want invalid prices and inventory values to be rejected before persistence, so that bad input does not silently change stored values.
17. As an API consumer, I want to provide a category by name, so that creating a product does not require knowledge of internal database identifiers.
18. As an API consumer, I want missing categories to be created during a product operation, so that an empty database is immediately usable without seed data.
19. As an API consumer, I want changing one product's category to leave other products unchanged, so that shared category data is not accidentally renamed.
20. As an API consumer, I want product and option changes to succeed or fail together, so that partial records are never committed.
21. As an API consumer, I want concurrent requests for the same product code to return a clear conflict, so that duplicates cannot be created.
22. As an API consumer, I want concurrent creation of the same category to reuse one category, so that shared classification remains consistent.
23. As an API consumer, I want deleting a product to remove its size and color details, so that no orphaned product data remains.
24. As an API consumer, I want operations on a missing product to return a clear not-found response, so that I can distinguish missing data from server failures.
25. As an API consumer, I want predictable JSON error codes and field messages, so that I can handle malformed requests and validation failures reliably.
26. As an evaluator, I want to start the API and PostgreSQL through Docker Compose, so that I do not need to install the application's Python dependencies or database directly on my computer.
27. As an evaluator, I want startup to wait for PostgreSQL readiness and successful migration, so that the API does not start against missing tables.
28. As an evaluator, I want migration failure to prevent initial API startup, so that schema setup problems are visible immediately.
29. As an evaluator, I want a health endpoint that checks database availability without requiring demo products, so that I can distinguish an empty catalog from an unavailable service.
30. As an evaluator, I want database data to survive application container recreation, so that normal environment operations preserve my changes.
31. As an evaluator, I want to import the four reference products with a separate seed command, so that I can choose when to load demonstration data.
32. As an evaluator, I want repeated seed runs to skip existing products without overwriting their attributes or options, so that my API edits remain intact.
33. As an evaluator, I want seed failures to roll back the whole run and return a failing exit code, so that partial imports are not mistaken for success.
34. As an evaluator, I want seed output to report created and skipped product counts, so that I can verify the result of each run.
35. As a maintainer, I want reviewed and versioned migrations, so that schema changes can be reproduced on a clean or existing database.
36. As a maintainer, I want an explicit environment update procedure, so that migration failures do not leave an incompatible API serving requests.
37. As a maintainer, I want tests to exercise the public API against an isolated PostgreSQL database, so that behavior is validated using the actual persistence semantics.
38. As an evaluator, I want documented setup, API examples, test commands, logs, and reset behavior, so that I can assess the submission independently.
39. As an assignment submitter, I want the complete AI conversation included with the submission, so that I meet the assignment's disclosure requirement.

## Implementation Decisions

1. **Application structure:** use Python, Flask Application Factory and a product Blueprint. Separate HTTP handling, input/output schemas, product Service operations, ORM models, shared error handling, and seed logic. Service directly uses SQLAlchemy; no separate Repository layer is required at this scale.
2. **Persistence integration:** use Flask-SQLAlchemy with SQLAlchemy 2.x interfaces and PostgreSQL. Flask-SQLAlchemy manages engine and session lifecycle; the Service owns the transaction for each write operation. Gunicorn runs the application in its container. Choose and lock compatible dependency and image versions during implementation; the PostgreSQL driver and validation library remain implementation choices.
3. **Normalized model:** use four tables. Products contain code, name, category reference, unit price, and inventory. Categories contain a generated identifier and unique name. Product sizes use a composite key of product code and size. Product colors use a composite key of product code and color. All product fields are required; DB constraints enforce key uniqueness, referential integrity, non-empty stored strings, and numeric bounds.
4. **Product identity:** code is the product's natural primary key, is globally unique, and cannot be modified through the API. Other tables reference it. API codes are non-empty strings containing ASCII letters, digits, hyphens, or underscores; preserve case and reject surrounding whitespace. Do not infer category from the code prefix. DB code storage remains text; API immutability is enforced by request validation, not merely by primary-key constraints.
5. **Stock and variants:** inventory is one total per code; price also belongs to the product. Sizes and colors are independent option collections. Their Cartesian product does not establish the existence of actual variants, and source stock must not be duplicated or divided across inferred combinations.
6. **Numeric types:** persist price as numeric with precision 12 and scale 2, and use Python Decimal. Accept price as a non-negative ordinary decimal string with zero, one, or two fractional digits and a value no greater than 9999999999.99. Output exactly two fractional digits. Reject JSON numbers for price, excess decimal places, signs, whitespace, exponent notation, NaN, and Infinity. Inventory must be a JSON integer between zero and 2147483647; reject booleans, strings, and fractional input.
7. **Option and text validation:** trim name, category, size, and color values before checking that they are non-empty strings. Names and option values remain case-sensitive. Sizes and colors must be non-empty arrays without duplicates after trimming. Reject null values, unknown fields, and non-object request bodies. Every product field is required for creation.
8. **Category resolution:** requests identify categories by name, not by internal identifier. Reuse an existing trimmed name or create it within the same transaction as the product write. Resolve concurrent category creation using the DB uniqueness guarantee and conflict handling. Changing a product category changes its reference; it never renames the shared category. Product deletion retains category records.
9. **CRUD contract:** the product collection is exposed at `/api/products`. POST creates a product and returns 201 with the product and a Location header. Collection GET returns 200 with a data array. GET by code returns 200 with the product. PATCH by code returns 200 with the updated product. DELETE by code returns 204 with no body. GET, PATCH, and DELETE for a missing product return 404.
10. **Product representation:** expose exactly code, name, category, sizes, unit_price, inventory, and colors. Single-product operations return the product directly. Collection responses wrap products in a data array, including an empty array when no products exist. Products are sorted by code; sizes and colors are independently sorted by Unicode code point order. Do not rely on input order or database collation. This is lexical ordering, not garment-size ordering. The initial small-data implementation has no pagination or filtering.
11. **PATCH semantics:** modify only supplied fields; omitted fields remain unchanged. Supplied arrays replace the entire corresponding collection. Reject empty arrays, null, an empty update object, and any submitted code field even if its value matches the current code. Validate the complete input before any writes.
12. **Atomic writes:** category creation, product attributes, and size/color mutations commit together or roll back together. Helpers do not commit independently, and success responses follow successful commit. Coordinate ORM deletion behavior with database cascades. Concurrent writes to the same product field use the last successfully written value; no optimistic version field is required in this scope.
13. **Efficient retrieval:** load related option collections in batches rather than issuing a query for each product. Avoid multiplying size and color rows into duplicated response values or inflated inventory. The precise loading technique is an implementation choice, with SQLAlchemy select-in loading suitable for the collections.
14. **Error contract:** product API failures return a JSON error object with a stable code, an English message, and a fields mapping of field names to message arrays; fields is an empty mapping when no field-specific information applies. Invalid or absent JSON returns 400 INVALID_JSON; unknown routes return 404 NOT_FOUND; missing products return 404 PRODUCT_NOT_FOUND; unsupported methods return 405 METHOD_NOT_ALLOWED; duplicate codes return 409 PRODUCT_CODE_EXISTS, including DB race conflicts; unsupported write media types return 415 UNSUPPORTED_MEDIA_TYPE; invalid fields return 422 VALIDATION_ERROR; unexpected failures return 500 INTERNAL_ERROR without SQL or tracebacks in the response. Validate media type and JSON parsing first, then the body, then existence and DB conflicts.
15. **Compose topology:** define persistent DB and API services plus a one-shot migration service. API and migration use the same application image and DB configuration. The migration service does not restart automatically. Connect to PostgreSQL using its Compose service hostname; use a named DB volume with a mount appropriate to the selected PostgreSQL image version, and bind the application server to all container interfaces.
16. **Startup sequencing:** wait for DB health, execute committed migrations successfully, then start the API. Configure API health checks and a startup command that waits for readiness. Verify the selected Compose version's handling of healthy services and a successfully completed one-shot migration job. Initial migration failure must leave the API unstarted and produce inspectable logs.
17. **Health endpoint:** GET `/health` returns 200 with status ok when a database query succeeds, or 503 with status unavailable when the database is unavailable. This operational endpoint has its own simple status response. Empty product tables and missing seed data are healthy states.
18. **Migration lifecycle:** use Flask-Migrate and Alembic. Generate and review migrations during development, include them in version control, and apply only existing revisions at runtime. Review constraints, keys, cascades, indexes, and rename operations. Repeating an upgrade at the current revision must not recreate or duplicate schema objects. Schema migration is the mechanism for building tables.
19. **Updating an existing environment:** stop the API, build the new application image, explicitly run the migration, then start the API only after success. Failure keeps the API stopped and does not trigger an automatic downgrade. Startup dependencies are not a mechanism for automatically stopping an already-running API; a container restart is not the schema/configuration update procedure.
20. **Seed interface and transaction:** provide a separate seed implementation exposed as the seed-demo Flask CLI command. Run it explicitly after schema setup. Resolve categories by name rather than hard-coded generated identifiers. Import all missing sample products and their details in one transaction. Skip an entire product when its code already exists, preserving all existing attributes and details. Print created and skipped product counts; failure rolls back the run and exits non-zero. The seed command does not run automatically when API containers restart.
21. **Seed lifecycle limits:** re-running seed after deleting a sample product recreates that product. Seed is not a reset or reconciliation tool and does not repair or overwrite existing sample products. A separate documented data-reset operation must explicitly describe that it deletes data.
22. **Sample data:** import Star / A-001 / cloth / sizes S and M / price 200 / inventory 20 / colors Red and Blue; Moon / A-002 / cloth / sizes M and L / price 300 / inventory 10 / colors Red and White; Eagle / B-001 / pants / sizes M and L / price 100 / inventory 23 / color Green; Bird / B-002 / pants / sizes S, M, and L / price 50 / inventory 12 / color Black. A clean import produces two categories, four products, nine size rows, and six color rows.
23. **Delivery:** provide dependency and image version locking, an environment-variable example, and reproducible instructions for startup, seed, CRUD examples, tests, migrations, updates, logs, stopping while preserving data, and destructive reset. Preserve and include the complete AI conversation as required by the original assignment.

## Testing Decisions

1. **Primary testing seam:** exercise the public HTTP interface through the Flask test client with a real, isolated PostgreSQL database. This preserves the already agreed API and database integration-testing direction. Route handling, validation, Service behavior, serialization, and persistence are tested together without separate mock-heavy tests for each layer.
2. **What makes a good test:** assert observable status codes, headers, response bodies, later read results, and durable data effects. Test a meaningful user scenario or failure boundary, not a private method call, exact internal query sequence, ORM implementation detail, or the chosen module layout. Keep only narrowly scoped database observations where an integrity promise such as orphan removal cannot be observed through the product API.
3. **Existing prior art:** the project currently contains design documents and a glossary, with no application code, tests, fixtures, or established test harness. Use the documented product examples and agreed API contract as behavior references. Introduce one primary API integration seam rather than inventing separate test abstractions for every layer.
4. **Test isolation:** build a separate PostgreSQL test database through the actual migrations, create each scenario's data independently, and isolate cleanup so no test can modify the demo/development database. Tests do not depend on seed having run, test execution order, hard-coded category identifiers, or database default sorting.
5. **CRUD lifecycle:** start with an empty catalog, create a product and new category, read it back, list it, patch scalar fields and option collections, delete it, and verify missing-product behavior. Assert the Location header, exact decimal output, array replacement, preserved omitted fields, fixed ordering, and empty responses where specified.
6. **Validation and errors:** cover missing and unknown fields, invalid content types, malformed JSON, null and non-object bodies, empty PATCH, immutable code, invalid code characters, empty or duplicate collections, trim behavior, invalid numeric types and ranges, boolean inventory, and excessive price precision. Verify the fixed error envelope and that rejected writes leave existing data unchanged.
7. **Shared data and conflicts:** verify that changing one product's category does not rename another product's category, that existing categories are reused, and that duplicate-code writes return conflict. Exercise overlapping writes using independent DB sessions to validate category uniqueness and duplicate-code race handling; avoid timing-only tests that merely hope the writes overlap.
8. **Transaction integrity:** verify whole-operation rollback after a controlled failure during a multi-table write, including any newly created category. A validation-only rejection is not evidence of rollback after writes. Drive the operation through the API; any narrow fault-injection fixture must avoid making private Service call order part of the test contract. Verify successful deletion removes size and color details while preserving shared categories.
9. **Operational testing seam:** use the existing public command surfaces—Compose and the Flask CLI—for a small set of environment checks. These verify initial startup, actual migrations, seed exit status and output, health availability, and data persistence. They complement the API seam because HTTP alone cannot prove container startup ordering or migration failure behavior.
10. **Migration and startup scenarios:** verify clean-database upgrade, repeated upgrade, API readiness after success, API not starting after an initial migration failure, and the documented existing-environment update failure behavior. Check that health is successful without demo data and becomes unavailable when DB access fails.
11. **Seed scenarios:** verify the exact clean-import counts and values, repeat seed without duplicates, edit an existing sample product and confirm seed preserves it, delete one sample product and confirm seed recreates it, and inject an import failure to verify full rollback and a non-zero exit code. Observe command results and resulting API/database state rather than seed helper calls.
12. **Environment and handoff:** recreate the application container and verify DB data survives, then execute the documented setup and verification steps against a fresh environment. Record what actually ran and any remaining limitations; do not claim these planned checks have already passed.

## Out of Scope

- Inventory, pricing, or availability per size-and-color variant; inferring variants from option combinations.
- Orders, reservations, checkout, stock deduction, inventory history, or allocation workflows.
- Authentication, permissions, multi-tenancy, payment processing, and production infrastructure beyond the specified local container environment.
- Modifying a product code through the API, soft deletion, or automatic redirects for renamed codes.
- Standalone category-management endpoints, global size/color dictionaries, garment-size ranking, or input-order preservation.
- Product search, filtering, pagination, bulk import beyond the four reference products, and additional frontend work.
- Repository abstractions, microservices, queues, caching services, asynchronous database architecture, or optimistic version locking.
- Automatic demo loading at startup, overwriting existing products during seed, automatic migration generation at startup, or automatic destructive database resets.
- Splitting this spec into implementation tickets or starting implementation as part of the current to-spec operation.

## Further Notes

- This spec synthesizes the conversation and the existing design documents. The original assignment requires JSON CRUD, an RDBMS installed through Docker, service startup instructions, and the complete conversation if AI is used. The more detailed rules are project decisions rather than additional claims about the assignment text.
- Product-level inventory, code as the fixed product identity, Flask/PostgreSQL/SQLAlchemy, container startup migrations, separate seed execution, and the suggested API rules were discussed with the user. Price strings, deterministic lexical ordering, code character restrictions, and unpaginated listing were subsequently recorded as implementation defaults; this spec retains those defaults.
- The project is a single product-catalog context. Use the established Product, Code, Category, Size, Color, Inventory, and Variant vocabulary. There are currently no ADRs or implementation/test conventions to override.
- This is the parent feature specification in the user-selected local Markdown issue tracker. The ready-for-agent status means the implementation can be planned from this spec; it does not mean code exists, tests passed, or an external GitHub issue was created.
- The API plus PostgreSQL integration seam preserves the previously accepted testing approach. Operational command checks cover the startup and seed guarantees that cannot be demonstrated solely through HTTP.
