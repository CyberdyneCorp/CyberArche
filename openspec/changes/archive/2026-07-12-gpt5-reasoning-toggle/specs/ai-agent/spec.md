# ai-agent Specification

## ADDED Requirements

### Requirement: Per-request reasoning effort

The chat window SHALL let the user toggle reasoning for a message. When enabled,
the agent SHALL request deeper reasoning from the model; when disabled, it SHALL
request minimal reasoning for a fast, cheap response. The reasoning setting SHALL
apply to that request's model calls, and SHALL be a no-op for models that do not
support reasoning effort (so it never breaks a non-reasoning model).

#### Scenario: Reasoning on requests deeper thinking

- **WHEN** the user sends a message with the reasoning toggle on
- **THEN** the agent SHALL call the model with a higher reasoning effort

#### Scenario: Reasoning off is fast

- **WHEN** the user sends a message with the reasoning toggle off
- **THEN** the agent SHALL call the model with minimal reasoning effort

### Requirement: Forward-compatible token limit

The OpenAI-compatible adapter SHALL cap responses using `max_completion_tokens`
so that reasoning models (GPT-5 family, o-series), which reject the legacy
`max_tokens` field, are supported alongside earlier models.

#### Scenario: A reasoning model is callable

- **WHEN** the configured model is a GPT-5 / o-series model
- **THEN** a completion request SHALL succeed rather than being rejected for an
  unsupported token field
