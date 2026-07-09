# code-execution Specification

## Purpose
TBD - created by archiving change agent-python-execution. Update Purpose after archive.
## Requirements
### Requirement: Execute Python and capture its outputs
The system SHALL provide a code-execution capability that runs Python source in a
sandboxed session and returns whether it succeeded, its standard output and
error, the result value, any error detail, the images it produced (e.g.
matplotlib figures, as bytes), and any tabular/text rich outputs (e.g. DataFrame
HTML). When code plots with matplotlib but does not save the figures, the system
SHALL capture the open figures so they are returned as images.

#### Scenario: Code returns stdout and a result
- **WHEN** Python that prints and evaluates a value is executed
- **THEN** the captured stdout and result value SHALL be returned

#### Scenario: A plot is captured as an image
- **WHEN** Python creates a matplotlib figure without saving it
- **THEN** the figure SHALL be returned as image bytes

#### Scenario: A failure is reported, not raised
- **WHEN** the executed code raises an error
- **THEN** the result SHALL report failure with the error detail, without
  crashing the caller

