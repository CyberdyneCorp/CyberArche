/** Page templates (page-templates). */
import type { Document } from './documents';
import { del, get, post } from './http';

export interface Template {
	id: string;
	name: string;
	created_by: string;
	created_at: string;
	block_count: number;
}

export const listTemplates = (workspaceId: string) =>
	get<Template[]>(`/api/v1/workspaces/${workspaceId}/templates`);

export const saveTemplate = (workspaceId: string, name: string, documentId: string) =>
	post<Template>(`/api/v1/workspaces/${workspaceId}/templates`, {
		name,
		document_id: documentId
	});

export const instantiateTemplate = (
	workspaceId: string,
	templateId: string,
	title: string,
	teamspaceId?: string | null
) =>
	post<Document>(
		`/api/v1/workspaces/${workspaceId}/templates/${templateId}/instantiate`,
		{ title, teamspace_id: teamspaceId ?? null }
	);

export const deleteTemplate = (templateId: string) =>
	del<void>(`/api/v1/templates/${templateId}`);
