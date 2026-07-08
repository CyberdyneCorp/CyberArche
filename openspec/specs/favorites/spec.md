# favorites Specification

## Purpose
TBD - created by archiving change add-teamspaces-and-agent-editing. Update Purpose after archive.
## Requirements
### Requirement: Favourite a document
The system SHALL let a user mark a document they can view as a favourite, and
SHALL let them remove it.

#### Scenario: Add and remove a favourite
- **WHEN** a user favourites a document they may view
- **THEN** the document SHALL appear in that user's favourites
- **AND** removing it SHALL take it out of the list

#### Scenario: Cannot favourite an inaccessible document
- **WHEN** a user favourites a document they may not view
- **THEN** the system SHALL deny the request

### Requirement: Favourites are per user
A user's favourites SHALL be visible only to that user.

#### Scenario: Favourites are private
- **WHEN** two users favourite different documents in the same workspace
- **THEN** each user's favourites list SHALL contain only their own

