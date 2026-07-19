# Clarify: meeting-notes documents are created private

## Why

The "meeting transcript to structured document" requirement says the document is
created "in the target workspace" but does not state *where* — and the shipped
behaviour (and users' expectation, per the sidebar's Private section) is that the
generated note is a **private** document, not filed under a teamspace. This
captures that behavioural guarantee in the spec.

## What Changes

- Modify the meeting-notes requirement to state the document is created as a
  private document of the workspace (not within a teamspace), so it appears in
  the member's Private section, with a scenario asserting it.

## Impact

- Affected specs: `ai-agent`.
- Affected code: none — documents behaviour already true (the generated doc has
  no teamspace); this is a spec clarification only.
