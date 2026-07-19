# Proposal: org-user-directory

## Why

Inviting someone to a workspace or document today requires pasting their raw
CyberdyneAuth user id — there is no way to see who is in the organization, and
no way to see or manage who is already in a workspace. This makes sharing
error-prone (silent grants to mistyped ids) and leaves workspace membership
unauditable from the UI.

## What Changes

- CyberArche gains an organization user directory sourced from CyberdyneAuth's
  new org-members endpoint (`GET /api/v1/orgs/{org_id}/members`, called with
  our service token holding a `directory:read` grant). Exposed to the SPA as
  `GET /api/v1/org/users` with search + pagination; the org is always resolved
  from the caller's verified claims, never from request input.
- Workspace membership becomes manageable: list members, change a member's
  role, and remove a member (`GET/PATCH/DELETE` under
  `/api/v1/workspaces/{id}/members`). Listing is visible to any workspace
  member; mutations are owner-gated; the last owner can never be demoted or
  removed.
- The Share dialog replaces the raw user-id input with an org-user picker
  (search by email, avatar shown, role select), falling back to raw-id entry
  when the directory is unavailable.
- Workspace Settings gains a **Members** tab: searchable member list with
  email/avatar/role, invite via the picker, per-member role dropdown, and
  remove — mutations owner-gated.

## Capabilities

### New Capabilities

- `org-directory`: listing the users of the caller's organization (identity
  data proxied from CyberdyneAuth: id, email, avatar, active flag) with search
  and pagination, and its authorization and degradation rules.
- `workspace-members`: enumerating and administering workspace memberships —
  list with roles, change role, remove member, last-owner protection.

### Modified Capabilities

- `permissions-sharing`: the invite requirement changes from "by CyberdyneAuth
  identity (raw id)" to "by selecting an organization user from the directory,
  with raw-id fallback".

## Impact

- **Backend**: new `DirectoryPort` (application/ports/identity.py) +
  CyberdyneAuth adapter (adapters/outbound/auth/); new org-users use case and
  HTTP router; `MembershipRepository` port + Postgres impl gain
  list/update/remove for workspace members; new workspace-members endpoints in
  the workspaces router; authz checks in `AccessControl`.
- **Frontend** (Svelte 5 MVVM): new `orgUsers` and `workspaceMembers` API
  clients + ViewModels; `ShareDialog.svelte` picker; `SettingsModal.svelte`
  Members tab.
- **External dependency**: CyberdyneAuth must ship
  `GET /api/v1/orgs/{org_id}/members` callable by our client-credentials token
  (tracked in the CyberdyneAuth repo, branch `org-members-directory`).
- **DB**: no new tables (memberships already exist); no migration expected.
- **Specs**: adds `org-directory` and `workspace-members`; modifies
  `permissions-sharing`.
