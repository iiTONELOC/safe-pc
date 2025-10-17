from typing import Any
from hashlib import sha256
from re import sub, MULTILINE
from proxmox_auto_installer.answer_file.disk import (
    DISK_CONFIG_DEFAULTS,
    DiskConfig,
)
from proxmox_auto_installer.answer_file._global import (
    GLOBAL_CONFIG_DEFAULTS,
    GlobalConfig,
)
from proxmox_auto_installer.answer_file.network import (
    NETWORK_CONFIG_DEFAULTS,
    NetworkConfig,
)

from pydantic import BaseModel, Field
from tomlkit import dumps as toml_dumps  # type: ignore[import]


class ProxFirstBootConfig(BaseModel):
    model_config = {"populate_by_name": True}

    source: str = "from-iso"
    ordering: str = "network-online"


class ProxmoxAnswerFile(BaseModel):
    model_config = {"populate_by_name": True}

    global_config: GlobalConfig = Field(
        ...,
        description="Global configuration settings",
        alias="global",
    )
    network: NetworkConfig = Field(
        ...,
        description="Network configuration settings",
    )
    disk_setup: DiskConfig = Field(
        ...,
        description="Disk setup configuration settings",
        alias="disk-setup",
    )
    # first_boot: ProxFirstBootConfig = Field(
    #     default_factory=ProxFirstBootConfig,
    #     description="Proxmox first boot configuration settings",
    #     alias="first-boot",
    # )

    def to_dict(self) -> dict[str, Any]:
        # ensure none values are removed
        def remove_none(d: Any) -> Any:
            if isinstance(d, dict):
                return {k: remove_none(v) for k, v in d.items() if v is not None}  # type: ignore[return-value]
            elif isinstance(d, list):
                return [remove_none(v) for v in d]  # type: ignore[return-value]
            else:
                return d

        return remove_none(self.model_dump(by_alias=True))

    def to_json(self) -> str:
        return self.model_dump_json(by_alias=True)

    def to_pretty_json(self) -> str:
        return self.model_dump_json(by_alias=True, indent=4)

    def to_toml_str(self) -> str:
        toml_str = toml_dumps(self.to_dict())
        # ensure keys are not quoted
        toml_str = sub(r'^"([^"]+)"\s*=', r"\1 =", toml_str, flags=MULTILINE)
        return toml_str

    def calculate_hash(self) -> str:
        toml_str = self.to_toml_str()
        return sha256(toml_str.encode("utf-8")).hexdigest()


def create_answer_file_from_dict(data: dict[str, Any]) -> ProxmoxAnswerFile:
    args: dict[str, Any] = {
        **{
            "global": GLOBAL_CONFIG_DEFAULTS,
            "network": NETWORK_CONFIG_DEFAULTS,
            "disk-setup": DISK_CONFIG_DEFAULTS,
        },
        **data,
    }

    ans = ProxmoxAnswerFile.model_validate(args)

    return ans


def create_answer_file_from_toml(toml_str: str) -> ProxmoxAnswerFile:
    import tomlkit  # type: ignore[import]

    data = tomlkit.parse(toml_str)
    return create_answer_file_from_dict(data)
