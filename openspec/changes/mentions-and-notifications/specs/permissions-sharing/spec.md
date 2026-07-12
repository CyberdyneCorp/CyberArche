# permissions-sharing Specification

## ADDED Requirements

### Requirement: Comment mentions notify workspace members

The system SHALL create a `mention` notification when a comment mentions a user
who is a member of the document's workspace, identifying the comment's author and
the document. A mention is written in the comment body as an at-sign followed by
the user id in brackets. The system SHALL NOT notify the author for mentioning
themselves, and SHALL NOT create a notification for a mentioned user who is not a
member of the document's workspace.

#### Scenario: A mention notifies a member

- **WHEN** a member adds a comment that mentions another workspace member
- **THEN** the mentioned member SHALL receive a mention notification for that
  document

#### Scenario: Non-members and self-mentions are ignored

- **WHEN** a comment mentions the author, or a user who is not a workspace member
- **THEN** no notification SHALL be created for that mention
