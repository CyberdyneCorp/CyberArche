# ai-agent Specification

## MODIFIED Requirements

### Requirement: Summarize and draft
The agent SHALL summarize a document or a selection of blocks, and SHALL draft
or rewrite content on request, returning results as blocks that can be inserted.
When a selection is given, the summary SHALL be scoped to the selected blocks.

#### Scenario: Summarize a document
- **WHEN** a user requests a summary with no selection
- **THEN** the agent SHALL produce a summary of the whole document the user can
  insert as blocks

#### Scenario: Summarize a selection
- **WHEN** a user requests a summary of specific block ids
- **THEN** the agent SHALL scope the summary to those blocks

#### Scenario: Rewrite a selection
- **WHEN** a user selects blocks and requests a rewrite with an instruction
- **THEN** the agent SHALL return revised blocks for that selection
