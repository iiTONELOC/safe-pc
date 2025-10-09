import uuid
import shutil
import aiofiles
from time import time
from io import BytesIO
from pathlib import Path
from logging import getLogger
from os import chmod, walk as os_walk
from asyncio import to_thread as aio_to_thread
from gzip import decompress as gzip_decompress
from json import dumps as json_dumps, loads as json_loads
from stat import S_ISDIR, S_ISLNK, S_IFDIR, S_IFLNK, S_IFREG

from zstandard import ZstdCompressor, ZstdDecompressor

LOGGER = getLogger("safe_pc.proxmox_auto_installer.utils.initrd_utils")
CPIO_HEADER_LEN = 110  # "newc" fixed header length
META_FILE = ".cpio_metadata.json"

# https://www.systutorials.com/docs/linux/man/5-cpio/


def _decompress_initrd_stream(initrd_path: Path) -> bytes:
    with initrd_path.open("rb") as f:
        magic = f.read(4)
        f.seek(0)
        raw = f.read()

    if magic.startswith(b"\x1f\x8b"):  # gzip
        return gzip_decompress(raw)
    else:
        dctx = ZstdDecompressor()
        with dctx.stream_reader(BytesIO(raw)) as reader:
            return reader.read()


def _parse_cpio_newc_to_dir(cpio_bytes: bytes, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    data = cpio_bytes
    off = 0
    metadata = {}

    while off < len(data):
        if off + CPIO_HEADER_LEN > len(data):
            break
        hdr = data[off : off + CPIO_HEADER_LEN]
        magic = hdr[:6].decode("ascii", errors="strict")
        if magic != "070701":
            raise ValueError(f"Unsupported cpio format magic={magic}")

        def h(i, j):
            return int(hdr[i:j].decode("ascii"), 16)

        entry = {
            "ino": h(6, 14),
            "mode": h(14, 22),
            "uid": h(22, 30),
            "gid": h(30, 38),
            "nlink": h(38, 46),
            "mtime": h(46, 54),
            "filesize": h(54, 62),
            "devmajor": h(62, 70),
            "devminor": h(70, 78),
            "rdevmajor": h(78, 86),
            "rdevminor": h(86, 94),
            "namesize": h(94, 102),
            "check": h(102, 110),
        }

        name_start = off + CPIO_HEADER_LEN
        name_end = name_start + entry["namesize"]
        name = data[name_start : name_end - 1].decode("utf-8", errors="strict")
        if name == "TRAILER!!!":
            break

        file_start = (name_end + 3) & ~3
        file_end = file_start + entry["filesize"]

        target = dest_dir / name
        if S_ISDIR(entry["mode"]):
            target.mkdir(parents=True, exist_ok=True)
        elif S_ISLNK(entry["mode"]):
            link_target = data[file_start:file_end].decode("utf-8", errors="ignore")
            metadata[str(target)] = {**entry, "symlink": link_target}
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("wb") as out:
                out.write(data[file_start:file_end])
            metadata[str(target)] = entry

        off = (file_end + 3) & ~3

    # save metadata
    with (dest_dir / META_FILE).open("w") as f:
        json_str = json_dumps(metadata, indent=2)
        f.write(json_str)


def _build_cpio_newc_from_dir(src_dir: Path) -> bytes:
    buf = BytesIO()
    now = int(time())

    # load metadata if exists
    meta_path = src_dir / META_FILE
    metadata = {}
    if meta_path.exists():
        metadata = json_loads(meta_path.read_text())

    def write_entry(
        name: str, full_path: Path, meta: dict, is_dir: bool, is_symlink: bool
    ):
        st = full_path.lstat() if full_path.exists() else None
        fsize = 0
        file_bytes = b""

        # restore metadata or fallback to stat
        mode = meta.get("mode", (st.st_mode if st else 0o100644))
        ino = meta.get("ino", 0)
        uid = meta.get("uid", 0)
        gid = meta.get("gid", 0)
        nlink = meta.get("nlink", 1)
        mtime = meta.get("mtime", now)
        devmajor = meta.get("devmajor", 0)
        devminor = meta.get("devminor", 0)
        rdevmajor = meta.get("rdevmajor", 0)
        rdevminor = meta.get("rdevminor", 0)

        if is_dir:
            mode = (mode & 0o7777) | S_IFDIR
        elif is_symlink:
            mode = (mode & 0o7777) | S_IFLNK
            link_target = meta.get("symlink", "")
            file_bytes = link_target.encode("utf-8")
            fsize = len(file_bytes)
        else:
            mode = (mode & 0o7777) | S_IFREG
            file_bytes = full_path.read_bytes()
            fsize = len(file_bytes)

        name_bytes = name.encode("utf-8") + b"\x00"

        header = (
            "070701"
            + f"{ino:08x}"
            + f"{mode:08x}"
            + f"{uid:08x}"
            + f"{gid:08x}"
            + f"{nlink:08x}"
            + f"{mtime:08x}"
            + f"{fsize:08x}"
            + f"{devmajor:08x}"
            + f"{devminor:08x}"
            + f"{rdevmajor:08x}"
            + f"{rdevminor:08x}"
            + f"{len(name_bytes):08x}"
            + f"{0:08x}"
        ).encode("ascii")
        buf.write(header)
        buf.write(name_bytes)
        pad = (4 - ((CPIO_HEADER_LEN + len(name_bytes)) % 4)) % 4
        if pad:
            buf.write(b"\x00" * pad)

        if fsize > 0:
            buf.write(file_bytes)
            fpad = (4 - (fsize % 4)) % 4
            if fpad:
                buf.write(b"\x00" * fpad)

    for root, dirs, files in os_walk(src_dir):
        root_p = Path(root)
        rel_root = root_p.relative_to(src_dir)
        for d in dirs:
            full = root_p / d
            rel = str((rel_root / d).as_posix())
            meta = metadata.get(str(full), {})
            write_entry(rel + "/", full, meta, is_dir=True, is_symlink=False)
        for f in files:
            if f == META_FILE:
                continue
            full = root_p / f
            rel = str((rel_root / f).as_posix())
            meta = metadata.get(str(full), {})
            is_symlink = "symlink" in meta
            write_entry(rel, full, meta, is_dir=False, is_symlink=is_symlink)

    # Trailer
    name_bytes = b"TRAILER!!!\x00"
    trailer = (
        "070701" + f"{0:08x}" * 13 + f"{len(name_bytes):08x}" + f"{0:08x}"
    ).encode("ascii")
    buf.write(trailer)
    buf.write(name_bytes)
    # calculate padding for trailer, should be 0, 1, 2, or 3
    pad = (4 - ((CPIO_HEADER_LEN + len(name_bytes)) % 4)) % 4
    if pad:
        buf.write(b"\x00" * pad)

    return buf.getvalue()


def _compress_initrd_zstd(cpio_bytes: bytes, level: int = 19) -> bytes:
    return ZstdCompressor(level=level).compress(cpio_bytes)


async def unpack_initrd(initrd_path: Path, dest_dir: Path) -> bool:
    try:
        data = await aio_to_thread(_decompress_initrd_stream, initrd_path)
        await aio_to_thread(_parse_cpio_newc_to_dir, data, dest_dir)
        return True
    except Exception as e:
        LOGGER.exception(f"unpack_initrd failed: {e}")
        return False


async def repack_initrd(src_dir: Path, out_path: Path, zstd_level: int = 19) -> bool:
    """
    Async: Build newc-cpio from src_dir and zstd-compress to out_path.
    Handles Windows overwrite issues cleanly.
    """

    try:
        # Build new cpio archive and compress it
        cpio_bytes = await aio_to_thread(_build_cpio_newc_from_dir, src_dir)
        zbytes = await aio_to_thread(_compress_initrd_zstd, cpio_bytes, zstd_level)

        out_path.parent.mkdir(parents=True, exist_ok=True)

        # Write to a temporary file first
        tmp_file = out_path.parent / f".tmp_{uuid.uuid4().hex}"
        await aio_to_thread(tmp_file.write_bytes, zbytes)

        # On Windows, make sure to remove the old file first to avoid PermissionError
        if out_path.exists():
            try:
                out_path.unlink()
            except PermissionError:
                # Retry with read-only attribute removal if needed
                chmod(out_path, 0o666)
                out_path.unlink()

        # Move the temp file into place
        shutil.move(str(tmp_file), str(out_path))

        return True

    except Exception as e:
        LOGGER.exception(f"repack_initrd failed: {e}")
        return False
