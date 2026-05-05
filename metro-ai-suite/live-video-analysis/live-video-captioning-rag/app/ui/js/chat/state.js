/**
 * Conversation state (localStorage + helpers)
 */
const ConversationState = (function () {
    const STORAGE_KEY = 'lvc-conversations-v1';

    // state = { conversations: [ { id, title, createdAt, messages:[{role,text,ts}], framesMeta? } ], activeId }
    let state = loadState();

    /*
     * Loads state from localStorage, with basic validation
     */
    function loadState() {
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            const parsed = raw ? JSON.parse(raw) : null;
            if (parsed && Array.isArray(parsed.conversations)) return parsed;
        } catch { }
        return { conversations: [], activeId: null };
    }

    /*
     * Persists current state to localStorage
     */
    function persist() {
        try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); } catch { }
    }

    /*
     * Generates a unique ID for conversations
     */
    function uid() {
        return (crypto?.randomUUID?.() || `id_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`);
    }

    /*
     * Generates a title from the first message or fallback
     */
    function titleFrom(text) {
        return (text || '').replace(/\s+/g, ' ').trim().slice(0, 60) || 'New chat';
    }

    /*
     * Returns the entire state object
     */
    function getState() { return state; }

    /*
     * Returns the active conversation object
     */
    function getActiveConversation() {
        return state.conversations.find(c => c.id === state.activeId) || null;
    }

    /*
     * Ensures there is an active conversation, creating one if necessary
     */
    function ensureActiveConversation(initialTitle) {
        if (state.activeId && getActiveConversation()) return state.activeId;
        const id = uid();
        const conv = {
            id,
            title: titleFrom(initialTitle),
            createdAt: Date.now(),
            messages: []
        };
        state.conversations.unshift(conv);
        state.activeId = id;
        persist();
        return id;
    }

    /*
     * Sets the active conversation by ID, returns the ID if successful
     */
    function setActive(id) {
        const exists = state.conversations.some(c => c.id === id);
        if (!exists) return null;
        state.activeId = id;
        persist();
        return id;
    }

    /*
     * Adds a message to the active conversation
     */
    function addMessageToActive(role, text) {
        const conv = getActiveConversation();
        if (!conv) return;
        conv.messages.push({ role, text, ts: Date.now() });
        persist();
    }

    /*
     * Sets frames metadata for the active conversation
     */
    function setFramesMetaForActive(meta) {
        const conv = getActiveConversation();
        if (!conv) return;
        conv.framesMeta = meta;
        persist();
    }

    /*
     * Moves the active conversation to the top of the list
     */
    function bumpActiveToTop() {
        const idx = state.conversations.findIndex(c => c.id === state.activeId);
        if (idx > 0) {
            const [c] = state.conversations.splice(idx, 1);
            state.conversations.unshift(c);
            persist();
        }
    }

    /*
     * Deletes a conversation by ID
     */
    function deleteConversation(id) {
        const idx = state.conversations.findIndex(c => c.id === id);
        if (idx === -1) return;
        const deletingActive = (state.activeId === id);
        state.conversations.splice(idx, 1);
        if (deletingActive) {
            state.activeId = state.conversations[0]?.id ?? null;
        }
        persist();
    }

    return {
        getState,
        loadState: () => { state = loadState(); },
        persist,
        uid,
        titleFrom,
        getActiveConversation,
        ensureActiveConversation,
        setActive,
        addMessageToActive,
        setFramesMetaForActive,
        bumpActiveToTop,
        deleteConversation
    };
})();
