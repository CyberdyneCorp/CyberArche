# Design

## D-1: Accept, then close

An application close code (>= 3000) only reaches a client after a successful
handshake. Closing before `accept()` yields `HTTP 403` and the code is lost.
So the endpoint accepts and immediately closes with the reason.

This leaks nothing: the socket is closed before any document state is sent, and
authorization is still decided before `accept()`. The only change is that the
client learns *why* it was refused.

## D-2: `onopen` is not acceptance

The direct consequence of D-1: a refused socket still fires `onopen` in the
browser. A client that treats `onopen` as success will reset its
refresh-attempt bookkeeping and can spin (refresh -> open -> 4401 -> refresh).

The provider therefore ends its refresh cycle on the first *frame* from the
server, which only an accepted session ever sends.

## D-3: Prefer prevention to recovery

The token travels in the socket URL, so an expired one is refused at the
handshake. The provider checks `exp` (minus 30s skew) before connecting and
renews first. Opaque, non-JWT credentials (API keys) are never judged locally —
the server decides.

## D-4: An unclean 1006 is ambiguous

`1006` means the browser never saw a code: a proxy, an older server, or a
dropped network. Refreshing on every `1006` would sign a user out on a blip,
because a failed refresh clears the session. So `1006` triggers a refresh only
when the token is demonstrably expired; otherwise the provider backs off and
reconnects.
