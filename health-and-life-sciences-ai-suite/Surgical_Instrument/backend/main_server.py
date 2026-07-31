"""CLI entrypoint: `python -m backend.main_server`."""
from __future__ import annotations

from .server.app import main

if __name__ == "__main__":
    main()
