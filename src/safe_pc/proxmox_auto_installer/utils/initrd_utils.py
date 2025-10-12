from time import time
from io import BytesIO
from pathlib import Path
from logging import getLogger
from collections.abc import Iterable, Set
from asyncio import to_thread as aio_to_thread
from gzip import decompress as gzip_decompress
from os import chdir, getcwd, walk as os_walk, chmod
from json import dumps as json_dumps, loads as json_loads
from stat import S_ISDIR, S_ISLNK, S_IMODE, S_IFDIR, S_IFLNK, S_IFREG

from zstandard import ZstdCompressor, ZstdDecompressor

LOGGER = getLogger("safe_pc.proxmox_auto_installer.utils.initrd_utils")
CPIO_HEADER_LEN = 110
META_FILE = ".cpio_metadata.json"


def _is_text_shell_script(name: str, data: bytes) -> bool:
    return (
        name == "init"
        or name.endswith(".sh")
        or (data.startswith(b"#!") and b"/sh" in data.splitlines()[:1][0])
    )


def _to_unix_lf(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def _perm_for(rel: str, is_dir: bool, is_symlink: bool, meta: dict) -> int:
    if "mode" in meta:
        m = S_IMODE(meta["mode"])
    else:
        if is_dir:
            m = 0o755
        elif is_symlink:
            m = 0o777
        else:
            m = 0o644
    if (
        rel == "init"
        or rel == "discovery.sh"
        or rel.startswith("bin/")
        or rel.startswith("sbin/")
        or rel.startswith("usr/bin/")
        or rel.startswith("usr/sbin/")
        or rel.endswith(".sh")
    ) and not is_dir:
        m |= 0o111
    return m


def _decompress_initrd_stream(initrd_path: Path) -> bytes:
    with initrd_path.open("rb") as f:
        magic = f.read(4)
        f.seek(0)
        raw = f.read()
    if magic.startswith(b"\x1f\x8b"):
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
            metadata[name] = entry
        elif S_ISLNK(entry["mode"]):
            link_target = data[file_start:file_end].decode("utf-8", errors="ignore")
            metadata[name] = {**entry, "symlink": link_target}
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("wb") as out:
                out.write(data[file_start:file_end])
            metadata[name] = entry

        off = (file_end + 3) & ~3

    with (dest_dir / META_FILE).open("w") as f:
        f.write(json_dumps(metadata, indent=2))


def _select_cpio_root(src_dir: Path) -> Path:
    entries = list(src_dir.iterdir())
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]
    return src_dir


def _should_skip(path: Path, skip_names: Iterable[str]) -> bool:
    name = path.name.lower()
    return (name == META_FILE.lower()) or (name in skip_names)


def _build_cpio_newc_from_dir(src_dir: Path) -> bytes:
    buf = BytesIO()
    now = int(time())
    root = _select_cpio_root(Path(src_dir).resolve())

    old_cwd = getcwd()
    chdir(root)
    try:
        metadata = {}
        meta_path = Path(META_FILE)
        if meta_path.exists():
            metadata = json_loads(meta_path.read_text())

        skip_names = {META_FILE.lower()}
        written: Set[str] = set()

        def write_entry(
            name: str, full_path: Path, meta: dict, is_dir: bool, is_symlink: bool
        ):
            name = name or "."
            assert name

            if is_symlink:
                link_target = meta.get("symlink", "")
                file_bytes = link_target.encode("utf-8")
            elif is_dir:
                file_bytes = b""
            else:
                b = full_path.read_bytes()
                if _is_text_shell_script(name, b):
                    b = _to_unix_lf(b)
                file_bytes = b
            fsize = len(file_bytes)

            perm = _perm_for(name, is_dir, is_symlink, meta)
            mode = perm | (S_IFDIR if is_dir else S_IFLNK if is_symlink else S_IFREG)

            ino = meta.get("ino", 0)
            uid = meta.get("uid", 0)
            gid = meta.get("gid", 0)
            nlink = meta.get("nlink", 1)
            mtime = meta.get("mtime", now)
            devmajor = meta.get("devmajor", 0)
            devminor = meta.get("devminor", 0)
            rdevmajor = meta.get("rdevmajor", 0)
            rdevminor = meta.get("rdevminor", 0)

            name_bytes = name.encode("utf-8") + b"\x00"
            header = (
                "070701"
                + f"{ino:08x}{mode:08x}{uid:08x}{gid:08x}{nlink:08x}{mtime:08x}"
                + f"{fsize:08x}{devmajor:08x}{devminor:08x}{rdevmajor:08x}{rdevminor:08x}"
                + f"{len(name_bytes):08x}{0:08x}"
            ).encode("ascii")

            buf.write(header)
            buf.write(name_bytes)
            pad = (4 - ((CPIO_HEADER_LEN + len(name_bytes)) % 4)) % 4
            if pad:
                buf.write(b"\x00" * pad)
            if fsize:
                buf.write(file_bytes)
                fpad = (4 - (fsize % 4)) % 4
                if fpad:
                    buf.write(b"\x00" * fpad)

        write_entry(
            ".", Path("."), metadata.get(".", {}), is_dir=True, is_symlink=False
        )
        written.add(".")

        for root_str, dirs, files in os_walk("."):
            root_p = Path(root_str)

            for d in dirs:
                full = root_p / d
                if _should_skip(full, skip_names):
                    continue
                rel = full.as_posix().lstrip("./") or "."
                if rel in written:
                    continue
                meta = metadata.get(rel, {})
                write_entry(rel, full, meta, is_dir=True, is_symlink=False)
                written.add(rel)

            for f in files:
                full = root_p / f
                if _should_skip(full, skip_names):
                    continue
                rel = full.as_posix().lstrip("./") or "."
                if rel in written:
                    continue
                meta = metadata.get(rel, {})
                is_symlink = "symlink" in meta
                write_entry(rel, full, meta, is_dir=False, is_symlink=is_symlink)
                written.add(rel)

        for rel, meta in metadata.items():
            if "symlink" not in meta:
                continue
            reln = rel or "."
            if reln in written:
                continue
            p = Path(reln)
            parents = [Path(*p.parts[:i]) for i in range(1, len(p.parts))]
            for d in parents:
                drel = d.as_posix().lstrip("./") or "."
                if drel != "." and drel not in written:
                    write_entry(
                        drel,
                        Path(drel),
                        metadata.get(drel, {}),
                        is_dir=True,
                        is_symlink=False,
                    )
                    written.add(drel)
            write_entry(reln, Path(reln), meta, is_dir=False, is_symlink=True)
            written.add(reln)

        name_bytes = b"TRAILER!!!\x00"
        trailer = (
            "070701" + f"{0:08x}" * 11 + f"{len(name_bytes):08x}" + f"{0:08x}"
        ).encode("ascii")
        assert len(trailer) == 110
        buf.write(trailer)
        buf.write(name_bytes)
        pad = (4 - ((CPIO_HEADER_LEN + len(name_bytes)) % 4)) % 4
        if pad:
            buf.write(b"\x00" * pad)

    finally:
        chdir(old_cwd)

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
    try:
        cpio_bytes = await aio_to_thread(_build_cpio_newc_from_dir, src_dir)
        zbytes = await aio_to_thread(_compress_initrd_zstd, cpio_bytes, zstd_level)

        out_path.parent.mkdir(parents=True, exist_ok=True)
        chmod(out_path.parent, 0o755)
        if not out_path.exists():
            out_path.touch()
            chmod(out_path, 0o644)

        await aio_to_thread(out_path.write_bytes, zbytes)
        return True
    except Exception as e:
        LOGGER.exception(f"repack_initrd failed: {e}")
        return False
