/** ArcheProvider: binds a Y.Doc to the relay's WebSocket protocol.
 *
 * Frames (see backend adapters/inbound/http/realtime.py):
 *   binary 0x00 + update     CRDT update (server persists + fans out)
 *   binary 0x01 + payload    awareness/presence JSON (fanout only)
 *   text   JSON              control messages (errors, presence_left)
 *
 * Offline story: local edits keep applying to the Y.Doc. On (re)connect the
 * server sends its full state (merged in), and we push our full local state
 * back — CRDT semantics make the exchange convergent and idempotent; the
 * server's compaction keeps the log bounded.
 */

import * as Y from 'yjs';

export interface PresencePeer {
	user_id: string;
	block_id: string | null;
	color: string;
	seen_at: number;
}

export type ProviderStatus = 'connecting' | 'connected' | 'offline';

/** How the provider obtains a *current* access token.
 *
 * Access tokens are short-lived (15 min). Capturing one at construction and
 * reusing it forever means every reconnect after expiry is refused with 4401,
 * and the provider retries the dead token until the tab is closed. The
 * provider therefore reads the token afresh on each connect, and refreshes
 * once when the server rejects it. */
export interface TokenSource {
	getAccessToken(): string | null;
	tryRefresh(): Promise<boolean>;
}

const RECONNECT_DELAY_MS = 1500;
/** Cap on the exponential backoff between reconnect attempts. A backend deploy
 * or outage would otherwise spam a fixed-interval retry (~1 error/1.5s) into
 * the console; backoff keeps the tab reconnecting without the noise. */
const RECONNECT_MAX_MS = 20_000;
const PEER_TTL_MS = 30_000;
/** Server close codes (adapters/inbound/http/realtime.py). */
const CLOSE_UNAUTHENTICATED = 4401;
const CLOSE_FORBIDDEN = 4403;
/** Clock skew allowance when deciding a token is spent. */
const EXPIRY_SKEW_MS = 30_000;

/** True when the JWT is absent, unreadable, or past (exp - skew).
 *
 * Checked before every connect: the socket carries its token as a subprotocol,
 * so an expired one is refused at the handshake and — depending on the server —
 * may come back as an opaque failure rather than a close code. Refreshing first
 * keeps the reconnect on the happy path. */
export function isExpired(token: string | null): boolean {
	if (!token) return true;
	try {
		const payload = token.split('.')[1];
		const { exp } = JSON.parse(atob(payload.replace(/-/g, '+').replace(/_/g, '/')));
		if (typeof exp !== 'number') return false;
		return Date.now() >= exp * 1000 - EXPIRY_SKEW_MS;
	} catch {
		return false; // opaque token: let the server judge it
	}
}

export class ArcheProvider {
	readonly doc: Y.Doc;
	status: ProviderStatus = 'connecting';
	peers = new Map<string, PresencePeer>();

	onStatus: (status: ProviderStatus) => void = () => {};
	onPeers: (peers: PresencePeer[]) => void = () => {};
	onDenied: () => void = () => {};
	/** Fires once, after the server's initial state has been applied. */
	onSynced: () => void = () => {};
	private synced = false;

	private socket: WebSocket | null = null;
	private closed = false;
	private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
	/** Consecutive failed attempts, for exponential backoff. Reset when the
	 * server sends its first frame (a genuinely established connection). */
	private reconnectAttempts = 0;

	/** Set while a refresh-and-retry is in flight, so an expiry storm triggers
	 * exactly one refresh. */
	private refreshing = false;
	/** Set after a refresh, cleared once a socket actually opens. Stops a tight
	 * connect -> "still expired" -> refresh loop if the refresh hands back a
	 * token that is itself spent. */
	private refreshed = false;

	constructor(
		private readonly documentId: string,
		private readonly tokens: TokenSource,
		doc?: Y.Doc
	) {
		this.doc = doc ?? new Y.Doc();
		this.doc.on('update', this.handleLocalUpdate);
		this.connect();
	}

	private wsUrl(): string {
		const base = (import.meta.env.VITE_API_URL as string | undefined) ?? '';
		const origin = base || window.location.origin;
		// No token in the URL — it travels as a subprotocol (see connect()).
		return new URL(
			`/api/v1/documents/${this.documentId}/sync`,
			origin.replace(/^http/, 'ws')
		).toString();
	}

	private connect(): void {
		if (this.closed) return;
		// A spent token would be refused at the handshake; renew it first.
		if (isExpired(this.tokens.getAccessToken())) {
			if (this.refreshed) {
				// We already refreshed and the token is still spent: nothing
				// this client can do. Do not spin.
				this.setStatus('offline');
				this.onDenied();
				return;
			}
			this.refreshThenReconnect();
			return;
		}
		this.setStatus('connecting');
		// The token is sent as the second subprotocol ("bearer", <token>) so it
		// stays out of the URL/query string and access logs (audit F-012). The
		// server selects "bearer" and reads the token from the handshake.
		const socket = new WebSocket(this.wsUrl(), [
			'bearer',
			this.tokens.getAccessToken() ?? ''
		]);
		socket.binaryType = 'arraybuffer';
		this.socket = socket;

		socket.onopen = () => {
			// NOT proof of acceptance: the server accepts the handshake and then
			// closes with 4401/4403/4404 so the code reaches us. Only a frame
			// from the server proves the session is real (see handleMessage).
			this.setStatus('connected');
			// Push local state so offline edits merge on the server.
			const state = Y.encodeStateAsUpdate(this.doc);
			socket.send(concat(0x00, state));
		};
		socket.onmessage = (event) => this.handleMessage(event);
		socket.onclose = (event) => this.handleClose(event);
		socket.onerror = () => socket.close();
	}

	private handleClose(event: CloseEvent): void {
		this.socket = null;
		if (this.closed) return;
		this.setStatus('offline');

		if (event.code === CLOSE_FORBIDDEN) {
			this.onDenied(); // no role on this document — retrying cannot help
			return;
		}

		if (event.code === CLOSE_UNAUTHENTICATED) {
			// The access token expired mid-session. Refresh once, then retry
			// with the new one; reconnecting with the same token would loop.
			this.refreshThenReconnect();
			return;
		}

		// Anything else (including an unclean 1006 from a handshake the proxy
		// or an older server refused without a code) may still be a spent
		// token. Renew it if it looks expired; otherwise just back off — a
		// network blip must not sign the user out.
		if (isExpired(this.tokens.getAccessToken())) {
			this.refreshThenReconnect();
			return;
		}
		this.scheduleReconnect();
	}

	/** Reconnect after an exponentially backed-off delay (capped), so a backend
	 * deploy or outage doesn't spam a fixed-interval retry. */
	private scheduleReconnect(): void {
		const delay = Math.min(
			RECONNECT_DELAY_MS * 2 ** this.reconnectAttempts,
			RECONNECT_MAX_MS
		);
		this.reconnectAttempts += 1;
		this.reconnectTimer = setTimeout(() => this.connect(), delay);
	}

	/** Refresh once, then reconnect. Concurrent calls collapse into one. */
	private refreshThenReconnect(): void {
		if (this.refreshing) return;
		this.refreshing = true;
		this.setStatus('connecting');
		void this.tokens
			.tryRefresh()
			.then((ok) => {
				this.refreshing = false;
				if (this.closed) return;
				if (ok) {
					this.refreshed = true;
					this.connect();
					return;
				}
				// Refresh failed: the session is over. Retrying the dead token
				// would loop forever, which is what shipped.
				this.setStatus('offline');
				this.onDenied();
			})
			.catch(() => {
				this.refreshing = false;
				if (!this.closed) {
					this.reconnectTimer = setTimeout(() => this.connect(), RECONNECT_DELAY_MS);
				}
			});
	}

	private handleMessage(event: MessageEvent): void {
		// The server talks to us: the connection was genuinely accepted, so the
		// refresh cycle is over and a later failure may refresh again.
		this.refreshing = false;
		this.refreshed = false;
		this.reconnectAttempts = 0; // established: reset the backoff

		if (typeof event.data === 'string') {
			this.handleControl(JSON.parse(event.data));
			return;
		}
		const frame = new Uint8Array(event.data as ArrayBuffer);
		if (frame.length === 0) return;
		const payload = frame.slice(1);
		if (frame[0] === 0x00) {
			Y.applyUpdate(this.doc, payload, 'remote');
			if (!this.synced) {
				this.synced = true;
				this.onSynced();
			}
		} else if (frame[0] === 0x01) {
			this.handleAwareness(JSON.parse(new TextDecoder().decode(payload)));
		}
	}

	private handleControl(message: { type?: string; error?: string; user_id?: string }): void {
		if (message.type === 'presence_left' && message.user_id) {
			this.peers.delete(message.user_id);
			this.emitPeers();
		}
		if (message.type === 'error' && message.error === 'NotAuthorized') {
			this.onDenied();
		}
	}

	private handleAwareness(peer: { user_id: string; block_id: string | null; color: string }): void {
		this.peers.set(peer.user_id, { ...peer, seen_at: Date.now() });
		for (const [id, existing] of this.peers) {
			if (Date.now() - existing.seen_at > PEER_TTL_MS) this.peers.delete(id);
		}
		this.emitPeers();
	}

	private handleLocalUpdate = (update: Uint8Array, origin: unknown): void => {
		if (origin === 'remote') return; // don't echo server frames back
		if (this.socket?.readyState === WebSocket.OPEN) {
			this.socket.send(concat(0x00, update));
		}
		// Offline: nothing to do — the full state syncs on reconnect.
	};

	broadcastPresence(blockId: string | null, userId: string, color: string): void {
		if (this.socket?.readyState !== WebSocket.OPEN) return;
		const payload = new TextEncoder().encode(
			JSON.stringify({ user_id: userId, block_id: blockId, color })
		);
		this.socket.send(concat(0x01, payload));
	}

	private setStatus(status: ProviderStatus): void {
		this.status = status;
		this.onStatus(status);
	}

	private emitPeers(): void {
		this.onPeers([...this.peers.values()]);
	}

	destroy(): void {
		this.closed = true;
		if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
		this.doc.off('update', this.handleLocalUpdate);
		this.socket?.close();
	}
}

function concat(kind: number, payload: Uint8Array): Uint8Array {
	const frame = new Uint8Array(payload.length + 1);
	frame[0] = kind;
	frame.set(payload, 1);
	return frame;
}
