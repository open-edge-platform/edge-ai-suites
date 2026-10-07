/**
 * Main application entry point
 */
(function () {
    const $ = (sel) => document.querySelector(sel);
    const els = {
        themeToggle: $('#themeToggle'),
        composer: $('#composer'),
        input: $('#userInput'),
        sendBtn: $('#sendBtn'),
        messages: $('#messages'),
        hint: $('#chatHint'),
        newChatBtn: $('#newChatBtn'),
        convList: document.querySelector('.conv-list'),
    };

    function isEmbedded() {
        return window.self !== window.top;
    }

    function setEmbeddedModeClass(enabled) {
        const root = document.body;
        if (!root) return;
        root.classList.toggle('embedded-mode', enabled);
    }

    function hideThemeToggleForEmbeddedMode() {
        if (!els.themeToggle) return;
        els.themeToggle.hidden = true;
        els.themeToggle.style.display = 'none';
        els.themeToggle.setAttribute('aria-hidden', 'true');
        els.themeToggle.setAttribute('tabindex', '-1');
    }

    function isTrustedParentOrigin(origin) {
        try {
            const parsed = new URL(origin);
            return parsed.hostname === window.location.hostname;
        } catch (_e) {
            return false;
        }
    }

    function handleThemeSyncMessage(event) {
        if (!isTrustedParentOrigin(event.origin)) return;
        const data = event.data || {};
        if (data.type !== 'LVC_THEME_SYNC') return;
        if (data.theme !== 'light' && data.theme !== 'dark') return;
        // If a parent sends theme-sync, we are in embedded mode.
        setEmbeddedModeClass(true);
        hideThemeToggleForEmbeddedMode();
        ThemeManager.applyTheme(data.theme, els.themeToggle);
    }

    function getEmbeddedInitialTheme() {
        if (!isEmbedded()) return null;
        const theme = new URLSearchParams(window.location.search).get('theme');
        return theme === 'light' || theme === 'dark' ? theme : null;
    }

    // Theme Setup
    ThemeManager.applyTheme(getEmbeddedInitialTheme() || ThemeManager.detectInitialTheme(), els.themeToggle);
    const embedded = isEmbedded();
    setEmbeddedModeClass(embedded);
    if (embedded && els.themeToggle) {
        hideThemeToggleForEmbeddedMode();
    }
    if (els.themeToggle) {
        els.themeToggle.addEventListener('click', () => {
            ThemeManager.toggleTheme(els.themeToggle);
        });
    }

    window.addEventListener('message', handleThemeSyncMessage);

    // Initialize chat UI
    ChatUI.init(els);
})();