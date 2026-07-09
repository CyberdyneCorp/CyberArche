# mcp-server Specification

## MODIFIED Requirements

### Requirement: Document tools
The MCP server SHALL provide tools to search documents, read a document, create a
document, and edit a document. Editing SHALL support appending blocks, inserting
blocks after a given block, and replacing an existing block's content. Every
edit SHALL be applied through the document CRDT and SHALL enforce the caller's
edit permission.

#### Scenario: Search then read
- **WHEN** a client calls the search tool with a query
- **THEN** the server SHALL return matching documents the caller may access
- **AND** a subsequent read tool call SHALL return that document's content

#### Scenario: Append blocks through a tool
- **WHEN** a client calls the insert tool with no position
- **THEN** the blocks SHALL be appended to the end of the document
- **AND** the edit SHALL be visible to live collaborators

#### Scenario: Insert blocks at a position
- **WHEN** a client calls the insert tool with an `after_block_id`
- **THEN** the new blocks SHALL appear immediately after that block
- **AND** the remaining blocks SHALL keep their order

#### Scenario: Replace a block's content
- **WHEN** a client calls the replace tool with a block id and new content
- **THEN** that block's type and data SHALL be replaced
- **AND** other blocks SHALL be unchanged

#### Scenario: Editing without permission is refused
- **WHEN** a caller who may only view the document calls an edit tool
- **THEN** the server SHALL refuse the edit
