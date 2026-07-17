# Google connector: read-only everywhere, Calendar the only writable surface

## Why

The Google connector should follow a simple, least-privilege model: the agent
reads across Google Workspace but the **only** thing it can change is the
Calendar. Today two things break that model — Gmail requests the `gmail.compose`
write scope (draft creation), and Calendar requests the broad full `calendar`
scope. Sheets and Slides aren't connected at all.

## What Changes

- **Gmail becomes read-only.** Drop the `gmail.compose` scope, the
  `gmail_draft` use case, the `google_gmail_draft` agent tool, and the adapter's
  `gmail_create_draft`. Gmail keeps `gmail.readonly` (search + read).
- **Calendar is the one writable surface, and the agent may write it.** Replace
  the full `calendar` scope with `calendar.events` (read + write events) plus
  `calendar.freebusy` (read). Expose `google_calendar_create_event` as an agent
  tool (previously HTTP-only), so the agent can create events within that scope.
- **Add read-only Sheets and Slides.** New scope groups `sheets`
  (`spreadsheets.readonly`) and `slides` (`presentations.readonly`) with
  `google_sheets_read` and `google_slides_read` agent tools.
- Frontend consent groups updated to match (Gmail read-only; Calendar labelled
  read + create; add Sheets and Slides).

## Impact

- Affected specs: `google-workspace-connector`.
- Affected code: `domain/google_workspace.py` (scopes), `ports/google_workspace.py`,
  `adapters/outbound/google/client.py`, `application/testing/fakes.py`,
  `use_cases/google_workspace.py`, `use_cases/agent.py` (tool set),
  `web/src/lib/viewmodels/google.svelte.ts`.
- No data migration: scopes are requested at consent time. Existing connections
  that granted `gmail.compose` or full `calendar` keep working for reads;
  reconnecting narrows them to the new scope set.
