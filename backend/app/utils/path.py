import os

from fastapi import HTTPException, status


def safe_resolve(base_dir: str, relative_path: str) -> str:
    """
    Safely resolve a relative path within a base directory.
    Prevents path traversal attacks.
    """
    base = os.path.realpath(base_dir)
    full = os.path.realpath(os.path.join(base, relative_path))

    if not full.startswith(base + os.sep) and full != base:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file path",
        )

    return full
