# document-export Specification

## ADDED Requirements

### Requirement: Export a teamspace or folder as a ZIP

The web app SHALL let a user export a teamspace or folder from its context menu,
downloading a ZIP that contains one Markdown file per document in that scope,
plus the documents' images as separate binary files under an `assets/` folder,
referenced from the Markdown by relative path. Only documents the caller may view
SHALL be included.

#### Scenario: Download a teamspace as a ZIP

- **WHEN** the user right-clicks a teamspace and chooses "Export (ZIP)"
- **THEN** a ZIP SHALL download containing a Markdown file for each of its
  documents
- **AND** the documents' images SHALL be included as separate files under
  `assets/`, referenced from the Markdown by relative path
