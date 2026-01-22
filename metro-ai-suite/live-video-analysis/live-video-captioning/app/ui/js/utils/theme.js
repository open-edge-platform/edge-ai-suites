/**
 * Theme management utilities
 */
const ThemeManager = (function() {
    const THEME_KEY = 'lvc-theme';

    function detectInitialTheme() {
        try {
            const saved = localStorage.getItem(THEME_KEY);
            if (saved === 'light' || saved === 'dark') return saved;
        } catch (_err) {}
        if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) return 'dark';
        return 'light';
    }

    function applyTheme(theme, themeToggle) {
        const next = theme === 'light' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', next);
        if (themeToggle) {
            themeToggle.setAttribute('aria-label', next === 'light' ? 'Switch to dark mode' : 'Switch to light mode');
        }
        try {
            localStorage.setItem(THEME_KEY, next);
        } catch (_err) {}
    }

    function toggleTheme(themeToggle) {
        const current = document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
        applyTheme(current === 'light' ? 'dark' : 'light', themeToggle);
    }

    function getChartColors() {
        const isLight = document.documentElement.getAttribute('data-theme') === 'light';
        return {
            gridColor: isLight ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.05)',
            tickColor: isLight ? 'rgba(0,0,0,0.65)' : 'rgba(255,255,255,0.55)',
        };
    }

    return {
        detectInitialTheme,
        applyTheme,
        toggleTheme,
        getChartColors
    };
})();
