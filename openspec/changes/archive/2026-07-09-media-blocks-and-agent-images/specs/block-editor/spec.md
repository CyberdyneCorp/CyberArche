# block-editor Specification

## ADDED Requirements
### Requirement: Image blocks
The editor SHALL provide an image block that renders an image from a URL. An
empty image block SHALL let the user either paste an image URL or upload an image
file; an uploaded image SHALL be stored and referenced by its served URL rather
than embedded in the document. The block SHALL support alt text.

#### Scenario: Render an image from a URL
- **WHEN** a user sets an image block's URL to an image address
- **THEN** the block SHALL display that image

#### Scenario: Upload an image into a block
- **WHEN** a user uploads an image into an empty image block
- **THEN** the image SHALL be stored and the block SHALL display it by its
  served URL

### Requirement: Embed blocks
The editor SHALL provide an embed block that renders a media URL. YouTube,
Vimeo, and Loom links SHALL render as embedded players; any other `https` URL
SHALL render in a sandboxed iframe with a fallback link to open it directly.
Non-`https` URLs SHALL NOT be embedded.

#### Scenario: Embed a YouTube video
- **WHEN** a user sets an embed block's URL to a YouTube link
- **THEN** the block SHALL render the YouTube player for that video

#### Scenario: Embed an arbitrary https page
- **WHEN** a user sets an embed block's URL to an https URL that is not a known
  provider
- **THEN** the block SHALL render it in a sandboxed iframe with a link to open it

#### Scenario: Refuse a non-https URL
- **WHEN** a user sets an embed block's URL to a non-`https` URL
- **THEN** the block SHALL NOT embed it
