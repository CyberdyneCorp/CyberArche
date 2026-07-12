# Page templates

## Why

Users recreate the same document structures (meeting notes, specs, checklists)
by hand. Saving a document as a reusable template and creating new documents
from it is a small, high-utility win.

## What Changes

- Add a **templates** capability: a workspace has named page templates, each
  capturing a document's block content at save time.
- **Save as template**: from a document, save its current blocks as a named
  template in the workspace.
- **New from template**: create a new document pre-filled with a template's
  blocks (fresh block ids), placed in a chosen teamspace (or private).
- List and delete a workspace's templates.

## Impact

- New capability spec: `templates`.
- Data model: new `templates` table (migration `0011_templates.sql`).
- Affected code: `Template` domain + `TemplateRepository` (in-memory + Postgres)
  + `TemplateUseCases` (save from document, instantiate, list, delete); a
  templates router; wiring. Web: `api/templates`, a "Save as template" action on
  the document page, and a "New from template" picker in the sidebar.
- Access: only workspace members may list/use templates; saving/instantiating
  needs edit rights; deleting needs the creator or a workspace owner.
