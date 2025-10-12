import os
import io
import json
import shutil
import hashlib
import asyncio
from time import time
from uuid import UUID
from pathlib import Path
from typing import Any
from logging import getLogger

LOGGER = getLogger(__name__)


CACHED_DATA_DIR = Path(__file__).parents[4] / "data" / "cached_answers"

class CacheManager:
    """
    Content-addressable cache plus explicit mappings for:
      - answers:   job_id -> answer-file hash -> path
      - iso paths: job_id -> iso absolute path

    Layout:
      <cache_dir>/data/<sha256>
      <cache_dir>/manifest.json
    """

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
            # generic answer store (kept for compatibility)
            "by_job": {},        # job_id -> hash
            "by_hash": {},       # hash  -> path
            # iso to job mapping (non-content-addressable)
            "iso_by_job": {},    # job_id -> iso path
        }

    # ---------- Initialization / I/O helpers ----------

    @classmethod
    async def new(cls) -> "CacheManager":
        self = cls(CACHED_DATA_DIR)
        await asyncio.to_thread(self.data_dir.mkdir, True, exist_ok=True)
        await self._load_manifest()
        return self

    async def _load_manifest(self) -> None:
        if await asyncio.to_thread(self.manifest_path.exists):
            try:
                data = await asyncio.to_thread(self.manifest_path.read_text, encoding="utf-8")
                loaded = json.loads(data)
                if loaded.get("version") == self.MANIFEST_VERSION:
                    self._manifest = loaded
                    # seed missing keys for forward-compat
                    self._manifest.setdefault("iso_by_job", {})
                    self._manifest.setdefault("by_job", {})
                    self._manifest.setdefault("by_hash", {})
                else:
                    LOGGER.warning("Manifest version mismatch; reinitializing manifest.")
                    await self._persist_manifest()
            except Exception as e:
                LOGGER.exception(f"Failed to read manifest; reinitializing. Error: {e}")
                await self._persist_manifest()
        else:
            await self._persist_manifest()

    async def _persist_manifest(self) -> None:
        self._manifest["updated_at"] = time()
        tmp = self.manifest_path.with_suffix(".json.tmp")
        txt = json.dumps(self._manifest, indent=2, ensure_ascii=False)
        await asyncio.to_thread(tmp.write_text, txt, "utf-8")
        await asyncio.to_thread(os.replace, tmp, self.manifest_path)

    # ---------- Hashing ----------

    @staticmethod
    def _sha256_stream(fobj: io.BufferedReader, chunk_size: int = 1024 * 1024) -> str:
        h = hashlib.sha256()
        for chunk in iter(lambda: fobj.read(chunk_size), b""):
            h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _sha256_bytes(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def _hash_file_path(self, path: Path) -> str:
        with path.open("rb") as f:
            return self._sha256_stream(f)

    # ---------- Generic content-addressable API (unchanged for back-compat) ----------

    async def put_bytes(self, job_id: str | UUID, data: bytes) -> tuple[str, Path]:
        jid = str(job_id)
        digest = await asyncio.to_thread(self._sha256_bytes, data)
        dest = self.data_dir / digest
        async with self._lock:
            if not dest.exists():
                tmp = dest.with_suffix(".tmp")
                await asyncio.to_thread(tmp.write_bytes, data)
                await asyncio.to_thread(os.replace, tmp, dest)
            self._manifest["by_job"][jid] = digest
            self._manifest["by_hash"][digest] = str(dest)
            await self._persist_manifest()
        return digest, dest

    async def put_file(self, job_id: str | UUID, src_path: Path | str, move: bool = False) -> tuple[str, Path]:
        jid = str(job_id)
        src = Path(src_path).resolve()
        if not await asyncio.to_thread(src.exists):
            raise FileNotFoundError(f"Source file not found: {src}")
        digest = await asyncio.to_thread(self._hash_file_path, src)
        dest = self.data_dir / digest
        async with self._lock:
            if not dest.exists():
                if move:
                    await asyncio.to_thread(shutil.move, str(src), str(dest))
                else:
                    await asyncio.to_thread(shutil.copy2, str(src), str(dest))
            self._manifest["by_job"][jid] = digest
            self._manifest["by_hash"][digest] = str(dest)
            await self._persist_manifest()
        return digest, dest

    async def get_path_by_job(self, job_id: str | UUID) -> Path | None:
        jid = str(job_id)
        async with self._lock:
            digest = self._manifest["by_job"].get(jid)
            if not digest:
                return None
            p = Path(self._manifest["by_hash"].get(digest, ""))
        return p if p.exists() else None

    async def get_path_by_hash(self, digest: str) -> Path | None:
        async with self._lock:
            p = Path(self._manifest["by_hash"].get(digest, ""))
        return p if p.exists() else None

    async def read_bytes_by_job(self, job_id: str | UUID) -> bytes | None:
        p = await self.get_path_by_job(job_id)
        if not p:
            return None
        return await asyncio.to_thread(p.read_bytes)

    async def read_bytes_by_hash(self, digest: str) -> bytes | None:
        p = await self.get_path_by_hash(digest)
        if not p:
            return None
        return await asyncio.to_thread(p.read_bytes)

    async def get_job_by_hash(self, digest: str) -> list[str]:
        async with self._lock:
            return [j for j, h in self._manifest["by_job"].items() if h == digest]

    async def link_job_to_hash(self, job_id: str | UUID, digest: str) -> Path | None:
        jid = str(job_id)
        async with self._lock:
            path_str = self._manifest["by_hash"].get(digest)
            if not path_str:
                return None
            self._manifest["by_job"][jid] = digest
            await self._persist_manifest()
            return Path(path_str)

    async def exists(self, digest: str) -> bool:
        p = await self.get_path_by_hash(digest)
        return p is not None

    async def list_jobs(self) -> dict[str, str]:
        async with self._lock:
            return dict(self._manifest["by_job"])

    async def list_hashes(self) -> dict[str, str]:
        async with self._lock:
            return dict(self._manifest["by_hash"])

    async def integrity_check(self, sample: int | None = None) -> dict[str, Any]:
        async with self._lock:
            items = list(self._manifest["by_hash"].items())
        if sample is not None:
            items = items[: max(0, sample)]
        mismatches: list[tuple[str, str]] = []
        missing: list[str] = []
        for digest, path_str in items:
            p = Path(path_str)
            if not p.exists():
                missing.append(digest)
                continue
            try:
                new_digest = await asyncio.to_thread(self._hash_file_path, p)
                if new_digest != digest:
                    mismatches.append((digest, new_digest))
            except Exception as e:
                LOGGER.warning(f"Integrity check error for {p}: {e}")
        return {"mismatches": mismatches, "missing": missing}

    # ---------- ANSWER-FILE API (explicit, by job_id) ----------

    async def put_answer_bytes(self, job_id: str | UUID, data: bytes) -> tuple[str, Path]:
        """Store answer-file bytes and link to job_id. Returns (hash, path)."""
        jid = str(job_id)
        digest = await asyncio.to_thread(self._sha256_bytes, data)
        dest = self.data_dir / digest
        async with self._lock:
            if not dest.exists():
                tmp = dest.with_suffix(".tmp")
                await asyncio.to_thread(tmp.write_bytes, data)
                await asyncio.to_thread(os.replace, tmp, dest)
            self._manifest["by_job"][jid] = digest
            self._manifest["by_hash"][digest] = str(dest)
            await self._persist_manifest()
        return digest, dest

    async def put_answer_file(self, job_id: str | UUID, src_path: Path | str, move: bool = False) -> tuple[str, Path]:
        """Ingest an answer-file by content and link to job_id."""
        jid = str(job_id)
        src = Path(src_path).resolve()
        if not await asyncio.to_thread(src.exists):
            raise FileNotFoundError(f"Answer file not found: {src}")
        digest = await asyncio.to_thread(self._hash_file_path, src)
        dest = self.data_dir / digest
        async with self._lock:
            if not dest.exists():
                if move:
                    await asyncio.to_thread(shutil.move, str(src), str(dest))
                else:
                    await asyncio.to_thread(shutil.copy2, str(src), str(dest))
            self._manifest["by_job"][jid] = digest
            self._manifest["by_hash"][digest] = str(dest)
            await self._persist_manifest()
        return digest, dest

    async def get_answer_path(self, job_id: str | UUID) -> Path | None:
        """Get the absolute path of the answer-file for this job_id."""
        jid = str(job_id)
        async with self._lock:
            digest = self._manifest["by_job"].get(jid)
            if not digest:
                return None
            p = Path(self._manifest["by_hash"].get(digest, ""))
        return p if p.exists() else None

    async def read_answer_bytes(self, job_id: str | UUID) -> bytes | None:
        """Read answer-file bytes by job_id."""
        p = await self.get_answer_path(job_id)
        return await asyncio.to_thread(p.read_bytes) if p else None

    async def link_answer_job_to_hash(self, job_id: str | UUID, digest: str) -> Path | None:
        """Link an existing cached answer (by hash) to a job_id."""
        jid = str(job_id)
        async with self._lock:
            path_str = self._manifest["by_hash"].get(digest)
            if not path_str:
                return None
            self._manifest["by_job"][jid] = digest
            await self._persist_manifest()
            return Path(path_str)

        
    async def update_answer_bytes(self, job_id: str | UUID, data: bytes) -> tuple[str, Path]:
        """Update the answer-file bytes for a given job_id; returns (new_hash, path)."""
        jid = str(job_id)
        digest = await asyncio.to_thread(self._sha256_bytes, data)
        dest = self.data_dir / digest
        async with self._lock:
            if not dest.exists():
                tmp = dest.with_suffix(".tmp")
                await asyncio.to_thread(tmp.write_bytes, data)
                await asyncio.to_thread(os.replace, tmp, dest)
            self._manifest["by_job"][jid] = digest
            self._manifest["by_hash"][digest] = str(dest)
            await self._persist_manifest()
        return digest, dest

    async def delete_by_job(self, job_id: str | UUID) -> None:
        """Remove job->answer mapping; GC file if unreferenced in answers."""
        jid = str(job_id)
        async with self._lock:
            digest = self._manifest["by_job"].pop(jid, None)
            if not digest:
                await self._persist_manifest()
                return
            still_ref = any(h == digest for h in self._manifest["by_job"].values())
            if not still_ref:
                path_str = self._manifest["by_hash"].pop(digest, None)
                if path_str:
                    p = Path(path_str)
                    try:
                        if p.exists():
                            await asyncio.to_thread(p.unlink)
                    except Exception as e:
                        LOGGER.warning(f"Failed to delete answer file {p}: {e}")
            await self._persist_manifest()

    async def delete_by_hash(self, digest: str) -> None:
        """Force-delete an answer by hash and unlink all jobs pointing to it."""
        async with self._lock:
            for j in [j for j, h in self._manifest["by_job"].items() if h == digest]:
                self._manifest["by_job"].pop(j, None)
            path_str = self._manifest["by_hash"].pop(digest, None)
            if path_str:
                p = Path(path_str)
                try:
                    if p.exists():
                        await asyncio.to_thread(p.unlink)
                except Exception as e:
                    LOGGER.warning(f"Failed to delete answer file {p}: {e}")
            await self._persist_manifest()

    # ---------- ISO path mapping API ----------

    async def set_iso_path(self, job_id: str | UUID, iso_path: Path | str, must_exist: bool = True) -> Path:
        """Record an absolute ISO path for a job_id (not hashed)."""
        jid = str(job_id)
        p = Path(iso_path).resolve()
        if must_exist and not await asyncio.to_thread(p.exists):
            raise FileNotFoundError(f"ISO path not found: {p}")
        async with self._lock:
            self._manifest["iso_by_job"][jid] = str(p)
            await self._persist_manifest()
        return p

    async def get_iso_path(self, job_id: str | UUID) -> Path | None:
        """Return the ISO path for a job_id, or None if not set/absent."""
        jid = str(job_id)
        async with self._lock:
            path_str = self._manifest["iso_by_job"].get(jid)
        if not path_str:
            return None
        p = Path(path_str)
        return p if await asyncio.to_thread(p.exists) else None

    async def read_iso_bytes(self, job_id: str | UUID) -> bytes | None:
        """Read ISO bytes by job_id (if path set and exists)."""
        p = await self.get_iso_path(job_id)
        return await asyncio.to_thread(p.read_bytes) if p else None
    

    async def delete_iso_by_job(self, job_id: str | UUID, remove_file: bool = False) -> None:
        """Remove the ISO mapping for a job_id; optionally delete the file."""
        jid = str(job_id)
        async with self._lock:
            path_str = self._manifest["iso_by_job"].pop(jid, None)
            await self._persist_manifest()
        if remove_file and path_str:
            p = Path(path_str)
            try:
                if await asyncio.to_thread(p.exists):
                    await asyncio.to_thread(p.unlink)
            except Exception as e:
                LOGGER.warning(f"Failed to delete ISO file {p}: {e}")

    async def list_iso_jobs(self) -> dict[str, str]:
        async with self._lock:
            return dict(self._manifest["iso_by_job"])
