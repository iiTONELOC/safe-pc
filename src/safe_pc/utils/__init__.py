import os
from safe_pc.utils.crypto import (
    TempKeyFile,
    compute_sha256,
    compute_sha512,
    verify_sha256,
    verify_sha512,
    validate_sha256,
    validate_sha512,
    password_entropy,
    SAFE_PC_CERT_DEFAULTS,
    is_high_entropy_password,
    generate_self_signed_cert,
)

from safe_pc.utils.utils import (
    CmdResult,
    IS_VERBOSE,
    IS_TESTING,
    CommandError,
    get_local_ip,
    run_command_async,
    calculate_percentage,
    handle_keyboard_interrupt,

)

from safe_pc.utils.logs import (
    setup_logging,
)

__all__ = [
    "CmdResult",
    "CommandError",
    "IS_VERBOSE",
    "IS_TESTING",
    "get_local_ip",
    "TempKeyFile",
    "verify_sha256",
    "verify_sha512",
    "setup_logging",
    "compute_sha256",
    "compute_sha512",
    "validate_sha256",
    "validate_sha512",
    "password_entropy",
    "run_command_async",
    "calculate_percentage",
    "SAFE_PC_CERT_DEFAULTS",
    "is_high_entropy_password",
    "generate_self_signed_cert",
    "handle_keyboard_interrupt",
]

if os.name == "nt":
    from safe_pc.utils.crypto.dpapi import (
        write_dpapi_protected_key,
        read_dpapi_protected_key,
    )

    __all__.append("read_dpapi_protected_key")
    __all__.append("write_dpapi_protected_key")