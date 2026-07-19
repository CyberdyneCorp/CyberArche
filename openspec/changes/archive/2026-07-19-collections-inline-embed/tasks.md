# Tasks
- [ ] 1.1 Domain: add `collection_view` to BLOCK_TYPES
- [ ] 1.2 CollectionViewBlock component: self-initialize a collection when absent (persist {collection_id, view_id} via updateData); render the collection views inline reusing CollectionTable/board/gallery/calendar; respect read-only
- [ ] 1.3 Block registry: register `collection_view` ("Database"); hide the legacy `database` from the slash menu but keep rendering it
- [ ] 1.4 Tests: block self-init creates + persists a collection; renders the view; legacy still renders + is not offered; slash menu lists the new one
- [ ] 1.5 `openspec validate collections-inline-embed --strict`; gates green
