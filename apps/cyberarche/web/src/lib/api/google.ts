/** Google Workspace connector (google-workspace-connector spec). */
import { del, get } from './http';

export interface GoogleStatus {
	connected: boolean;
	configured: boolean;
	email: string | null;
	status: string | null;
	scopes: string[];
	expires_at: string | null;
}

export const getGoogleStatus = (workspaceId: string) =>
	get<GoogleStatus>(`/api/v1/workspaces/${workspaceId}/google/status`);

export const getGoogleConnectUrl = (workspaceId: string, groups: string[]) =>
	get<{ url: string }>(
		`/api/v1/workspaces/${workspaceId}/google/connect?groups=${groups.join(',')}`
	);

export const disconnectGoogle = (workspaceId: string) =>
	del<void>(`/api/v1/workspaces/${workspaceId}/google`);
