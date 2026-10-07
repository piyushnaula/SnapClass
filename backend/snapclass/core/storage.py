"""File storage for photos, audio and face crops.

Files live in a local folder (a Docker volume shared by the API and the worker).
To move to S3 later, write an S3Storage class with the same methods.
"""

import re
import shutil
from pathlib import Path

from snapclass.core.config import settings

# Keys look like "sessions/<uuid>/<uuid>.jpg". Only safe characters are allowed,
# which blocks path tricks such as "../../etc/passwd".
_SAFE_KEY = re.compile(r"^[A-Za-z0-9_\-./]+$")


class LocalStorage:
    def __init__(self, base_dir: str):
        self.base = Path(base_dir).resolve()

    def _path(self, key: str) -> Path:
        if not _SAFE_KEY.match(key) or ".." in key or key.startswith("/"):
            raise ValueError(f"Unsafe storage key: {key!r}")
        return self.base / key

    def save(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def read(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def delete_folder(self, prefix: str) -> None:
        """Delete every file under a folder, e.g. "crops/<session_id>/" before a new check."""
        folder = self._path(prefix.rstrip("/"))
        if folder.is_dir():
            shutil.rmtree(folder)

    def local_path(self, key: str) -> Path:
        """Used by the API to stream a file back (signed media URLs)."""
        return self._path(key)


storage = LocalStorage(settings.media_dir)
