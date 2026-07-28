from enum import Enum


class CapabilityState(Enum):
    """Lifecycle states for a loaded capability.

    Allowed transitions
    -------------------
    UNLOADED → LOADING  : first call to load() / extract_text()
    LOADING  → READY    : processor + runner built successfully
    LOADING  → UNLOADED : build failed (exception); slot released
    READY    → EVICTING : shutdown() called
    EVICTING → UNLOADED : runner released; handler ready to be re-created
    """

    UNLOADED = "unloaded"
    LOADING = "loading"
    READY = "ready"
    EVICTING = "evicting"