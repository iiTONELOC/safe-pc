import os
import json
import asyncio
from time import time
from typing import Any
from pathlib import Path
from logging import getLogger


LOGGER = getLogger(__name__)
CACHED_DATA_DIR = Path(__file__).parents[4] / "data" / "cached_answers"

class CacheManager:
    MANIFEST_VERSION = 1

    def __init__(self, cache_dir: Path | str):
        self.cache_dir = Path(cache_dir).resolve()
        self.data_dir = self.cache_dir / "data"
        self.manifest_path = self.cache_dir / "manifest.json"
        self._lock = asyncio.Lock()
        self._manifest: dict[str, Any] = {
            "version": self.MANIFEST_VERSION,
            "created_at": time(),
            "updated_at": time(),
            "answers": {},   # job_id -> path
            "isos": {},      # job_id -> iso path
        }

    @classmethod
    async def new(cls) -> "CacheManager":
        self = cls(CACHED_DATA_DIR)
        await asyncio.to_thread(self.data_dir.mkdir, parents=True, exist_ok=True)
        await self._load_manifest()
        return self

    async def _load_manifest(self):
        if self.manifest_path.exists():
            try:
                data = json.loads(self.manifest_path.read_text())
                if data.get("version") == self.MANIFEST_VERSION:
                    self._manifest = data
                else:
                    LOGGER.warning("Manifest version mismatch, reinitializing.")
                    await self._persist_manifest()
            except Exception:
                LOGGER.warning("Manifest load failed, reinitializing.")
                await self._persist_manifest()
        else:
            await self._persist_manifest()

    async def _persist_manifest(self):
        """Asynchronously writes the manifest to disk ensuring atomicity."""
        self._manifest["updated_at"] = time()
        tmp = self.manifest_path.with_suffix(".tmp")
        txt = json.dumps(self._manifest, indent=2)
        await asyncio.to_thread(tmp.write_text, txt, "utf-8")
        await asyncio.to_thread(os.replace, tmp, self.manifest_path)
        
    async def put_answer_bytes(self, job_id: str, data: bytes):
        """Asynchronously stores answer file bytes for a given job_id.
        
        Args:
            job_id (str): The unique identifier for the job.
            data (bytes): The answer file content to be stored.
        
        Returns:
            The path where the answer file is stored.
        """
        dest = self.data_dir / f"{job_id}.answer"
        tmp = dest.with_suffix(".tmp")
        async with self._lock:
            await asyncio.to_thread(tmp.write_bytes, data)
            await asyncio.to_thread(os.replace, tmp, dest)
            self._manifest["answers"][job_id] = str(dest)
            await self._persist_manifest()
        return dest

    async def read_answer_bytes(self, job_id: str) -> bytes | None:
        """Asynchronously reads the answer file bytes for a given job_id."""
        async with self._lock:
            p = Path(self._manifest["answers"].get(job_id, ""))
            return await asyncio.to_thread(p.read_bytes) if p.exists() else None
    
    def get_answer_path(self, job_id: str) -> Path | None:
        """Return the absolute path to the answer file for a given job_id, if it exists."""
        path_str = self._manifest["answers"].get(job_id)
        if not path_str:
            return None
        p = Path(path_str)
        return p if p.exists() else None

    async def delete_answer(self, job_id: str):
        """Remove the answer file and remove it from the cache by job id

        Args:
            job_id (str): UUID for the job as a string
        """
        async with self._lock:
            path = self._manifest["answers"].pop(job_id, None)
            await self._persist_manifest()
        if path:
            p = Path(path)
            if p.exists():
                await asyncio.to_thread(p.unlink)

    async def set_iso_path(self, job_id: str, iso_path: Path | str):
        """Set the path for the iso

        Args:
            job_id (str): UUID for the job as a string
            iso_path (Path | str): Path to the ISO file

        Raises:
            FileNotFoundError: If the provided iso_path does not exist
        """
        p = Path(iso_path).resolve()
        if not p.exists():
            raise FileNotFoundError(p)
        async with self._lock:
            self._manifest["isos"][job_id] = str(p)
            await self._persist_manifest()

    def get_iso_path(self, job_id: str) -> Path | None:
        """Return the absolute path to the ISO file for a given job_id, if it exists."""
        p = Path(self._manifest["isos"].get(job_id, ""))
        return p if p.exists() else None

    async def delete_iso(self, job_id: str, remove_file:bool=False):
        """Remove the ISO file path from the cache by job id
        
        Args:
            job_id (str): UUID for the job as a string
            remove_file (bool): If True, also deletes the ISO file from disk. Defaults to False.
        """
        async with self._lock:
            path = self._manifest["isos"].pop(job_id, None)
            await self._persist_manifest()
        if remove_file and path:
            p = Path(path)
            if p.exists():
                await asyncio.to_thread(p.unlink)
