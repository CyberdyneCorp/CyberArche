/** Connector settings ViewModel (external-mcp-connectors spec):
 * attach/enable/disable/remove external MCP servers and inspect the
 * namespaced tools they contribute to the agent. */

import {
	listConnectors,
	listExternalTools,
	registerConnector,
	removeConnector,
	setConnectorEnabled,
	type Connector,
	type ExternalTool
} from '$lib/api/connectors';

export function createConnectors(workspaceId: string) {
	let items = $state<Connector[]>([]);
	let tools = $state<ExternalTool[]>([]);
	let error = $state<string | null>(null);
	let busy = $state(false);

	async function refreshTools() {
		try {
			tools = await listExternalTools(workspaceId);
		} catch {
			tools = [];
		}
	}

	return {
		get items() {
			return items;
		},
		get tools() {
			return tools;
		},
		get error() {
			return error;
		},
		get busy() {
			return busy;
		},
		toolsOf(connector: Connector): ExternalTool[] {
			return tools.filter((tool) => tool.name.startsWith(`${connector.slug}__`));
		},

		async load() {
			items = await listConnectors(workspaceId);
			await refreshTools();
		},

		/** Registration performs a live MCP handshake server-side; failures
		 * (unreachable endpoint, bad credentials) surface as errors here. */
		async register(name: string, endpoint: string, credentials = ''): Promise<boolean> {
			busy = true;
			error = null;
			try {
				const connector = await registerConnector(workspaceId, name, endpoint, credentials);
				items = [...items, connector];
				await refreshTools();
				return true;
			} catch (err) {
				error = (err as Error).message;
				return false;
			} finally {
				busy = false;
			}
		},

		async setEnabled(connectorId: string, enabled: boolean) {
			error = null;
			try {
				const updated = await setConnectorEnabled(workspaceId, connectorId, enabled);
				items = items.map((c) => (c.id === connectorId ? updated : c));
				await refreshTools();
			} catch (err) {
				error = (err as Error).message;
			}
		},

		async remove(connectorId: string) {
			error = null;
			try {
				await removeConnector(workspaceId, connectorId);
				items = items.filter((c) => c.id !== connectorId);
				await refreshTools();
			} catch (err) {
				error = (err as Error).message;
			}
		}
	};
}

export type ConnectorsVM = ReturnType<typeof createConnectors>;
