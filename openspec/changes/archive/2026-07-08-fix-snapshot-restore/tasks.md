# Tasks

## 1. CRDT engine

- [x] 1.1 Add `replace_blocks(state, blocks) -> bytes` to `CrdtEnginePort`
- [x] 1.2 Implement in the pycrdt adapter: reconcile by block id (insert / merge / delete / reorder) in one transaction; wholesale replace on type change
- [x] 1.3 Return an empty update when the document already matches
- [x] 1.4 Unit tests: insert, delete, reorder, data merge, id preservation, idempotence

## 2. Restore use case

- [x] 2.1 Give `SnapshotUseCases` the CRDT engine and `RealtimeUseCases`
- [x] 2.2 `restore` computes the replacing update and applies it via `realtime.apply(origin=f"restore:{user}")`
- [x] 2.3 Skip the apply when the update is empty (D-5); still record the snapshot
- [x] 2.4 Wire the new dependencies in the Container
- [x] 2.5 Backend tests, one per scenario: content replaced, applied through CRDT, snapshot recorded, ids preserved, idempotent, commenter rejected, unknown snapshot

## 3. Contract + regression

- [x] 3.1 Cover `replace_blocks` for the only CrdtEnginePort adapter (tests/test_crdt_engine.py). The port-contract suite parametrises over *multiple* adapters (memory/postgres); the CRDT port has a single implementation, so a parametrised contract would compare pycrdt to itself.
- [x] 3.2 Regression test proving the old no-op fails (read the document back, not the snapshot row)
- [x] 3.3 Realtime test: a restore reaches a connected relay client
