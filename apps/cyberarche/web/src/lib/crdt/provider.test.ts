import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ArcheProvider } from './provider';

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

	/** Simulate the server closing the handshake with a code. */
	serverClose(code: number) {
		this.onclose?.({ code } as CloseEvent);
	}
}

function tokenOf(socket: FakeSocket): string {
	return new URL(socket.url).searchParams.get('token') ?? '';
}

beforeEach(() => {
	FakeSocket.instances = [];
	vi.stubGlobal('WebSocket', FakeSocket as unknown as typeof WebSocket);
	vi.stubGlobal('window', { location: { origin: 'http://localhost' } });
});

describe('ArcheProvider token lifecycle', () => {
	it('reconnects with a REFRESHED token after the server rejects an expired one', async () => {
		// Regression: the provider captured the access token once, so every
		// reconnect after the 15-minute expiry retried the dead token and the
		// server refused it with 4401 forever. Seen in production as an endless
		// "WebSocket connection failed" loop.
		let token = 'expired';
		const tokens = {
			getAccessToken: () => token,
			tryRefresh: vi.fn(async () => {
				token = 'fresh';
				return true;
			})
		};
		const provider = new ArcheProvider('doc-1', tokens);
		expect(tokenOf(FakeSocket.instances[0])).toBe('expired');

		FakeSocket.instances[0].serverClose(4401);
		await vi.waitFor(() => expect(FakeSocket.instances).toHaveLength(2));

		expect(tokens.tryRefresh).toHaveBeenCalledTimes(1);
		expect(tokenOf(FakeSocket.instances[1])).toBe('fresh'); // not 'expired'
		provider.destroy();
	});

	it('gives up (and signals denial) when the refresh fails', async () => {
		const tokens = { getAccessToken: () => 'expired', tryRefresh: vi.fn(async () => false) };
		const provider = new ArcheProvider('doc-1', tokens);
		const denied = vi.fn();
		provider.onDenied = denied;

		FakeSocket.instances[0].serverClose(4401);
		await vi.waitFor(() => expect(denied).toHaveBeenCalled());

		expect(FakeSocket.instances).toHaveLength(1); // no dead-token retry loop
		provider.destroy();
	});

	it('does not retry a 4403: no role on the document', async () => {
		const tokens = { getAccessToken: () => 'good', tryRefresh: vi.fn(async () => true) };
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
		let token = 'expired';
		const tokens = {
			getAccessToken: () => token,
			tryRefresh: vi.fn(async () => {
				token = 'fresh';
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
