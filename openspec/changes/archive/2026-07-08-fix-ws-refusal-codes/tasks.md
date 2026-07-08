# Tasks

- [x] 1.1 Accept the handshake before closing, so 4401/4403/4404 reach the client
- [x] 1.2 Backend tests assert the close code (previously only "it raised")
- [x] 1.3 Client: end the refresh cycle on the first server frame, not on `onopen`
- [x] 1.4 Client: renew a demonstrably expired token before connecting
- [x] 1.5 Client: refresh on an unclean 1006 only when the token is expired
- [x] 1.6 Vitest for the provider's token lifecycle; e2e asserting the code a real browser observes
