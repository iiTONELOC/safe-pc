from enum import auto
import aiofiles
from pathlib import Path
from safe_pc.proxmox_auto_installer.answer_file.answer_file import ProxmoxAnswerFile


def ensure_flag_file(path: Path, flag_name: str) -> None:
    flag_file = path / flag_name
    if not flag_file.exists():
        flag_file.touch()


def create_answer_file(
    path_to_unpacked_iso: Path,
    using_answer_file: str,
    verify_flag: bool = True,
) -> str:

    if verify_flag:
        # ensure the flag 'auto-installer-capable' is present
        ensure_flag_file(path=path_to_unpacked_iso, flag_name="auto-installer-capable")

    answer_file_path = path_to_unpacked_iso / "tmp" / "answer.toml"
    answer_file_path.touch(exist_ok=True)

    answer_file_path.write_text(using_answer_file)
    answer_file_path.chmod(0o644)
    return answer_file_path.__str__()


def create_auto_installer_mode_file(
    path_to_unpacked_iso: Path,
    path_to_answer_file: str,
    verify_flag: bool = True,
) -> str:

    toml_str = f"""mode = "file"
    
[file]
path = "{path_to_answer_file}"
    """

    if verify_flag:
        # ensure the flag 'auto-installer-capable' is present
        ensure_flag_file(path=path_to_unpacked_iso, flag_name="auto-installer-capable")

    auto_file = path_to_unpacked_iso / "auto-installer-mode.toml"
    auto_file.touch(exist_ok=True)
    auto_file.write_text(toml_str.strip())
    auto_file.chmod(0o644)
    return auto_file.__str__()
