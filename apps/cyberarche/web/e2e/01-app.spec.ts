import { expect, test } from '@playwright/test';

/** Full vertical against the real backend + live CyberdyneAuth.
 * Requires CYBERARCHE_IT_EMAIL / CYBERARCHE_IT_PASSWORD (a test user). */

const EMAIL = process.env.CYBERARCHE_IT_EMAIL ?? '';
const PASSWORD = process.env.CYBERARCHE_IT_PASSWORD ?? '';

test.skip(!EMAIL || !PASSWORD, 'CYBERARCHE_IT_EMAIL / _PASSWORD not configured');

async function signIn(page: import('@playwright/test').Page) {
	await page.goto('/');
	await page.waitForURL('**/signin');
	await page.getByPlaceholder('you@company.com').fill(EMAIL);
	await page.locator('input[type="password"]').fill(PASSWORD);
	await page.getByRole('button', { name: 'Sign in' }).click();
}

test('sign in, create workspace and documents, organize the tree', async ({ page }) => {
	await signIn(page);

	// Fresh in-memory backend -> first-run workspace creation.
	await page.waitForURL('**/w/new');
	await page.getByTestId('workspace-name-input').fill('Arche Labs');
	await page.getByTestId('create-workspace').click();
	await expect(page.getByTestId('workspace-name')).toHaveText('Arche Labs');

	// Create a document and give it a title. Wait for the document to sync
	// before typing: the title input mounts in the same flush that seeds its
	// value, and a fill() landing inside that flush is overwritten by the
	// binding — a race only an automated driver can hit, but it silently
	// dropped the rename and left the tree showing "Untitled".
	await page.getByTestId('new-document').click();
	await page.waitForURL('**/d/**');
	await expect(page.getByTestId('sync-status')).toHaveText('Synced');
	await page.getByTestId('doc-title').fill('Retrieval Pipeline RFC');
	await page.getByTestId('doc-title').press('Enter');
	await expect(page.getByTestId('tree-doc').first()).toContainText(
		'Retrieval Pipeline RFC'
	);

	// Nest a child under it via the tree hover action.
	const firstRow = page.locator('.item').first();
	await firstRow.hover();
	await firstRow.getByLabel('Add child document').click();
	await firstRow.getByLabel('Collapse').isVisible(); // auto-expanded
	await expect(page.getByTestId('tree-doc')).toHaveCount(2);

	// Trash the child, then restore it from the Trash section.
	const childRow = page.locator('.item').nth(1);
	await childRow.hover();
	await childRow.getByLabel('Move to trash').click();
	await expect(page.getByTestId('tree-doc')).toHaveCount(1);
	await expect(page.getByTestId('trash-doc')).toHaveCount(1);
	await page.getByTestId('trash-doc').getByTestId('trash-restore').click();
	await expect(page.getByTestId('trash-doc')).toHaveCount(0);
});

test('invalid credentials are rejected by the live auth service', async ({ page }) => {
	await page.goto('/signin');
	await page.getByPlaceholder('you@company.com').fill(EMAIL);
	await page.locator('input[type="password"]').fill('definitely-wrong-password');
	await page.getByRole('button', { name: 'Sign in' }).click();
	await expect(page.getByRole('alert')).toContainText(/failed/i);
	await expect(page).toHaveURL(/signin/);
});

test('theme toggle persists across reloads', async ({ page }) => {
	await signIn(page);
	await page.waitForURL(/\/w\//);
	// Workspace may or may not exist depending on test order; ensure shell.
	if (page.url().endsWith('/w/new')) {
		await page.getByTestId('workspace-name-input').fill('Theme WS');
		await page.getByTestId('create-workspace').click();
	}
	await page.getByTestId('theme-toggle').click();
	await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
	await page.reload();
	await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
});
