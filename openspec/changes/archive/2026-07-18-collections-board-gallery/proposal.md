# Collections — Board and Gallery views

## Why

Collections render only as a Table today. The Board (kanban) and Gallery views
are the next two of the four planned view kinds; the view model already has the
kinds and a `group_by` field, so this is frontend rendering plus the ability to
add a view of a chosen kind.

## What Changes

- Board view: rows grouped into columns by a chosen single-select property
  (`group_by`), with an "Uncategorized" column for empty values; each card shows
  the row title and its properties; moving a card to another column sets that
  row's property value. Members choose the group-by property.
- Gallery view: rows as a responsive grid of cards (title + properties).
- The view switcher can add a view of any kind and pick the Board group-by
  property; all views honor the active filters/sorts.

## Impact

- Affected specs: `collections`.
- Affected code: frontend only — Board and Gallery components, the view switcher
  (add view of a kind, pick group-by), and small VM helpers (group rows, set a
  row's group value, create/select views). Backend already supports it.
