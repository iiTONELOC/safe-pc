import asyncio
from pathlib import Path
from dataclasses import dataclass
from typing import Mapping, Optional, Sequence, Union

# ---------- Tool paths ----------
TOOLS_DIR = Path(__file__).resolve().parents[4] / "tools"
XORRISO = TOOLS_DIR / "xorriso.exe"


# ---------- Runner ----------
@dataclass
class CmdResult:
    stdout: str
    stderr: str
    returncode: int


class CommandError(RuntimeError):
    def __init__(self, args: Sequence[str], rc: int, stdout: str, stderr: str):
        super().__init__(f"Command failed ({rc}): {' '.join(map(str, args))}")
        self.args_list = list(args)
        self.returncode = rc
        self.stdout = stdout
        self.stderr = stderr


async def run(
    *args: Union[str, Path],
    cwd: Optional[Union[str, Path]] = None,
    env: Optional[Mapping[str, str]] = None,
    check: bool = True,
) -> CmdResult:
    cmd = tuple(str(a) for a in args)
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(cwd) if cwd else None,
        env=dict(env) if env else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout_b, stderr_b = await proc.communicate()
    except (asyncio.CancelledError, asyncio.TimeoutError):
        proc.kill()
        await proc.communicate()
        raise
    rc = proc.returncode
    stdout = stdout_b.decode(errors="replace")
    stderr = stderr_b.decode(errors="replace")
    if check and rc != 0:
        raise CommandError(cmd, rc, stdout, stderr)
    return CmdResult(stdout, stderr, rc)


def ensure_paths_exist(*paths: Path) -> None:
    missing = [p for p in paths if not p.exists()]
    if missing:
        short = ", ".join(str(p) for p in missing[:3])
        more = "…" if len(missing) > 3 else ""
        raise FileNotFoundError(f"Required tool(s) not found: {short}{more}")


async def xorriso_extract_iso(
    iso_path: Union[str, Path], out_dir: Union[str, Path]
) -> bool:
    iso = Path(iso_path).resolve()
    outp = Path(out_dir).resolve()
    outp.mkdir(parents=True, exist_ok=True)
    ensure_paths_exist(XORRISO)

    cwd = Path(__file__).resolve().parents[4]
    rel_iso = iso.relative_to(cwd)
    rel_outp = outp.relative_to(cwd)

    args = (
        str(XORRISO),
        "-osirrox",
        "on",
        "-indev",
        str(rel_iso),
        "-find",
        "/",
        "-type",
        "l",
        "-exec",
        "rm",
        "--",
        "-extract",
        "/",
        str(rel_outp),
        "-rollback_end",
    )
    await run(*args, cwd=cwd, check=False)
    return any(outp.iterdir())


async def xorriso_repack_iso(unpacked_iso_dir: Path, output_iso: Path) -> bool:
    ensure_paths_exist(XORRISO)
    cwd = Path(__file__).resolve().parents[4]

    src = (Path(unpacked_iso_dir).resolve().relative_to(cwd)).as_posix()
    outp = (Path(output_iso).resolve().relative_to(cwd)).as_posix()

    src_abs = Path(cwd) / src
    # hard fail if core payloads are missing
    for must in (
        "pve-base.squashfs",
        "pve-installer.squashfs",
        "boot/grub/i386-pc/eltorito.img",
    ):
        if not (src_abs / must).exists():
            raise FileNotFoundError(f"Missing in source: {src_abs / must}")

    args = (
        str(XORRISO),
        "-as",
        "mkisofs",
        "-r",  # like your Linux cmd
        "-J",
        "-joliet-long",
        "-V",
        "PVE",
        "-o",
        outp,
        "-isohybrid-gpt-basdat",
        "-eltorito-boot",
        "boot/grub/i386-pc/eltorito.img",
        "-no-emul-boot",
        "-boot-load-size",
        "4",
        "-boot-info-table",
        src,
    )
    await run(*args, cwd=cwd, check=True)

    # quick presence check
    listed = (
        await run(
            str(XORRISO),
            "-indev",
            outp,
            "-lsl",
            "/",
            "--",
            "-abort_on",
            "NEVER",
            cwd=cwd,
            check=False,
        )
    ).stdout
    if ("pve-base.squashfs" not in listed) or ("pve-installer.squashfs" not in listed):
        raise RuntimeError("Rebuilt ISO missing squashfs payloads")
    return True
