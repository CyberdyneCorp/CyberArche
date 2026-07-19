# Tasks
- [ ] 1.1 Domain markdown→blocks converter (fences first, then line blocks + GFM tables); tests
- [ ] 1.2 FileExtractor: .md/.markdown via the converter; add .docx (python-docx) → blocks
- [ ] 1.3 ImportUseCases: single file → one private document (title from first H1/filename); Notion .zip → a document per .md with folder nesting + id-suffix stripping
- [ ] 1.4 Router POST /workspaces/{id}/import (multipart); wiring
- [ ] 1.5 Frontend: import API client + a sidebar Import trigger; open the created (first) document
- [ ] 1.6 Tests: markdown blocks, docx extraction, single + zip import, private placement, access; frontend
- [ ] 1.7 `openspec validate document-import --strict`; gates green
