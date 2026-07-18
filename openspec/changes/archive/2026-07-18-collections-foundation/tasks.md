# Tasks
- [ ] 1.1 Domain: PropertyType/PropertyDef, ViewKind/View/Filter/Sort, Collection; add collection_id + properties to Document; pure apply_view(rows, view)
- [ ] 1.2 Ports + in-memory + postgres repos: CollectionRepository; DocumentRepository.list_by_collection + persist collection_id/properties; migration 0020
- [ ] 1.3 CollectionUseCases: collection CRUD, property-schema edits, view CRUD, row ops (compose DocumentUseCases for rows), query_view — access-scoped
- [ ] 1.4 REST router + wiring + UseCases assembly + conftest fixture
- [ ] 1.5 Frontend: collections API client + VM; sidebar create/list; collection route with editable Table view (typed cells, add row, add property, open row)
- [ ] 1.6 Tests: use cases + repos (both backends) + apply_view; frontend api/VM/table
- [ ] 1.7 `openspec validate collections-foundation --strict`; gates green
