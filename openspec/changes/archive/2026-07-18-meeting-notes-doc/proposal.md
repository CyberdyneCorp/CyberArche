# AI meeting notes → document

## Why

The agent can already read a member's meeting recordings and transcripts, but
turning one into a shareable, structured document is a manual copy-paste job.
"Turn this transcript into a doc — summary, decisions, action items" is the
single most-requested thing to do with a recording, and every piece (meetings
port, LLM, document creation, block insertion) already exists.

## What Changes

- Add `MeetingNotesUseCases.create_from_recording(caller, *, workspace_id,
  recording_id, access_token, teamspace_id=None)`: fetch the recording's
  transcript via the meetings port (delegated auth), have the LLM structure it
  into Summary / Key points / Decisions / Action items, create a new document
  titled from the recording, and populate it with the structured blocks. Returns
  the created document.
- New endpoints: `GET /api/v1/meetings` (list the caller's recordings for a
  picker) and `POST /api/v1/workspaces/{id}/meeting-notes`.
- A "Meeting notes" surface in the app: pick a recording → generate the doc →
  open it.

## Impact

- Affected specs: `ai-agent`.
- Affected code: new `use_cases/meeting_notes.py` composing document creation +
  block insertion; meetings + meeting-notes routers; wiring (build the use case);
  a meetings API client, a modal + store, and a trigger. No migration.
