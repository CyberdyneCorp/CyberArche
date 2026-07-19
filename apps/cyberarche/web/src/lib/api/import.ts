/** Document import (document-import spec): upload a file (Markdown / Word /
 * text / Notion .zip) and get back the created private document(s). */
import type { Document } from './documents';
import { postForm } from './http';

/** Import a file into new private document(s); returns them (roots first). */
export const importFile = (workspaceId: string, file: File) => {
	const form = new FormData();
	form.append('file', file);
	return postForm<Document[]>(`/api/v1/workspaces/${workspaceId}/import`, form);
};
