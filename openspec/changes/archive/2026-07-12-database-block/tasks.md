# Tasks

## 1. Backend
- [x] 1.1 Whitelist `database` in `domain/blocks.py`
- [x] 1.2 Regression test: `database` accepted

## 2. Frontend model
- [x] 2.1 `viewmodels/database.svelte.ts`: schema + rows over a per-block Y.Map; operations; debounced mirror to `data`
- [x] 2.2 Unit tests: add/remove property, add/remove row, set cell, sort, group-by, move row

## 3. Frontend UI
- [x] 3.1 `DatabaseBlock.svelte`: Table view (typed cell editors, add/remove row+column, rename, type menu, sort)
- [x] 3.2 Board view (group by select; add card; drag card between groups)
- [x] 3.3 View switcher; register the `database` block in the slash menu

## 4. Validate
- [x] 4.1 `openspec validate database-block --strict`; backend + web green
