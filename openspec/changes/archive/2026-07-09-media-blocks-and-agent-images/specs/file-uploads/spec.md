# file-uploads Specification

## ADDED Requirements
### Requirement: Upload an image to a workspace
The system SHALL let a workspace editor upload an image file, store it, and
return a stable URL that renders it. The upload SHALL be rejected when the file
exceeds a maximum size or is not a supported raster image. Supported types SHALL
be PNG, JPEG, GIF, and WebP, determined by inspecting the file's content
(magic bytes) rather than trusting the declared content type; SVG and other
types SHALL be rejected to avoid script-bearing uploads.

#### Scenario: Upload a valid image
- **WHEN** an editor uploads a PNG within the size limit
- **THEN** the system SHALL store it and return a URL that serves the image

#### Scenario: Reject an oversized file
- **WHEN** a file larger than the maximum allowed size is uploaded
- **THEN** the system SHALL reject it and store nothing

#### Scenario: Reject a non-image or disguised file
- **WHEN** a file whose content is not a supported raster image is uploaded
- **THEN** the system SHALL reject it, even if its declared content type claims
  to be an image

### Requirement: Serve an uploaded file to workspace members
The system SHALL serve a stored file's bytes with its content type to callers
who can access the workspace, and SHALL deny callers who cannot.

#### Scenario: A member loads an uploaded image
- **GIVEN** an image was uploaded to a workspace
- **WHEN** a member of that workspace requests its URL
- **THEN** the system SHALL return the image bytes with the correct content type

#### Scenario: A non-member is denied
- **WHEN** a caller who is not a member of the workspace requests the file
- **THEN** the system SHALL deny the request
