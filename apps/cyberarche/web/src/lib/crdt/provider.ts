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
const PEER_TTL_MS = 30_000;
/** Server close codes (adapters/inbound/http/realtime.py). */
const CLOSE_UNAUTHENTICATED = 4401;
const CLOSE_FORBIDDEN = 4403;

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

	/** Set while a refresh-and-retry is in flight, so an expiry storm triggers
	 * exactly one refresh. */
	private refreshing = false;

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
		const url = new URL(
			`/api/v1/documents/${this.documentId}/sync`,
			origin.replace(/^http/, 'ws')
		);
		url.searchParams.set('token', this.tokens.getAccessToken() ?? '');
		return url.toString();
	}

	private connect(): void {
		if (this.closed) return;
		this.setStatus('connecting');
		const socket = new WebSocket(this.wsUrl());
		socket.binaryType = 'arraybuffer';
		this.socket = socket;

		socket.onopen = () => {
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
			if (this.refreshing) return;
			this.refreshing = true;
			void this.tokens
				.tryRefresh()
				.then((ok) => {
					this.refreshing = false;
					if (this.closed) return;
					if (ok) this.connect();
					else this.onDenied(); // signed out; the app routes to /signin
				})
				.catch(() => {
					this.refreshing = false;
				});
			return;
		}

		this.reconnectTimer = setTimeout(() => this.connect(), RECONNECT_DELAY_MS);
	}

	private handleMessage(event: MessageEvent): void {
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
