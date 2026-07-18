# Collections — interactive filter & sort controls

## Why

The collection model already stores per-view filters and sorts and `apply_view`
applies them, but there is no UI to edit them — a view is stuck with whatever it
was created with. This adds the filter/sort controls to the collection surface so
members can shape any view.

## What Changes

- A filter builder on the collection toolbar: add/remove filter rules (property,
  operator, value) whose operators adapt to the property type; changes persist to
  the current view (update_view) and re-query.
- A sort builder: add/remove/reorder sort rules (property, asc/desc), persisted
  the same way.
- An empty/active-count affordance so it's clear when a view is filtered/sorted.

## Impact

- Affected specs: `collections`.
- Affected code: frontend only — the collection VM (filter/sort editing +
  re-query) and the collection toolbar components. Backend + `apply_view` already
  support this; no schema or endpoint changes.
