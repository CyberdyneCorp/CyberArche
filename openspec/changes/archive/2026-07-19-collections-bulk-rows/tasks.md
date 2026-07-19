# Tasks
- [ ] 1.1 Use case: delete_rows + set_rows_value (per-row access check; skip ids not in the collection; reject computed-property writes); return count changed
- [ ] 1.2 Router: POST rows/bulk-delete and rows/bulk-set
- [ ] 1.3 Frontend: row + select-all selection state in the VM; a bulk action bar (set property / delete / clear); re-query after
- [ ] 1.4 Tests: bulk delete + bulk set (count, access enforced, skips foreign ids, rejects formula/rollup); frontend selection + bulk calls
- [ ] 1.5 `openspec validate collections-bulk-rows --strict`; gates green
