import { del, get, post } from './http';

export interface ApiKey {
	id: string;
	name: string;
	prefix: string;
	created_at: string;
	expires_at: string | null;
	revoked: boolean;
	last_used_at: string | null;
}

export interface CreatedApiKey extends ApiKey {
	secret: string; // shown exactly once
}

export const createApiKey = (name: string) =>
	post<CreatedApiKey>('/api/v1/api-keys', { name });

export const listApiKeys = () => get<ApiKey[]>('/api/v1/api-keys');

export const revokeApiKey = (keyId: string) => del<ApiKey>(`/api/v1/api-keys/${keyId}`);
