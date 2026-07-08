import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ArcheProvider, isExpired } from './provider';

/** A WebSocket whose lifecycle the test drives by hand. */
class FakeSocket {
	static instances: FakeSocket[] = [];
	onopen: (() => void) | null = null;
	onmessage: ((event: MessageEvent) => void) | null = null;
	onclose: ((event: CloseEvent) => void) | null = null;
	onerror: (() => void) | null = null;
	binaryType = '';
	sent: unknown[] = [];

	constructor(readonly url: string) {
		FakeSocket.instances.push(this);
	}
	send(data: unknown) {
		this.sent.push(data);
	}
	close() {}

	/** The server refuses with an application close code (accept-then-close). */
	serverClose(code: number) {
		this.onclose?.({ code } as CloseEvent);
	}
	/** The handshake itself failed: browsers report an unclean 1006. */
	handshakeFailed() {
		this.onclose?.({ code: 1006 } as CloseEvent);
	}
	open() {
		this.onopen?.();
	}
}

/** A JWT whose `exp` we control. Only the payload is ever read. */
function jwt(secondsFromNow: number): string {
	const payload = { exp: Math.floor(Date.now() / 1000) + secondsFromNow };
	return `h.${btoa(JSON.stringify(payload))}.s`;
}

function tokenOf(socket: FakeSocket): string {
	return new URL(socket.url).searchParams.get('token') ?? '';
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
	it('refreshes BEFORE connecting when the token is already spent', async () => {
		// The socket carries its token in the URL, so connecting with a spent one
		// is refused at the handshake — where the close code was historically
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
});
