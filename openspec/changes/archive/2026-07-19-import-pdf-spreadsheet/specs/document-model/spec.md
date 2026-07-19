# document-model Specification

## MODIFIED Requirements

### Requirement: Import documents from files

The system SHALL let a member import external content into a workspace as
documents. It SHALL accept a Markdown, plain-text, Word (`.docx`), or PDF file
and create one private document from it, converting the content into editable
blocks and titling the document from its first heading or the file name. It SHALL
accept a CSV or Excel (`.xlsx`) file and import the sheet as a new collection:
the first column SHALL become each row's title and the remaining columns SHALL
become typed properties (a column whose values are all numeric SHALL be a number
property), and a new document SHALL embed a view of that collection. It SHALL
accept a Notion `.zip` export and create one document per Markdown file it
contains, preserving folder nesting as parent documents and removing the
identifier suffixes Notion appends to names. Markdown conversion SHALL map
headings, bullet and numbered lists, to-dos, quotes, code and diagram fences,
tables, dividers, and images to their corresponding blocks. Importing SHALL
require edit access to the workspace and SHALL be scoped to the caller's tenant.

#### Scenario: Import a Markdown file

- **GIVEN** a member with edit access to a workspace
- **WHEN** they import a Markdown file
- **THEN** the system SHALL create a private document whose blocks reflect the
  file's headings, lists, and tables
- **AND** SHALL return the document so it can be opened

#### Scenario: Import a spreadsheet as a database

- **GIVEN** a member with edit access to a workspace
- **WHEN** they import a CSV or Excel file
- **THEN** the system SHALL create a collection whose rows come from the sheet's
  rows and whose properties come from its columns
- **AND** SHALL create a document that embeds a view of that collection

#### Scenario: Import a Notion export

- **WHEN** a member imports a Notion `.zip` export with nested pages
- **THEN** the system SHALL create a document per page, nested to match the
  export's folder structure

#### Scenario: Access required

- **WHEN** a caller without edit access to the workspace imports a file
- **THEN** the system SHALL refuse the import
