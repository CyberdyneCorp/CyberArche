# collections Specification

## ADDED Requirements

### Requirement: Board view

A collection SHALL offer a Board (kanban) view that groups its rows into columns
by a chosen single-select property. There SHALL be a column per option of that
property plus a column for rows with no value. Each card SHALL show the row's
title and its property values. Moving a card to another column SHALL set the
row's grouping property to that column's value. The Board view SHALL honor the
view's active filters and sorts.

#### Scenario: Group rows on a board

- **GIVEN** a collection with a single-select property and rows
- **WHEN** a member views it as a Board grouped by that property
- **THEN** rows SHALL appear in the column matching their value, and rows with no
  value SHALL appear in the uncategorized column

#### Scenario: Move a card

- **WHEN** a member moves a card to another column
- **THEN** the row's grouping property SHALL be set to that column's value

### Requirement: Gallery view

A collection SHALL offer a Gallery view that presents its rows as a grid of
cards, each showing the row's title and property values, honoring the view's
active filters and sorts.

#### Scenario: Show rows as a gallery

- **GIVEN** a collection with rows
- **WHEN** a member views it as a Gallery
- **THEN** the rows SHALL be presented as a grid of cards
