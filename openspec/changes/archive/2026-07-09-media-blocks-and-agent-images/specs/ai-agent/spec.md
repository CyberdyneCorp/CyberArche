# ai-agent Specification

## ADDED Requirements
### Requirement: Agent generates images
When image generation is configured, the agent SHALL offer a tool that creates
an image from a text prompt, stores it, and inserts an image block into the open
document as a CRDT peer (attributed like other agent edits). The caller SHALL
need edit permission on the document. When image generation is not configured,
the tool SHALL report that it is unavailable rather than failing the run.

#### Scenario: Agent creates and inserts an image
- **GIVEN** image generation is configured and the caller may edit the document
- **WHEN** the agent calls the image tool with a prompt
- **THEN** an image SHALL be generated, stored, and inserted as an image block in
  the open document

#### Scenario: Image generation not configured
- **WHEN** the agent calls the image tool but no image provider is configured
- **THEN** the tool SHALL report that image generation is unavailable
- **AND** the run SHALL continue without error
