/**
 * Theme Manager Module - Handles light/dark theme switching and persistence
 */
const ThemeManager = (function () {
    const THEME_KEY = 'lvc-theme';

    /*
     * Detects initial theme: localStorage -> system preference -> light (default)
     */
    function detectInitialTheme() {
        try {
            const saved = localStorage.getItem(THEME_KEY);
            if (saved === 'light' || saved === 'dark') return saved;
        } catch (_err) { }
        if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) return 'dark';
        return 'light';
    }

    /*
     * Applies theme to document and updates toggle button accessibility
     */
    function applyTheme(theme, themeToggle) {
        const next = theme === 'light' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', next);
        if (themeToggle) {
            const sunIcon = themeToggle.querySelector('.icon-sun');
            const moonIcon = themeToggle.querySelector('.icon-moon');

            if (sunIcon) sunIcon.hidden = next !== 'light';
            if (moonIcon) moonIcon.hidden = next !== 'dark';
            themeToggle.setAttribute('aria-label', next === 'light' ? 'Switch to dark mode' : 'Switch to light mode');
        }
        try {
            localStorage.setItem(THEME_KEY, next);
        } catch (_err) { }
    }

    /*
     * Toggles between light and dark themes
     */
    function toggleTheme(themeToggle) {
        const current = document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
        applyTheme(current === 'light' ? 'dark' : 'light', themeToggle);
    }

    return {
        detectInitialTheme,
        applyTheme,
        toggleTheme
    };
})();