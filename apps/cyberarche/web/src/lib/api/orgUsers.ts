/** Organization user directory (org-directory spec): identity data proxied
 * from CyberdyneAuth — searchable, paginated, scoped to the caller's org. */
import { get } from './http';

export interface OrgUser {
	id: string;
	email: string | null;
	avatar_url: string | null;
	is_active: boolean;
}

export interface OrgUsersPage {
	users: OrgUser[];
	total: number;
	page: number;
	page_size: number;
}

export const listOrgUsers = (search = '', page = 1, pageSize = 50) =>
	get<OrgUsersPage>(
		`/api/v1/org/users?${new URLSearchParams({
			search,
			page: String(page),
			page_size: String(pageSize)
		})}`
	);
