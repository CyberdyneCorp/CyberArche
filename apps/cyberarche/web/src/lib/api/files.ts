/** File uploads (file-uploads spec): upload an image, get back a served URL. */
import { postForm } from './http';

export interface UploadedFile {
	id: string;
	url: string;
	content_type: string;
}

export const uploadImage = (workspaceId: string, file: File) => {
	const form = new FormData();
	form.append('file', file);
	return postForm<UploadedFile>(`/api/v1/workspaces/${workspaceId}/files`, form);
};
