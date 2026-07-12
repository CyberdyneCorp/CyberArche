# ai-agent Specification

## ADDED Requirements

### Requirement: Saved agent skills

The system SHALL let a workspace member save a named, reusable agent instruction
(a "skill") in the workspace, optionally with a short description and an
instruction template containing simple `{variable}` placeholders. Skills SHALL be
workspace- and tenant-scoped and shared with the workspace. Invoking a skill
SHALL expand its declared variables into a concrete instruction string and run
that instruction through the existing agent tool-loop against the current
document/workspace; a skill SHALL produce only instruction text and SHALL NOT
introduce any new agent-loop mechanics. Listing and running a skill SHALL require
workspace membership; creating and editing a skill SHALL require editor rights;
deleting a skill SHALL require the skill's creator or a workspace owner. Running a
skill SHALL respect the caller's permissions on the current document and
workspace and SHALL NOT widen access.

#### Scenario: Save a named skill

- **GIVEN** a workspace member with editor rights
- **WHEN** they save a skill with a name, optional description, and an
  instruction template
- **THEN** the system SHALL create the skill in that workspace
- **AND** the skill SHALL appear when the workspace's skills are listed

#### Scenario: Invoke a skill expands variables and runs it

- **GIVEN** a saved skill whose instruction template contains `{variable}`
  placeholders
- **WHEN** a member invokes the skill and supplies values for its variables
- **THEN** the system SHALL expand each `{variable}` into the supplied value to
  produce a concrete instruction string
- **AND** SHALL run that instruction through the agent tool-loop against the
  current document/workspace

#### Scenario: Skills are workspace and tenant scoped

- **GIVEN** a skill saved in one workspace of a tenant
- **WHEN** a member of a different workspace or a different tenant lists skills
- **THEN** that skill SHALL NOT be returned

#### Scenario: Only authorized roles create, edit, or delete

- **GIVEN** a workspace member with view-only rights
- **WHEN** they attempt to create, edit, or delete a skill
- **THEN** the operation SHALL be denied
- **AND** deleting a skill SHALL be permitted only for the skill's creator or a
  workspace owner

#### Scenario: Running a skill respects the caller's document permissions

- **GIVEN** a caller with view-only permission on the current document
- **WHEN** they run a skill whose instruction would edit the document
- **THEN** the edit SHALL be denied by the agent's permission checks
- **AND** the skill SHALL NOT grant any access the caller does not already have
