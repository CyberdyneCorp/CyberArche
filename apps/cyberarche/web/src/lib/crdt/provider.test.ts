import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import * as Y from 'yjs';

import { ArcheProvider, isExpired, type PresencePeer } from './provider';

/** A WebSocket whose lifecycle the test drives by hand. */
class FakeSocket {
	static CONNECTING = 0;
	static OPEN = 1;
	static CLOSED = 3;
	static instances: FakeSocket[] = [];
	onopen: (() => void) | null = null;
	onmessage: ((event: MessageEvent) => void) | null = null;
	onclose: ((event: CloseEvent) => void) | null = null;
	onerror: (() => void) | null = null;
	binaryType = '';
	readyState = FakeSocket.CONNECTING;
	sent: unknown[] = [];
	closedByClient = false;

	readonly protocols: string[];
	constructor(
		readonly url: string,
		protocols?: string | string[]
	) {
		this.protocols = protocols == null ? [] : Array.isArray(protocols) ? protocols : [protocols];
		FakeSocket.instances.push(this);
	}
	send(data: unknown) {
		this.sent.push(data);
	}
	close() {
		this.closedByClient = true;
	}

	/** The server refuses with an application close code (accept-then-close). */
	serverClose(code: number) {
		this.readyState = FakeSocket.CLOSED;
		this.onclose?.({ code } as CloseEvent);
	}
	/** The handshake itself failed: browsers report an unclean 1006. */
	handshakeFailed() {
		this.readyState = FakeSocket.CLOSED;
		this.onclose?.({ code: 1006 } as CloseEvent);
	}
	open() {
		this.readyState = FakeSocket.OPEN;
		this.onopen?.();
	}
	message(data: unknown) {
		this.onmessage?.({ data } as MessageEvent);
	}
}

/** A binary relay frame: kind byte + payload, as an ArrayBuffer. */
function frame(kind: number, payload: Uint8Array): ArrayBuffer {
	const buffer = new Uint8Array(payload.length + 1);
	buffer[0] = kind;
	buffer.set(payload, 1);
	return buffer.buffer;
}

function awarenessFrame(peer: { user_id: string; block_id: string | null; color: string }) {
	return frame(0x01, new TextEncoder().encode(JSON.stringify(peer)));
}

/** A JWT whose `exp` we control. Only the payload is ever read. */
function jwt(secondsFromNow: number): string {
	const payload = { exp: Math.floor(Date.now() / 1000) + secondsFromNow };
	return `h.${btoa(JSON.stringify(payload))}.s`;
}

function tokenOf(socket: FakeSocket): string {
	// The token travels as the second subprotocol ("bearer", <token>) — never in
	// the URL (F-012).
	return socket.protocols[0] === 'bearer' ? (socket.protocols[1] ?? '') : '';
}

const LIVE = jwt(3600);
const SPENT = jwt(-60);

beforeEach(() => {
	FakeSocket.instances = [];
	vi.stubGlobal('WebSocket', FakeSocket as unknown as typeof WebSocket);
	vi.stubGlobal('window', { location: { origin: 'http://localhost' } });
});

describe('isExpired', () => {
	it('treats a missing or past-due token as spent, a live one as usable', () => {
		expect(isExpired(null)).toBe(true);
		expect(isExpired(SPENT)).toBe(true);
		expect(isExpired(LIVE)).toBe(false);
	});

	it('treats a token expiring inside the skew window as spent', () => {
		expect(isExpired(jwt(10))).toBe(true);
		expect(isExpired(jwt(120))).toBe(false);
	});

	it('lets the server judge an opaque (non-JWT) token', () => {
		expect(isExpired('cak_some_api_key')).toBe(false);
	});
});

describe('ArcheProvider token lifecycle', () => {
	it('sends the token as a subprotocol, never in the URL (F-012)', async () => {
		const provider = new ArcheProvider('doc-1', {
			getAccessToken: () => LIVE,
			tryRefresh: vi.fn(async () => true)
		});
		await vi.waitFor(() => expect(FakeSocket.instances).toHaveLength(1));
		const socket = FakeSocket.instances[0];
		expect(socket.url).not.toContain('token');
		expect(socket.url).not.toContain(LIVE);
		expect(socket.protocols).toEqual(['bearer', LIVE]);
		provider.destroy();
	});

	it('refreshes BEFORE connecting when the token is already spent', async () => {
		// The socket carries its token as a subprotocol, so connecting with a spent
		// one is refused at the handshake — where the close code was historically
		// lost, and the client retried the dead token forever.
		let token = SPENT;
		const tokens = {
			getAccessToken: () => token,
			tryRefresh: vi.fn(async () => {
				token = LIVE;
				return true;
			})
		};
		const provider = new ArcheProvider('doc-1', tokens);

		await vi.waitFor(() => expect(FakeSocket.instances).toHaveLength(1));
		expect(tokens.tryRefresh).toHaveBeenCalledTimes(1);
		expect(tokenOf(FakeSocket.instances[0])).toBe(LIVE); // never the spent one
		provider.destroy();
	});

	it('reconnects with a refreshed token after a 4401', async () => {
		let token = LIVE;
		const tokens = {
			getAccessToken: () => token,
			tryRefresh: vi.fn(async () => {
				token = jwt(7200);
				return true;
			})
		};
		const provider = new ArcheProvider('doc-1', tokens);
		const first = tokenOf(FakeSocket.instances[0]);

		FakeSocket.instances[0].serverClose(4401);
		await vi.waitFor(() => expect(FakeSocket.instances).toHaveLength(2));

		expect(tokens.tryRefresh).toHaveBeenCalledTimes(1);
		expect(tokenOf(FakeSocket.instances[1])).not.toBe(first);
		provider.destroy();
	});

	it('recovers from an unclean 1006 when the token has expired', async () => {
		// A handshake refused without a code (a proxy, or a server that closes
		// before accept) surfaces as 1006 — the symptom seen in production.
		let token = LIVE;
		const tokens = {
			getAccessToken: () => token,
			tryRefresh: vi.fn(async () => {
				token = jwt(7200);
				return true;
			})
		};
		const provider = new ArcheProvider('doc-1', tokens);
		FakeSocket.instances[0].open();

		token = SPENT; // the token expires while the tab sits open
		FakeSocket.instances[0].handshakeFailed();

		await vi.waitFor(() => expect(FakeSocket.instances).toHaveLength(2));
		expect(tokens.tryRefresh).toHaveBeenCalledTimes(1);
		expect(isExpired(tokenOf(FakeSocket.instances[1]))).toBe(false);
		provider.destroy();
	});

	it('a 1006 with a healthy token is a network blip: back off, do not sign out', async () => {
		const tokens = { getAccessToken: () => LIVE, tryRefresh: vi.fn(async () => true) };
		const provider = new ArcheProvider('doc-1', tokens);
		const denied = vi.fn();
		provider.onDenied = denied;

		FakeSocket.instances[0].handshakeFailed();

		expect(tokens.tryRefresh).not.toHaveBeenCalled(); // no needless refresh
		expect(denied).not.toHaveBeenCalled(); // and certainly no sign-out
		provider.destroy();
	});

	it('gives up when the refresh fails', async () => {
		const tokens = { getAccessToken: () => SPENT, tryRefresh: vi.fn(async () => false) };
		const provider = new ArcheProvider('doc-1', tokens);
		const denied = vi.fn();
		provider.onDenied = denied;

		await vi.waitFor(() => expect(denied).toHaveBeenCalled());
		expect(FakeSocket.instances).toHaveLength(0); // never opened a dead socket
		provider.destroy();
	});

	it('does not spin when a refresh hands back a still-spent token', async () => {
		const tokens = { getAccessToken: () => SPENT, tryRefresh: vi.fn(async () => true) };
		const provider = new ArcheProvider('doc-1', tokens);
		const denied = vi.fn();
		provider.onDenied = denied;

		await vi.waitFor(() => expect(denied).toHaveBeenCalled());
		expect(tokens.tryRefresh).toHaveBeenCalledTimes(1); // one attempt, then stop
		provider.destroy();
	});

	it('does not retry a 4403: no role on the document', async () => {
		const tokens = { getAccessToken: () => LIVE, tryRefresh: vi.fn(async () => true) };
		const provider = new ArcheProvider('doc-1', tokens);
		const denied = vi.fn();
		provider.onDenied = denied;

		FakeSocket.instances[0].serverClose(4403);

		expect(denied).toHaveBeenCalled();
		expect(tokens.tryRefresh).not.toHaveBeenCalled();
		expect(FakeSocket.instances).toHaveLength(1);
		provider.destroy();
	});

	it('refreshes only once when several closes arrive in a storm', async () => {
		let token = LIVE;
		const tokens = {
			getAccessToken: () => token,
			tryRefresh: vi.fn(async () => {
				token = jwt(7200);
				return true;
			})
		};
		const provider = new ArcheProvider('doc-1', tokens);

		FakeSocket.instances[0].serverClose(4401);
		FakeSocket.instances[0].serverClose(4401);

		await vi.waitFor(() => expect(FakeSocket.instances).toHaveLength(2));
		expect(tokens.tryRefresh).toHaveBeenCalledTimes(1);
		provider.destroy();
	});

	it('backs off exponentially between reconnect attempts and resets on a frame', () => {
		vi.useFakeTimers();
		const tokens = { getAccessToken: () => LIVE, tryRefresh: vi.fn(async () => false) };
		const provider = new ArcheProvider('doc-1', tokens);
		expect(FakeSocket.instances).toHaveLength(1);

		// First failure: retry after 1500ms.
		FakeSocket.instances[0].handshakeFailed();
		vi.advanceTimersByTime(1499);
		expect(FakeSocket.instances).toHaveLength(1); // not yet
		vi.advanceTimersByTime(1);
		expect(FakeSocket.instances).toHaveLength(2); // reconnected at 1500

		// Second failure: the delay doubled to 3000ms.
		FakeSocket.instances[1].handshakeFailed();
		vi.advanceTimersByTime(1500);
		expect(FakeSocket.instances).toHaveLength(2); // 1500 is no longer enough
		vi.advanceTimersByTime(1500);
		expect(FakeSocket.instances).toHaveLength(3); // reconnected at 3000

		// A frame from the server resets the backoff to the base delay.
		FakeSocket.instances[2].onmessage?.({ data: new Uint8Array(0).buffer } as MessageEvent);
		FakeSocket.instances[2].handshakeFailed();
		vi.advanceTimersByTime(1500);
		expect(FakeSocket.instances).toHaveLength(4); // back to 1500 after the reset

		provider.destroy();
		vi.useRealTimers();
	});
});

describe('ArcheProvider sync protocol', () => {
	const liveTokens = () => ({ getAccessToken: () => LIVE, tryRefresh: vi.fn(async () => true) });

	afterEach(() => vi.useRealTimers());

	it('honours VITE_API_URL for the relay origin', () => {
		vi.stubEnv('VITE_API_URL', 'https://api.cyberarche.io');
		const provider = new ArcheProvider('doc-9', liveTokens());

		const socket = FakeSocket.instances[0];
		expect(socket.url).toContain('wss://api.cyberarche.io/api/v1/documents/doc-9/sync');
		expect(tokenOf(socket)).toBe(LIVE);

		provider.destroy();
		vi.unstubAllEnvs();
	});

	it('announces status and pushes the full local state on open', () => {
		const doc = new Y.Doc();
		doc.getText('t').insert(0, 'offline edits'); // made before connecting
		const provider = new ArcheProvider('doc-1', liveTokens(), doc);
		const statuses: string[] = [];
		provider.onStatus = (s) => statuses.push(s);
		expect(provider.status).toBe('connecting');

		FakeSocket.instances[0].open();

		expect(statuses).toEqual(['connected']);
		const first = FakeSocket.instances[0].sent[0] as Uint8Array;
		expect(first[0]).toBe(0x00); // a CRDT update frame…
		const replica = new Y.Doc();
		Y.applyUpdate(replica, first.slice(1)); // …that replays the local edits
		expect(replica.getText('t').toString()).toBe('offline edits');
		provider.destroy();
	});

	it('merges server updates and fires onSynced exactly once', () => {
		const provider = new ArcheProvider('doc-1', liveTokens());
		const synced = vi.fn();
		provider.onSynced = synced;
		const socket = FakeSocket.instances[0];
		socket.open();

		socket.message(new ArrayBuffer(0)); // a keepalive-ish empty frame is ignored
		expect(synced).not.toHaveBeenCalled();

		const remote = new Y.Doc();
		remote.getText('t').insert(0, 'hello');
		socket.message(frame(0x00, Y.encodeStateAsUpdate(remote)));

		expect(provider.doc.getText('t').toString()).toBe('hello');
		expect(synced).toHaveBeenCalledTimes(1);

		remote.getText('t').insert(5, ' world');
		socket.message(frame(0x00, Y.encodeStateAsUpdate(remote)));
		expect(provider.doc.getText('t').toString()).toBe('hello world');
		expect(synced).toHaveBeenCalledTimes(1); // initial sync only
		provider.destroy();
	});

	it('forwards local edits when connected, but never echoes server frames', () => {
		const provider = new ArcheProvider('doc-1', liveTokens());
		const socket = FakeSocket.instances[0];

		provider.doc.getText('t').insert(0, 'early'); // socket not open yet
		expect(socket.sent).toHaveLength(0);

		socket.open();
		expect(socket.sent).toHaveLength(1); // the full-state push

		provider.doc.getText('t').insert(5, '!');
		expect(socket.sent).toHaveLength(2);
		expect((socket.sent[1] as Uint8Array)[0]).toBe(0x00);

		const remote = new Y.Doc();
		remote.getText('other').insert(0, 'server');
		Y.applyUpdate(provider.doc, Y.encodeStateAsUpdate(remote), 'remote');
		expect(socket.sent).toHaveLength(2); // not echoed back
		provider.destroy();
	});

	it('tracks presence peers and evicts the stale ones', () => {
		vi.useFakeTimers();
		const provider = new ArcheProvider('doc-1', liveTokens());
		const emitted: PresencePeer[][] = [];
		provider.onPeers = (peers) => emitted.push(peers);
		const socket = FakeSocket.instances[0];
		socket.open();

		socket.message(awarenessFrame({ user_id: 'alice', block_id: 'blk-1', color: '#f00' }));
		expect(provider.peers.get('alice')?.block_id).toBe('blk-1');
		expect(emitted.at(-1)?.map((p) => p.user_id)).toEqual(['alice']);

		vi.advanceTimersByTime(31_000); // alice goes quiet past the TTL
		socket.message(awarenessFrame({ user_id: 'bob', block_id: null, color: '#0f0' }));

		expect([...provider.peers.keys()]).toEqual(['bob']);
		expect(emitted.at(-1)?.map((p) => p.user_id)).toEqual(['bob']);
		provider.destroy();
	});

	it('handles control frames: presence_left, NotAuthorized, and noise', () => {
		const provider = new ArcheProvider('doc-1', liveTokens());
		const denied = vi.fn();
		provider.onDenied = denied;
		const socket = FakeSocket.instances[0];
		socket.open();
		socket.message(awarenessFrame({ user_id: 'alice', block_id: null, color: '#f00' }));

		socket.message(JSON.stringify({ type: 'presence_left', user_id: 'alice' }));
		expect(provider.peers.size).toBe(0);

		socket.message(JSON.stringify({ type: 'presence_left' })); // no user_id
		socket.message(JSON.stringify({ type: 'error', error: 'SomethingElse' }));
		expect(denied).not.toHaveBeenCalled();

		socket.message(JSON.stringify({ type: 'error', error: 'NotAuthorized' }));
		expect(denied).toHaveBeenCalledTimes(1);
		provider.destroy();
	});

	it('broadcasts presence only over an open socket', () => {
		const provider = new ArcheProvider('doc-1', liveTokens());
		const socket = FakeSocket.instances[0];

		provider.broadcastPresence('blk-1', 'alice', '#f00'); // still connecting
		expect(socket.sent).toHaveLength(0);

		socket.open();
		provider.broadcastPresence('blk-1', 'alice', '#f00');

		const presence = socket.sent[1] as Uint8Array;
		expect(presence[0]).toBe(0x01);
		expect(JSON.parse(new TextDecoder().decode(presence.slice(1)))).toEqual({
			user_id: 'alice',
			block_id: 'blk-1',
			color: '#f00'
		});
		provider.destroy();
	});

	it('works without any callbacks wired (defaults are no-ops)', () => {
		const provider = new ArcheProvider('doc-1', liveTokens());
		const socket = FakeSocket.instances[0];
		socket.open();

		const remote = new Y.Doc();
		remote.getText('t').insert(0, 'quiet');
		socket.message(frame(0x00, Y.encodeStateAsUpdate(remote))); // default onSynced
		socket.message(JSON.stringify({ type: 'error', error: 'NotAuthorized' })); // default onDenied

		expect(provider.doc.getText('t').toString()).toBe('quiet');
		provider.destroy();
	});

	it('an errored socket is closed so the close path takes over', () => {
		const provider = new ArcheProvider('doc-1', liveTokens());
		const socket = FakeSocket.instances[0];
		socket.onerror?.();
		expect(socket.closedByClient).toBe(true);
		provider.destroy();
	});
});

describe('ArcheProvider teardown', () => {
	afterEach(() => vi.useRealTimers());

	it('a refresh network failure retries after the base delay', async () => {
		vi.useFakeTimers();
		const tokens = {
			getAccessToken: () => SPENT,
			tryRefresh: vi.fn(async () => {
				throw new Error('network down');
			})
		};
		const provider = new ArcheProvider('doc-1', tokens);
		await vi.advanceTimersByTimeAsync(0); // flush the rejection
		expect(tokens.tryRefresh).toHaveBeenCalledTimes(1);
		expect(FakeSocket.instances).toHaveLength(0); // never dialed a dead token

		await vi.advanceTimersByTimeAsync(1500);
		expect(tokens.tryRefresh).toHaveBeenCalledTimes(2); // kept trying
		provider.destroy();
	});

	it('destroy closes the socket and detaches from the doc', () => {
		const tokens = { getAccessToken: () => LIVE, tryRefresh: vi.fn(async () => true) };
		const provider = new ArcheProvider('doc-1', tokens);
		const socket = FakeSocket.instances[0];
		socket.open();

		provider.destroy();

		expect(socket.closedByClient).toBe(true);
		provider.doc.getText('t').insert(0, 'after death');
		expect(socket.sent).toHaveLength(1); // only the original state push

		// A straggling close event must not resurrect the connection.
		socket.serverClose(1006);
		expect(FakeSocket.instances).toHaveLength(1);
		expect(provider.status).toBe('connected'); // untouched after teardown
	});

	it('destroy cancels a pending reconnect', () => {
		vi.useFakeTimers();
		const tokens = { getAccessToken: () => LIVE, tryRefresh: vi.fn(async () => true) };
		const provider = new ArcheProvider('doc-1', tokens);
		FakeSocket.instances[0].handshakeFailed(); // reconnect scheduled

		provider.destroy();
		vi.advanceTimersByTime(60_000);
		expect(FakeSocket.instances).toHaveLength(1); // never re-dialed
	});

	it('a refresh resolving after destroy does not reconnect', async () => {
		let resolveRefresh!: (ok: boolean) => void;
		const tokens = {
			getAccessToken: () => SPENT,
			tryRefresh: vi.fn(() => new Promise<boolean>((r) => (resolveRefresh = r)))
		};
		const provider = new ArcheProvider('doc-1', tokens);
		expect(tokens.tryRefresh).toHaveBeenCalledTimes(1);

		provider.destroy();
		resolveRefresh(true);
		await Promise.resolve();
		await Promise.resolve();
		expect(FakeSocket.instances).toHaveLength(0);
	});
});
