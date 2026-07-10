# ai-agent Specification

## ADDED Requirements
### Requirement: Agent uses recent conversation history
The agent SHALL accept recent conversation turns with a request and take them
into account, so a follow-up instruction that refers to the prior exchange (e.g.
"insert the plot", "run that code") resolves against the conversation rather than
only the document. The amount of history included MAY be bounded.

#### Scenario: A follow-up resolves against the prior turn
- **GIVEN** the user asked the agent to create a plot and got a reply
- **WHEN** the user then says "insert the plot"
- **THEN** the agent SHALL interpret "the plot" as the one from the prior turn

#### Scenario: History is optional
- **WHEN** a request is made with no prior turns
- **THEN** the agent SHALL answer from the document and instruction alone
