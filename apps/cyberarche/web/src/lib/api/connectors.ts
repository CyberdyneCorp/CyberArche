import { del, get, patch, post } from './http';

export interface Connector {
	id: string;
	name: string;
	slug: string;
	endpoint: string;
	enabled: boolean;
	created_by: string;
	created_at: string;
}

export interface ExternalTool {
	name: string;
	description: string;
}

export const listConnectors = (workspaceId: string) =>
	get<Connector[]>(`/api/v1/workspaces/${workspaceId}/connectors`);

export const registerConnector = (
	workspaceId: string,
	name: string,
	endpoint: string,
	credentials = ''
) =>
	post<Connector>(`/api/v1/workspaces/${workspaceId}/connectors`, {
		name,
		endpoint,
		credentials
	});

export const setConnectorEnabled = (workspaceId: string, connectorId: string, enabled: boolean) =>
	patch<Connector>(`/api/v1/workspaces/${workspaceId}/connectors/${connectorId}`, { enabled });

export const removeConnector = (workspaceId: string, connectorId: string) =>
	del<void>(`/api/v1/workspaces/${workspaceId}/connectors/${connectorId}`);

export const listExternalTools = (workspaceId: string) =>
	get<ExternalTool[]>(`/api/v1/workspaces/${workspaceId}/connectors/tools`);
