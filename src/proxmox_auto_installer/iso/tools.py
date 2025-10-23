import asyncio, os, tempfile, shlex, stat
from shutil import copy2
from pathlib import Path
from logging import getLogger
from utm.__main__ import run_command_async

XORRISO = "xorriso"
LOGGER = getLogger("safe_pc.proxmox_auto_installer.iso:tools" if __name__ == "__main__" else __name__)


# ---------- helpers ----------
async def _ensure_tree_writable(root: Path) -> None:
    """Best-effort: ensure user can write/execute under root."""
    root = Path(root).resolve()
    # Fast path: if root already writable, skip expensive ops
    if os.access(root, os.W_OK | os.X_OK):
        return
    # Use chmod -R u+rwX (portable and fast)
    cmd = f"chmod -R u+rwX {shlex.quote(str(root))}"
    res = await run_command_async("bash", "-lc", cmd, cwd=None, check=False)
    if res.returncode != 0:
        LOGGER.warning("chmod -R failed; attempting per-dir fix in Python")
        # Fallback: walk and chmod what we can (in case shell denied)
        for dirpath, _, filenames in os.walk(root):
            p = Path(dirpath)
            try:
                m = p.stat().st_mode
                os.chmod(p, m | stat.S_IWUSR | stat.S_IXUSR)
            except PermissionError:
                pass
            for name in filenames:
                fp = p / name
                try:
                    m = fp.stat().st_mode
                    os.chmod(fp, m | stat.S_IWUSR)
                except PermissionError:
                    pass
    # Final check (non-fatal if some subpaths remain RO; we only need parent dirs)
    if not os.access(root, os.W_OK | os.X_OK):
        LOGGER.warning("Root dir still not writable by user: %s", root)


def _ensure_parent_writable(dst: Path) -> None:
    parent = Path(dst).parent
    # Need write+exec on parent to create temp and replace atomically
    if not os.access(parent, os.W_OK | os.X_OK):
        try:
            mode = parent.stat().st_mode
            os.chmod(parent, mode | stat.S_IWUSR | stat.S_IXUSR)
        except PermissionError as e:
            raise PermissionError(f"Parent not writable: {parent}") from e


# ---------- ISO ----------
async def xorriso_extract_iso(iso_path: str | Path, out_dir: str | Path) -> bool:
    iso = Path(iso_path).resolve(strict=True)
    outp = Path(out_dir).resolve()
    outp.mkdir(parents=True, exist_ok=True)

    LOGGER.debug(f"Extracting ISO {iso} to {outp}")
    args = (
        str(XORRISO),
        "-osirrox",
        "on",
        "-indev",
        str(iso),
        "-extract",
        "/",
        str(outp),
    )
    res = await run_command_async(*args, cwd=None, check=False)
    if res.returncode != 0:
        LOGGER.error("xorriso extract failed: rc=%s", res.returncode)
        return False

    # Make extracted tree writable so later steps can modify files in-place
    await _ensure_tree_writable(outp)
    return any(outp.iterdir())


async def xorriso_repack_iso(unpacked_iso_dir: Path, output_iso: Path) -> bool:
    src_abs = Path(unpacked_iso_dir).resolve(strict=True)
    out_iso = Path(output_iso).resolve()
    out_iso.parent.mkdir(parents=True, exist_ok=True)

    for must in ("pve-base.squashfs", "pve-installer.squashfs", "boot/grub/i386-pc/eltorito.img"):
        if not (src_abs / must).exists():
            raise FileNotFoundError(f"Missing in source: {src_abs / must}")

    args = (
        str(XORRISO),
        "-as",
        "mkisofs",
        "-r",
        "-J",
        "-joliet-long",
        "-V",
        "PVE",
        "-o",
        str(out_iso),
        "-isohybrid-gpt-basdat",
        "-eltorito-boot",
        "boot/grub/i386-pc/eltorito.img",
        "-no-emul-boot",
        "-boot-load-size",
        "4",
        "-boot-info-table",
        ".",
    )
    res = await run_command_async(*args, cwd=src_abs, check=False)
    LOGGER.debug(f"Repacked ISO to {out_iso}, rc={res.returncode}")
    return (res.returncode == 0) and out_iso.exists() and out_iso.stat().st_size > 0


# ---------- INITRD ----------
async def unpack_initrd(initrd_path: Path, out_dir: Path) -> bool:
    initrd = Path(initrd_path).resolve(strict=True)
    outp = Path(out_dir).resolve()
    outp.mkdir(parents=True, exist_ok=True)

    cmd = f"zstdcat {shlex.quote(str(initrd))} | cpio -idmv"
    res = await run_command_async("bash", "-lc", cmd, cwd=outp, check=False)
    LOGGER.info(f"Unpacked initrd {initrd} to {outp}, rc={res.returncode}")

    return any(outp.iterdir())


async def repack_initrd(unpacked_initrd_dir: Path, output_initrd: Path) -> bool:
    src_abs = Path(unpacked_initrd_dir).resolve(strict=True)
    out_initrd = Path(output_initrd).resolve()
    out_initrd.parent.mkdir(parents=True, exist_ok=True)

    if not (src_abs / "init").exists():
        raise FileNotFoundError(f"Missing in source: {src_abs / 'init'}")

    cmd = f"find . | cpio -o -H newc | zstd -19 -T0 > {shlex.quote(str(out_initrd))}"
    res = await run_command_async("bash", "-lc", cmd, cwd=src_abs, check=False)
    LOGGER.debug(f"Repacked initrd to {out_initrd}, rc={res.returncode}")
    return (res.returncode == 0) and out_initrd.exists() and out_initrd.stat().st_size > 0


# ---------- FILE OPS ----------
def _atomic_copy2(src: Path, dst: Path) -> None:
    dst = Path(dst)
    _ensure_parent_writable(dst)  # <-- ensure we can create temp alongside dst

    dst_parent = dst.parent
    fd, tmp = tempfile.mkstemp(dir=dst_parent, prefix=dst.name + ".tmp.")
    os.close(fd)
    try:
        copy2(src, tmp)
        os.replace(tmp, dst)  # atomic on same fs
    finally:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass


async def replace_initrd_file(new_file: Path, dest_file: Path) -> bool:
    new_file = Path(new_file).resolve(strict=True)
    dest_file = Path(dest_file).resolve(strict=True)
    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _atomic_copy2, new_file, dest_file)
        return True
    except Exception as e:
        LOGGER.exception("Failed to replace %s with %s: %s", dest_file, new_file, e)
        return False
