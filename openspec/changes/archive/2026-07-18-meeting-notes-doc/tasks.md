# Tasks
- [ ] 1.1 `MeetingNotesUseCases.create_from_recording` — transcript → tool-free LLM structure → create doc → insert blocks
- [ ] 1.2 Endpoints: `GET /api/v1/meetings`; `POST /api/v1/workspaces/{id}/meeting-notes`
- [ ] 1.3 Wiring: build the use case (meetings, llm, documents, agent, ids); register router
- [ ] 1.4 Frontend: meetings API client, meeting-notes modal + store + trigger; open the created doc
- [ ] 1.5 Tests: structure+create+insert flow, access enforced, meetings-not-configured / no-token errors, list; frontend flow
- [ ] 1.6 `openspec validate meeting-notes-doc --strict`; gates green
