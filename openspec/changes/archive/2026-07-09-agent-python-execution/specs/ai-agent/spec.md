# ai-agent Specification

## ADDED Requirements
### Requirement: Agent runs Python
When code execution is configured, the agent SHALL offer a tool that runs Python
to compute, analyze data, run simulations, or plot. Figures the code produces
SHALL be stored and inserted into the open document as image blocks (a CRDT peer
edit), and the standard output, result value, and any error SHALL be returned to
the agent so it can explain them. The caller SHALL need edit permission on the
document. When code execution is not configured, the tool SHALL report it is
unavailable rather than failing the run.

#### Scenario: Agent plots and inserts a figure
- **GIVEN** code execution is configured and the caller may edit the document
- **WHEN** the agent runs Python that creates a plot
- **THEN** the figure SHALL be inserted into the document as an image block
- **AND** the run's stdout and result SHALL be available to the agent

#### Scenario: Code execution not configured
- **WHEN** the agent calls the Python tool but no interpreter is configured
- **THEN** the tool SHALL report that code execution is unavailable
- **AND** the run SHALL continue without error
