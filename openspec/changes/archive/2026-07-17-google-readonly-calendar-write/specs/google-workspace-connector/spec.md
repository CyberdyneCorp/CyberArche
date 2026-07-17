# google-workspace-connector Specification

## MODIFIED Requirements

### Requirement: Gmail tools

The system SHALL provide agent tools to search and read the connected user's
Gmail. Gmail access SHALL be **read-only**: the system SHALL request only the
`gmail.readonly` scope and SHALL NOT provide any tool that composes, drafts,
sends, or otherwise modifies mail.

#### Scenario: Search and read mail

- **GIVEN** a user connected with the `gmail.readonly` scope
- **WHEN** the agent runs a Gmail search or reads a message on that user's behalf
- **THEN** the system SHALL return matching messages the user can access

#### Scenario: No write capability

- **WHEN** the Gmail consent scopes are requested
- **THEN** the system SHALL NOT request `gmail.compose`, `gmail.send`, or
  `gmail.modify`
- **AND** no agent tool SHALL create a draft or send mail

#### Scenario: Missing scope blocks the tool

- **GIVEN** a user connected without the Gmail scope
- **WHEN** a Gmail tool is invoked
- **THEN** the system SHALL NOT call Google
- **AND** SHALL return an error asking the user to grant Gmail permission

### Requirement: Calendar tools and scheduling

The Calendar SHALL be the only writable Google surface. The system SHALL provide
agent tools to list Calendar events, find free/busy times across a window, and
create events. Event write SHALL use the `calendar.events` scope and free/busy
SHALL use `calendar.freebusy`; the system SHALL NOT request the broad full
`calendar` scope. The agent MAY create events within the granted scope.

#### Scenario: Find free/busy times

- **GIVEN** a user connected with the `calendar.freebusy` scope
- **WHEN** the agent requests free/busy for a time window
- **THEN** the system SHALL return the user's busy periods for that window

#### Scenario: The agent may create an event

- **GIVEN** a user connected with the `calendar.events` scope
- **WHEN** the agent invokes the create-event tool
- **THEN** the system SHALL create the event on the user's primary calendar
- **AND** SHALL return the created event id

#### Scenario: Create is blocked without the events scope

- **GIVEN** a user connected without the `calendar.events` scope
- **WHEN** the create-event tool is invoked
- **THEN** the system SHALL NOT call Google
- **AND** SHALL return an error asking the user to grant Calendar permission

## ADDED Requirements

### Requirement: Sheets and Slides read

The system SHALL provide read-only agent tools for Google Sheets and Google
Slides, requesting only the `spreadsheets.readonly` and `presentations.readonly`
scopes. No tool SHALL modify a spreadsheet or presentation.

#### Scenario: Read a spreadsheet

- **GIVEN** a user connected with the `spreadsheets.readonly` scope
- **WHEN** the agent reads a spreadsheet's values on that user's behalf
- **THEN** the system SHALL return the requested cell values
- **AND** SHALL NOT request any spreadsheet write scope

#### Scenario: Read a presentation

- **GIVEN** a user connected with the `presentations.readonly` scope
- **WHEN** the agent reads a presentation on that user's behalf
- **THEN** the system SHALL return its slide text
- **AND** SHALL NOT request any presentation write scope

#### Scenario: Missing scope blocks the tool

- **GIVEN** a user connected without the Sheets (or Slides) scope
- **WHEN** the corresponding tool is invoked
- **THEN** the system SHALL NOT call Google
- **AND** SHALL return an error asking the user to grant that permission
