from re import sub, MULTILINE
from safe_pc.proxmox_auto_installer.answer_file import (
    disk as disk_config,
    _global as global_config,
    network as network_config,
)

from pydantic import BaseModel, Field
from tomlkit import dumps as toml_dumps


class ProxmoxAnswerFile(BaseModel):
    global_config = Field(
        ...,
        description="Global configuration settings",
        example=global_config.GlobalConfig.model_dump(),
        alias="global",
    )
    network = Field(
        ...,
        description="Network configuration settings",
        example=network_config.NetworkConfig.model_dump(),
    )
    disk_setup = Field(
        ...,
        description="Disk setup configuration settings",
        example=disk_config.DiskConfig.model_dump(),
        alias="disk-setup",
    )

    # provide a method to dump to a dict with aliases
    def to_dict(self) -> dict:
        return self.model_dump(by_alias=True)

    def to_json(self) -> str:
        return self.model_dump_json(by_alias=True)

    def to_pretty_json(self) -> str:
        return self.model_dump_json(by_alias=True, indent=4)

    def to_toml_str(self) -> str:
        toml_str = toml_dumps(self.to_dict())
        # ensure keys are not quoted
        toml_str = sub(r'^"([^"]+)"\s*=', r"\1 =", toml_str, flags=MULTILINE)
