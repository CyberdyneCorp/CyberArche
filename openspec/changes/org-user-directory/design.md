# Design: org-user-directory

## Context

CyberArche stores no user records — identity lives in CyberdyneAuth and every
membership row (`workspace_memberships`, `document_grants`, teamspace members)
keys on an opaque `user_id` string from the JWT `sub`. The tenant is the JWT
`org_id` claim. CyberdyneAuth's only user listing today is admin-user-gated;
its repo is adding `GET /api/v1/orgs/{org_id}/members` callable by a
client-credentials token holding a `directory:read` grant (branch
`org-members-directory`). CyberdyneAuth users have no display-name field —
identity for pickers is email + avatar_url.

The settings modal (`SettingsModal.svelte`) registers tabs via a `TABS` array
+ `TabId` union; teamspace members endpoints/dialog are the existing precedent
for membership management.

## Goals / Non-Goals

**Goals:**
- Let any authenticated org user browse/search their organization's users to
  invite them by picking, not by pasting ids.
- Full workspace-membership administration (list/change role/remove) in
  settings, with sound authorization and last-owner protection.
- Degrade gracefully: sharing must keep working when CyberdyneAuth's directory
  is down or the service token lacks the grant.

**Non-Goals:**
- No local persistence/caching of user profiles (no new tables; directory is
  read-through).
- No cross-org sharing; the directory only ever serves the caller's own org.
- No workspace-level "pending invitations" concept — invites remain immediate
  membership grants, as today.
- Display names: out of scope until CyberdyneAuth models them.

## Decisions

1. **DirectoryPort in `application/ports/identity.py`** (protocol:
   `list_org_users(org_id, *, search, page, page_size) -> DirectoryPage`)
   with a `CyberdyneDirectory` adapter next to the other CyberdyneAuth
   adapters, using `ClientCredentialsTokenSource` for auth. Alternative — a
   repository port — rejected: this is identity data owned by the IdP, so it
   belongs with the identity ports; hexagonal wiring stays symmetric with
   `IamAuthorization`.
2. **SPA endpoint `GET /api/v1/org/users`** resolves the org exclusively from
   `CallerContext.tenant_id`. A personal tenant (tenant == subject, i.e. no
   org) returns an empty page rather than an error, so the picker simply has
   nothing to offer. Alternative — 404 — rejected: it forces the frontend to
   special-case personal accounts.
3. **Directory failure → 503 with a typed error**, frontend falls back to the
   raw-id input (same behavior as today). We do not cache responses;
   picker queries are interactive and low-volume.
4. **Workspace members API mirrors teamspace members** (`GET .../members`,
   `PATCH .../members/{user_id}` `{role}`, `DELETE .../members/{user_id}`) for
   consistency. `MembershipRepository` gains `list_workspace_members`,
   `set_workspace_role`, `remove_workspace_member`; Postgres impl over the
   existing `workspace_memberships` table — no migration.
5. **Authorization**: listing requires any role on the workspace; role change
   and removal require `owner` (existing `AccessControl` helpers). The use
   case rejects demoting/removing the workspace's last owner (counted in the
   same transaction) so a workspace can never become ownerless. Members lists
   are enriched with directory data best-effort — if the directory is down the
   list still renders with bare user ids.
6. **Frontend**: new `lib/api/orgUsers.ts` + `lib/api/workspaceMembers.ts`
   clients; `orgUsers.svelte.ts` ViewModel with debounced search shared by the
   ShareDialog picker and the Members tab; `workspaceMembers.svelte.ts` for
   the tab. Members tab registers as a new `TabId`/`TABS` entry. The picker is
   a combobox listing email + avatar; selecting fills the invite target, and a
   "use raw id" affordance remains for the degraded path.

## Risks / Trade-offs

- [CyberdyneAuth filter semantics: primary-org column vs `user_organizations`
  m2m] → the new endpoint includes both; CyberArche treats its response as
  authoritative and adds no local filtering.
- [Directory outage degrades member-list labels to raw ids] → acceptable;
  membership operations never depend on the directory.
- [`directory:read` grant misconfigured in an environment] → surfaced as the
  same 503/fallback path, logged distinctly for ops.
- [Email is PII now exposed org-wide] → scoped to authenticated members of the
  same org only; no anonymous or cross-org access path.

## Migration Plan

Backend and frontend ship together in one PR; no DB migration. The feature is
inert until the CyberdyneAuth endpoint is deployed and the CyberArche client
is granted `directory:read` — until then the UI uses the fallback path.
Rollback = revert; no data changes.

## Open Questions

- None blocking. Display names pend on CyberdyneAuth modeling them.
