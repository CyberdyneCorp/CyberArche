# Tasks
- [ ] 1.1 Domain: PropertyType.FORMULA + PropertyDef.formula; a safe pure evaluator (whitelisted AST, prop()/now()/functions) + evaluate_row helper
- [ ] 1.2 Use case: validate formula on add/update; reject setting a formula value; compute formulas in query_view (enrich rows before apply_view)
- [ ] 1.3 Postgres property (de)serialization includes formula; in-memory unaffected
- [ ] 1.4 Frontend: formula in the add/edit-property UI; read-only formula cell showing the computed value
- [ ] 1.5 Tests: evaluator (arithmetic/if/now/prop/functions + rejects unsafe input), compute-in-query, filter/sort on a formula column, write rejected, bad-expression rejected; frontend
- [ ] 1.6 `openspec validate collections-formula --strict`; gates green
