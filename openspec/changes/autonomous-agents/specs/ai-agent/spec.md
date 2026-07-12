# ai-agent Specification

## ADDED Requirements

### Requirement: Scheduled autonomous agent runs
The system SHALL let a user create a scheduled agent task with a name, a
natural-language instruction, a target workspace, an optional target document,
and a schedule (a cron-like expression) and/or a trigger. The system SHALL run
each enabled task autonomously in the background — with no live user present —
by invoking the existing agent tool-loop, SHALL write the run's result into a
document, and SHALL notify the task owner with a link to that document. Tasks
SHALL be listable, enable-able, and disable-able, and each SHALL expose its run
history.

#### Scenario: Create and schedule a task
- **GIVEN** an authenticated user in a workspace
- **WHEN** the user creates a task with an instruction, a target document, and a
  cron schedule
- **THEN** the system SHALL store the task with the creating user recorded as its
  owner and its tenant taken from the user's verified token
- **AND** the task SHALL appear in the user's task list as enabled with a
  computed next run time

#### Scenario: A due task runs without a live user
- **GIVEN** an enabled task whose next run time has arrived
- **WHEN** the scheduler evaluates due tasks
- **THEN** the system SHALL execute the task through the existing agent tool-loop
  with no live user token
- **AND** SHALL write the result into the task's target document through the CRDT
  attributed to the agent
- **AND** SHALL emit a notification to the task owner containing a link to that
  document

#### Scenario: A disabled task does not run
- **GIVEN** a task that has been disabled
- **WHEN** its scheduled time arrives
- **THEN** the system SHALL NOT execute it
- **AND** no run record SHALL be created for that occurrence

#### Scenario: A task is not double-run on a tick
- **GIVEN** a single due task and more than one scheduler evaluating due tasks
  concurrently
- **WHEN** they both attempt to claim the task on the same tick
- **THEN** the task SHALL be executed at most once
- **AND** the losing claimant SHALL skip the task

#### Scenario: Every run is audited
- **GIVEN** a background task execution
- **WHEN** the run finishes for any reason (success, failure, denied, or stopped)
- **THEN** the system SHALL write an audit record including the task id, the
  owner, the trigger, and the outcome

### Requirement: Background run safety limits
Because a background run has no user to confirm actions, the system SHALL disable
destructive tools (deleting a document or a block) in background mode unless the
task carries an explicit pre-approval, and SHALL enforce per-run limits on the
maximum number of tool rounds, maximum wall-clock time, and maximum number of
actions. On exceeding any limit the system SHALL stop the run and record which
limit was exceeded.

#### Scenario: Destructive tools are unavailable in background mode
- **GIVEN** a background run whose instruction would delete a block or document
- **WHEN** the agent attempts a destructive tool that is not pre-approved
- **THEN** the system SHALL NOT perform the deletion
- **AND** SHALL record the refusal in the run outcome

#### Scenario: A run that exceeds the tool-round limit is stopped
- **GIVEN** a background run configured with a maximum number of tool rounds
- **WHEN** the run reaches that number of rounds without completing
- **THEN** the system SHALL stop the run
- **AND** SHALL record the outcome as stopped for exceeding the round limit

#### Scenario: A run that exceeds the wall-clock limit is stopped
- **GIVEN** a background run configured with a maximum wall-clock time
- **WHEN** the run's elapsed time reaches that limit
- **THEN** the system SHALL stop the run
- **AND** SHALL record the outcome as stopped for exceeding the time limit

#### Scenario: A run that exceeds the action limit is stopped
- **GIVEN** a background run configured with a maximum number of actions
- **WHEN** the run performs that many actions without completing
- **THEN** the system SHALL stop the run
- **AND** SHALL record the outcome as stopped for exceeding the action limit

### Requirement: Owner-scoped background authorization
A background run SHALL be authorized from the task's stored owner, not from the
service identity used to authenticate outbound calls. The system SHALL execute
the run within the owner's tenant and SHALL evaluate the owner's current
document and workspace permissions at run time. The client-credentials service
token SHALL be used only as transport to sibling backends and SHALL NOT be
treated as the run's authority.

#### Scenario: Run acts within the owner's tenant and permissions
- **GIVEN** a task owned by a user in a given tenant
- **WHEN** the task runs in the background
- **THEN** the run SHALL operate strictly within that owner's tenant
- **AND** SHALL only access documents and workspaces the owner is permitted to
  access

#### Scenario: Run is denied when the owner has lost access
- **GIVEN** a task whose owner no longer has permission on the target document
- **WHEN** the task's scheduled time arrives and it runs
- **THEN** the system SHALL deny the run
- **AND** SHALL record the outcome as denied without writing to the document

#### Scenario: The service identity is never the authority
- **GIVEN** a background run authenticating to sibling backends with a
  client-credentials service token whose subject is the service client
- **WHEN** the system authorizes what the run may read or change
- **THEN** it SHALL derive authorization from the stored owner
- **AND** SHALL NOT grant the run any access based on the service identity
