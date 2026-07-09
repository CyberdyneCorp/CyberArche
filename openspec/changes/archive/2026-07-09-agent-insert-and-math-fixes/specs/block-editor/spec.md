# block-editor Specification

## MODIFIED Requirements

### Requirement: LaTeX math blocks
The editor SHALL support LaTeX for both inline math (delimited by `$…$` or by
the TeX delimiters `\(…\)` and `\[…\]` within text) and block-level math (the
`latex` block), rendering both via KaTeX. It SHALL preserve the raw source for
editing and show a non-destructive error on invalid LaTeX.

#### Scenario: Render a block equation
- **WHEN** a user enters a valid LaTeX expression in a `latex` block
- **THEN** the editor SHALL render the typeset equation
- **AND** SHALL preserve the raw LaTeX source for editing

#### Scenario: Render inline math within text
- **WHEN** a paragraph contains a `$…$` fragment and is not being edited
- **THEN** the editor SHALL render that fragment as typeset inline math
- **AND** SHALL restore the raw `$…$` source when the paragraph is focused

#### Scenario: Render TeX-delimited inline math
- **WHEN** a paragraph contains `\(…\)` or `\[…\]` and is not being edited
- **THEN** the editor SHALL render that fragment as typeset inline math

#### Scenario: Invalid LaTeX
- **WHEN** a user enters LaTeX that fails to parse
- **THEN** the editor SHALL show an inline error without losing the source
