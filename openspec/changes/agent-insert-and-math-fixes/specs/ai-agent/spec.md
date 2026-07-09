# ai-agent Specification

## MODIFIED Requirements

### Requirement: Every answer yields insertable blocks
An agent answer that did not itself modify the document SHALL be accompanied by
blocks derived from it, so the user can insert the answer without retyping it.
When the agent already applied its change to the document during the run (via an
editing tool), the answer SHALL NOT offer the same content for manual insertion,
so it is not added twice. Blocks the agent inserts SHALL be normalized so a
source-based block (code, latex, mermaid) is never left empty when its content
was provided under a different field.

#### Scenario: Insert a conversational answer
- **WHEN** the agent answers a question without editing the document
- **THEN** the response SHALL include blocks representing the answer
- **AND** the user SHALL be able to insert them into the document

#### Scenario: No duplicate insert after a live edit
- **WHEN** the agent applies an edit to the document during its run
- **THEN** the answer SHALL NOT carry insertable blocks for that content

#### Scenario: An agent-inserted source block is never empty
- **WHEN** the agent inserts a mermaid, latex, or code block with the content
  under a field other than `source`
- **THEN** the inserted block SHALL still render that content, not a placeholder
