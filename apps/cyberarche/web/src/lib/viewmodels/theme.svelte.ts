/** Theme ViewModel: light/dark, persisted, applied on the root element. */

const STORAGE_KEY = 'cyberarche.theme';

export function createTheme() {
	let mode = $state<'light' | 'dark'>(
		typeof localStorage !== 'undefined' && localStorage.getItem(STORAGE_KEY) === 'dark'
			? 'dark'
			: 'light'
	);

	function apply() {
		if (typeof document === 'undefined') return;
		if (mode === 'dark') document.documentElement.dataset.theme = 'dark';
		else delete document.documentElement.dataset.theme;
	}

	apply();
	return {
		get mode() {
			return mode;
		},
		toggle() {
			mode = mode === 'dark' ? 'light' : 'dark';
			localStorage.setItem(STORAGE_KEY, mode);
			apply();
		}
	};
}

export const theme = createTheme();
