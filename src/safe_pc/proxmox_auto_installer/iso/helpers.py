
from pathlib import Path
from safe_pc.utils import get_local_ip
#from safe_pc.utils.crypto.crypto import cert_sha256_fingerprint
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

    answer_file_path = path_to_unpacked_iso / "answer.toml"
    answer_file_path.touch(exist_ok=True)

    answer_file_path.write_text(using_answer_file)
    answer_file_path.chmod(0o644)
    return answer_file_path.__str__()


# async def _get_cert_fingerprint() -> str:
#     # cert folder is at the project root/certs
#     cert_path = Path(__file__).parents[4] / "certs" / "safe-pc-cert.pem"
#     if not cert_path.exists():
#         raise FileNotFoundError(f"Certificate file not found: {cert_path}")

#     return await cert_sha256_fingerprint(cert_path.__str__())


async def create_auto_installer_mode_file(
    path_to_unpacked_iso: Path,
    job_id: str,
    verify_flag: bool = True,
) -> str:

    toml_str = f"""
    mode = "http"
    
    [http]
    url = "http://{get_local_ip()}:33007/api/prox/answer_file/{job_id}"
    """

    if verify_flag:
        # ensure the flag 'auto-installer-capable' is present
        ensure_flag_file(path=path_to_unpacked_iso, flag_name="auto-installer-capable")

    auto_file = path_to_unpacked_iso / "auto-installer-mode.toml"
    auto_file.touch(exist_ok=True)
    auto_file.write_text(toml_str.strip())
    auto_file.chmod(0o644)
    return auto_file.__str__()



