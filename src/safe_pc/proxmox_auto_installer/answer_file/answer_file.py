from re import sub, MULTILINE
from safe_pc.proxmox_auto_installer.answer_file.disk import DiskConfig
from safe_pc.proxmox_auto_installer.answer_file._global import GlobalConfig
from safe_pc.proxmox_auto_installer.answer_file.network import NetworkConfig

from pydantic import BaseModel, Field
from tomlkit import dumps as toml_dumps


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

    def to_dict(self) -> dict:
        # ensure none values are removed
        def remove_none(d):
            if isinstance(d, dict):
                return {k: remove_none(v) for k, v in d.items() if v is not None}
            elif isinstance(d, list):
                return [remove_none(v) for v in d]
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
