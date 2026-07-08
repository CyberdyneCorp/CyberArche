# Realtime refusals must tell the client why

## Why

The realtime endpoint closed the WebSocket **before** `accept()`. Starlette
turns that into an HTTP 403 handshake denial, and the application close code is
discarded: the browser only reports a generic failure (`1006`).

A client therefore cannot distinguish:

- an expired access token — refresh and retry, or
- a forbidden document — stop.

So it retried the dead token forever. Observed in production as an endless
`WebSocket connection failed` loop after a tab sat open past the 15-minute
access-token lifetime.

The `realtime-collaboration` capability already requires the client to "refresh
its token at most once and retry" when refused as unauthenticated. That
requirement is unimplementable against a server that never says why.

Verified with a real WebSocket client: a rejected connection returns
`HTTP 403` at the handshake, no close code.

## What Changes

- The realtime endpoint accepts the handshake and *then* closes with the
  application code (4401 / 4403 / 4404), so the reason reaches the client.
- The client stops treating `onopen` as proof of acceptance — with
  accept-then-close, `onopen` fires for refused sockets too. Only a frame from
  the server ends the refresh cycle.
- The client renews a token it can see is spent *before* connecting, and
  recovers from an opaque `1006` when its token has expired, while treating a
  `1006` with a healthy token as a network blip (back off, do not sign out).

## Non-goals

- Changing token lifetimes or the refresh protocol.
- Reconnect/backoff policy beyond the auth cases.

## Impact

- `realtime-collaboration`: refusal reasons become part of the contract.
- Backend WebSocket tests assert close codes instead of "some exception" —
  they previously could not tell 4401 from 4403.
