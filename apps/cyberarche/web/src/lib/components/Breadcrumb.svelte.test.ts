import { flushSync, mount, unmount } from 'svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import Breadcrumb from './Breadcrumb.svelte';
import type { PathCrumb } from '$lib/api/documents';

const CRUMBS: PathCrumb[] = [
	{ kind: 'workspace', id: 'ws-1', label: 'Acme' },
	{ kind: 'teamspace', id: 'ts-1', label: 'Team' },
	{ kind: 'folder', id: 'f-1', label: 'Research' },
	{ kind: 'document', id: 'doc-parent', label: 'Parent' },
	{ kind: 'document', id: 'doc-self', label: 'Child' }
];

describe('Breadcrumb component', () => {
	let target: HTMLElement;
	let instance: Record<string, unknown> | null = null;

	beforeEach(() => {
		target = document.createElement('div');
		document.body.appendChild(target);
	});
	afterEach(() => {
		if (instance) unmount(instance);
		instance = null;
		target.remove();
	});

	function render(crumbs: PathCrumb[], onNavigate = vi.fn()) {
		instance = mount(Breadcrumb, {
			target,
			props: { crumbs, workspaceId: 'ws-1', onNavigate }
		});
		flushSync();
		return onNavigate;
	}

	it('renders workspace and ancestor documents as links, the rest as text', () => {
		render(CRUMBS);
		const links = target.querySelectorAll<HTMLAnchorElement>('[data-testid="crumb-link"]');
		const texts = target.querySelectorAll('[data-testid="crumb-text"]');

		// workspace + parent document are navigable.
		expect([...links].map((a) => a.textContent)).toEqual(['Acme', 'Parent']);
		// teamspace, folder, and the current document render as plain text.
		expect([...texts].map((t) => t.textContent)).toEqual(['Team', 'Research', 'Child']);
	});

	it('puts a separator between crumbs (one fewer than the crumbs)', () => {
		render(CRUMBS);
		expect(target.querySelectorAll('.sep').length).toBe(CRUMBS.length - 1);
	});

	it('clicking the workspace crumb navigates to the workspace route', () => {
		const onNavigate = render(CRUMBS);
		const links = target.querySelectorAll<HTMLAnchorElement>('[data-testid="crumb-link"]');
		links[0].click();
		expect(onNavigate).toHaveBeenCalledWith('/w/ws-1');
	});

	it('clicking an ancestor document navigates to that document', () => {
		const onNavigate = render(CRUMBS);
		const links = target.querySelectorAll<HTMLAnchorElement>('[data-testid="crumb-link"]');
		links[1].click();
		expect(onNavigate).toHaveBeenCalledWith('/w/ws-1/d/doc-parent');
	});

	it('never links the final crumb (the current document)', () => {
		const onNavigate = render([
			{ kind: 'workspace', id: 'ws-1', label: 'Acme' },
			{ kind: 'document', id: 'doc-self', label: 'Solo' }
		]);
		const texts = target.querySelectorAll('[data-testid="crumb-text"]');
		expect([...texts].map((t) => t.textContent)).toEqual(['Solo']);
		// The only link is the workspace, not the document itself.
		expect(target.querySelectorAll('[data-testid="crumb-link"]').length).toBe(1);
		expect(onNavigate).not.toHaveBeenCalled();
	});
});
