# Tasks
- [x] 1.1 Snapshot `label` (domain + migration 0016 + postgres repo + fake); record accepts optional label; rename method
- [x] 1.2 `diff_blocks(old, new)` domain fn (added/removed/modified by block id) + `SnapshotUseCases.diff(...)` (snapshot↔snapshot or snapshot↔current)
- [x] 1.3 Endpoints: diff (GET), label on record, rename (PATCH)
- [x] 1.4 Frontend: History modal — timeline (time/author/label), view + restore, compare-two block diff; viewmodel + api client; entry point (doc header/menu)
- [x] 1.5 Tests: diff detects add/remove/modify; label persists; rename; access-scoped; frontend viewmodel
- [x] 1.6 `openspec validate version-history --strict`; backend + frontend gates green
