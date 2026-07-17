# Tasks

- [x] 1.1 Domain scopes: drop `gmail_compose`; split `calendar` → `calendar.events` + `calendar.freebusy`; add `sheets` (`spreadsheets.readonly`) and `slides` (`presentations.readonly`) groups + scope constants
- [x] 1.2 Port + adapter: remove `gmail_create_draft`; add `sheets_read`, `slides_read`; keep `calendar_create_event`
- [x] 1.3 Fake (`FakeGoogleWorkspace`): remove draft, add sheets/slides reads
- [x] 1.4 Use cases: remove `gmail_draft`; `calendar_list`→events scope, `free_busy`→freebusy scope; add `sheets_read`/`slides_read`; keep `calendar_create_event`
- [x] 1.5 Agent tools: remove `google_gmail_draft`; add `google_calendar_create_event`, `google_sheets_read`, `google_slides_read`; gate each by the connection's granted scope
- [x] 1.6 Frontend consent groups: Gmail read-only; Calendar (read + create events); add Sheets and Slides
- [x] 1.7 Tests: read-only Gmail (no draft path), calendar create as an agent tool, sheets/slides read, per-scope gating; update existing google tests
- [x] 1.8 `openspec validate google-readonly-calendar-write --strict`; backend + frontend green
