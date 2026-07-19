# Tasks
- [ ] 1.1 FileExtractor.extract_table (csv + xlsx → header, rows)
- [ ] 1.2 ImportUseCases: import_spreadsheet (collection from sheet: col0=title, rest=typed properties incl. number inference; doc embeds a collection_view block); route .csv/.xlsx → it, .pdf → import_file; cap rows
- [ ] 1.3 Wiring: give ImportUseCases the CollectionUseCases dependency
- [ ] 1.4 Frontend: add .pdf/.csv/.xlsx to the accept list + update the import label/tooltip
- [ ] 1.5 Tests: extract_table, spreadsheet→collection (schema/rows/title, number inference, embedded block), pdf→doc, dispatch, access; frontend
- [ ] 1.6 `openspec validate import-pdf-spreadsheet --strict`; gates green
