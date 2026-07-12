# Design — Database block

## Storage

A database is CRDT-native, matching the whiteboard block:
- Rows live in a document-level `Y.Map` keyed `db:<blockId>`, one entry per row
  id → the row record (a plain object of `propertyId -> value`). Per-row entries
  let concurrent edits to *different* rows merge; same-row edits are LWW.
- The schema (ordered list of properties) is stored under the reserved key
  `__schema` in that same map (whole-value LWW — schema changes are rare).
- A debounced mirror writes `{ properties, rows }` into the block's `data` so the
  backend snapshot, the agent's context, and export see the current state (the
  same mirror pattern the whiteboard uses).

## Model

- Property: `{ id, name, type, options? }` where `type ∈ text|number|select|
  checkbox|date`; `options` is a list of `{ id, name, color }` for `select`.
- Row: `{ id, values: { [propertyId]: string|number|boolean|null } }`.

## View-model (`createDatabase(doc, blockId, opts)`)

Pure operations, unit-testable, mutating the `Y.Map` in transactions:
`addProperty`, `removeProperty`, `renameProperty`, `setPropertyType`,
`addOption`, `addRow`, `removeRow`, `setCell`, `sortBy(propertyId, dir)`,
`groupBy(propertyId)` → groups rows by a select value for the board, and
`moveRow(rowId, optionId)` (board drag) sets that row's select value.

## Views

- **Table**: header cells (name + type menu + add-column), body rows of typed
  cell editors (text input, number input, select dropdown, checkbox, date
  input), add-row footer, per-column sort toggle.
- **Board**: pick a select property to group by; a column per option (plus "No
  value"); cards show the row's title/text; drag a card to another column to set
  its value; add a card to a column (a new row with that value).

## Non-goals (this change)

Filters, calendar/gallery/list views, relations/rollups, rows-as-pages, and
formula/person types are out of scope; the schema/data shape leaves room for
them.
