# Tasks
- [ ] 1.1 Domain: PropertyType.RELATION/ROLLUP; relation_collection_id + rollup config on PropertyDef; pure rollup aggregation (count/sum/average/min/max/earliest/latest/list)
- [ ] 1.2 Use case: validate relation target + coerce relation values to valid linked-row ids; validate rollup config; reject rollup writes; compute rollups in query_view (batch-load linked rows); resolve linked titles
- [ ] 1.3 Router: rows response carries linked {id,title}; add-property/update carry relation/rollup config; GET collection rows (id+title) for the picker
- [ ] 1.4 Postgres (de)serialization of the new PropertyDef fields
- [ ] 1.5 Frontend: relation cell (chips + row picker over the target collection), read-only rollup cell, add-property UI for relation (pick target) and rollup (relation + target property + function)
- [ ] 1.6 Tests: aggregation functions; relation coercion/validation; rollup compute in query_view; linked-title resolution; writes rejected on rollup; postgres round-trip; frontend
- [ ] 1.7 `openspec validate collections-relations-rollups --strict`; gates green
