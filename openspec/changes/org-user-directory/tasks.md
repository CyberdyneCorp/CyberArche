# Tasks: org-user-directory

## 1. Application layer (ports + use cases)

- [x] 1.1 Add `DirectoryPort` protocol + `DirectoryUser`/`DirectoryPage` types to `application/ports/identity.py`; add an `InMemoryDirectory` to `application/testing/fakes`
- [x] 1.2 Extend `MembershipRepository` port with `list_workspace_members` and `remove_workspace_member` (role changes reuse the existing `add_workspace_member` upsert); update in-memory fake
- [x] 1.3 Add `OrgDirectoryUseCases.list_org_users` (tenant from caller claims; personal tenant → empty page; directory failure → typed unavailable error)
- [x] 1.4 Add workspace-members use cases: list (any member, best-effort directory enrichment), change role (owner-only), remove (owner-only), with last-owner protection (also enforced on the invite upsert path); unit tests over fakes for all authz/edge scenarios

## 2. Adapters (outbound)

- [x] 2.1 Implement `CyberdyneDirectory` adapter in `adapters/outbound/auth/cyberdyne.py` calling `GET /api/v1/orgs/{org_id}/members` with the service token; map errors to the unavailable error; unit tests with mocked httpx
- [x] 2.2 Implement the new `MembershipRepository` methods in `PostgresMembershipRepository`; SQL-shape unit tests + port-contract coverage (postgres leg runs where TEST_DATABASE_URL is set)

## 3. Adapters (inbound HTTP)

- [x] 3.1 Add `GET /api/v1/org/users` router (search/page/page_size, 503 on directory unavailable); wire in `Container`
- [x] 3.2 Add `GET/PATCH/DELETE /api/v1/workspaces/{id}/members[/{user_id}]` to the workspaces router; API tests: member list, non-member 403, owner-only mutations, last-owner 409

## 4. Frontend (Svelte 5 MVVM)

- [x] 4.1 API clients `lib/api/orgUsers.ts` and `lib/api/workspaceMembers.ts`
- [x] 4.2 ViewModels `orgUsers.svelte.ts` (debounced search, unavailable flag) and `workspaceMembers.svelte.ts` (list/invite/setRole/remove, error surfacing)
- [x] 4.3 ShareDialog: replace raw-id input with org-user picker combobox (email + avatar, role select), raw-id fallback when directory unavailable
- [x] 4.4 SettingsModal: add `members` TabId + TABS entry + pane — searchable member list, invite via picker, per-member role dropdown, remove; owner-gated controls
- [x] 4.5 Frontend tests per existing conventions (vitest component/VM tests if present)

## 5. Verification & docs

- [x] 5.1 Run backend + frontend test suites; fix regressions (backend 1019 passed; frontend 681 passed, svelte-check + build clean; ruff + lint-imports clean)
- [x] 5.2 Verify end-to-end against the running stack (share dialog picker, members tab flows, degraded mode with directory down) — driven in a real browser against the API + live CyberdyneAuth sign-in; found and fixed a stale role-select after a rejected last-owner demote
- [x] 5.3 Update docs/config samples for the `directory:read` client grant (docs/deployment.md); archive the OpenSpec change after merge
