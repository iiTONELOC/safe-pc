import shutil
import aiofiles
from pathlib import Path
from sys import platform

from safe_pc.proxmox_auto_installer.iso.iso import ModifiedProxmoxISO
from safe_pc.proxmox_auto_installer.iso.extractor import repack_iso_7z, unpack_iso_7z
from safe_pc.proxmox_auto_installer.answer_file.answer_file import ProxmoxAnswerFile


def ensure_flag_file(path: Path, flag_name: str) -> None:
    flag_file = path / flag_name
    if not flag_file.exists():
        flag_file.touch()


async def create_answer_file(
    path_to_unpacked_iso: Path,
    using_answer_file: ProxmoxAnswerFile,
    verify_flag: bool = True,
) -> str:

    if verify_flag:
        # ensure the flag 'auto-installer-capable' is present
        ensure_flag_file(path=path_to_unpacked_iso, flag_name="auto-installer-capable")

    async with aiofiles.open(
        path=path_to_unpacked_iso / "tmp" / "answer.toml", mode="w"
    ) as f:
        await f.write(using_answer_file.to_toml_str().strip())


async def create_auto_installer_mode_file(
    path_to_unpacked_iso: Path,
    path_to_answer_file: str,
    verify_flag: bool = True,
) -> str:

    toml_str = f"""
    mode = "file"
    
    [file]
    path = "{path_to_answer_file.name}"
    """

    if verify_flag:
        # ensure the flag 'auto-installer-capable' is present
        ensure_flag_file(path=path_to_unpacked_iso, flag_name="auto-installer-capable")

    async with aiofiles.open(
        path=path_to_unpacked_iso / "auto-installer-mode.toml", mode="w"
    ) as f:
        await f.write(toml_str.strip())


async def modify_iso(iso: ModifiedProxmoxISO, answer_file: ProxmoxAnswerFile) -> str:
    print("Modifying ISO... (not yet implemented)")
    # 1. Extract the ISO contents
    if platform == "win32":
        await unpack_iso_7z(
            iso_path=iso.base_iso.iso_path,
            dest_path=iso.base_iso.iso_dir / "extracted",
        )
    else:
        print("ISO modification on a Unix-like system is not yet implemented.")

    # 2. Modify the extracted contents
    # await create_answer_file(  # Also creates the auto-installer-capable flag file
    #     path_to_unpacked_iso=iso.extracted_iso_dir,
    #     using_answer_file=answer_file,
    # )
    await create_auto_installer_mode_file(
        path_to_unpacked_iso=iso.extracted_iso_dir,
        path_to_answer_file="/tmp/answer.toml",
        verify_flag=True,
    )

    # 3. Unpack the initrd.img from the boot directory
    await unpack_iso_7z(
        iso_path=iso.extracted_iso_dir / "boot" / "initrd.img",
        dest_path=iso.extracted_ram_disk.parent,
    )

    # 4. Add the answer file, into the unpacked's tmp directory
    await create_answer_file(
        path_to_unpacked_iso=iso.extracted_ram_disk.parent,
        using_answer_file=answer_file,
        verify_flag=False,
    )
    # 5. Add our discovery script to the root of the unpacked initrd
    discovery_script_path = Path(__file__).resolve().parent / "discovery.sh"
    shutil.copy(
        src=discovery_script_path,
        dst=iso.extracted_ram_disk.parent / "discovery.sh",
    )
    # 6. Modify the installer (init) to call our script on mount of the installation iso
    # find the line where INSTALLER_SQFS = "/mnt/WHATEVER", after that line, add
    # echo "[*] Running discovery script..."
    # chmod x+ /discovery.sh
    # /discovery.sh
    init_file_path = iso.extracted_ram_disk.parent / "init"
    async with aiofiles.open(path=init_file_path, mode="r") as f:
        init_contents = await f.readlines()
    for i, line in enumerate(init_contents):
        if line.strip().startswith("INSTALLER_SQFS="):
            init_contents.insert(i + 1, '\necho "[*] Running discovery script..."\n')
            init_contents.insert(i + 2, "chmod +x /discovery.sh\n")
            init_contents.insert(i + 3, "/discovery.sh\n")
            init_contents.insert(i + 4, 'echo "[*] Discovery script finished."\n')
            break
    # 7. Repack the initrd.img
    if platform == "win32":
        await repack_iso_7z(
            source_dir=iso.extracted_ram_disk.parent,
            output_iso=iso.repacked_ram_disk,
        )
    else:
        print("ISO modification on a Unix-like system is not yet implemented.")
    # 8. Replace the initrd.img in the extracted ISO's boot directory
    shutil.copy(
        src=iso.repacked_ram_disk,
        dst=iso.extracted_iso_dir / "boot" / "initrd.img",
    )
    # 9. Repack the ISO
    if platform == "win32":
        await repack_iso_7z(
            source_dir=iso.extracted_iso_dir,
            output_iso=iso.repacked_iso_dir,
        )
    else:
        print("ISO modification on a Unix-like system is not yet implemented.")

    return iso.repacked_iso_dir
