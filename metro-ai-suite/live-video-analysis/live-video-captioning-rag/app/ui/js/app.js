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

    // Theme Setup
    ThemeManager.applyTheme(ThemeManager.detectInitialTheme(), els.themeToggle);
    if (els.themeToggle) {
        els.themeToggle.addEventListener('click', () => {
            ThemeManager.toggleTheme(els.themeToggle);
        });
    }

    // Initialize chat UI
    ChatUI.init(els);
})();