"""
Full library scan CLI.

Run via:
    python -m app.scripts.scan              # full scan
    python -m app.scripts.scan --dry        # dry run (list files only)
    # or inside Docker:
    docker compose exec backend python -m app.scripts.scan
"""
import sys

from app.services.scanner import main

if __name__ == "__main__":
    main()
