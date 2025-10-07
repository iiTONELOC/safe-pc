from re import compile as re_compile
from pydantic import BaseModel, Field, field_validator
from safe_pc.proxmox_auto_installer.utils.tzd import ProxmoxTimezoneHelper
from safe_pc.proxmox_auto_installer.constants import PROXMOX_ALLOWED_KEYBOARDS
from safe_pc.proxmox_auto_installer.utils.country_codes import ProxmoxCountryCodeHelper

timezone_list = ProxmoxTimezoneHelper()._timezones
country_list = ProxmoxCountryCodeHelper().get_country_codes_list()

COUNTRY_CODE_PATTERN = re_compile(r"^[A-Z]{2}$")
KEYBOARD_COUNTRY_PATTERN = re_compile(r"^[a-z]{2}(-[a-z]{2})?$")
TIMEZONE_PATTERN = re_compile(r"^[A-Za-z_]+/[A-Za-z_]+(/[A-Za-z_]+)?$")
FQDN_PATTERN = re_compile(
    r"^([a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,63}$"
)
HASHED_PASSWORD_PATTERN = re_compile(
    r"^\$6\$rounds=\d{6}\$[./A-Za-z0-9]{8}\$[./A-Za-z0-9]{86}$"
)
EMAIL_OR_LOCALHOST_PATTERN = re_compile(
    r"(^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$)|^(root|admin|user)@localhost$"
)

GLOBAL_CONFIG_DEFAULTS = {
    "keyboard": "en-us",
    "country": "US",
    "timezone": "America/New_York",
    "fqdn": "proxmox.lab.local",
    "mailto": "root@localhost",
    "root_password_hashed": "$6$rounds=656000$12345678$" + "A" * 86,
}


class GlobalConfig(BaseModel):
    model_config = {"populate_by_name": True}

    keyboard: str = Field(
        default=GLOBAL_CONFIG_DEFAULTS["keyboard"],
        description="Keyboard layout code",
        pattern=KEYBOARD_COUNTRY_PATTERN.pattern,
    )

    country: str = Field(
        default=GLOBAL_CONFIG_DEFAULTS["country"],
        description="Country code",
        pattern=COUNTRY_CODE_PATTERN.pattern,
    )

    timezone: str = Field(
        default=GLOBAL_CONFIG_DEFAULTS["timezone"],
        description="Timezone string",
        pattern=TIMEZONE_PATTERN.pattern,
    )

    fqdn: str = Field(
        default=GLOBAL_CONFIG_DEFAULTS["fqdn"],
        max_length=255,
        description="Fully Qualified Domain Name for the Proxmox server",
        pattern=FQDN_PATTERN.pattern,
    )

    mailto: str = Field(
        default=GLOBAL_CONFIG_DEFAULTS["mailto"],
        description="Email address for system notifications",
        pattern=EMAIL_OR_LOCALHOST_PATTERN.pattern,
    )

    root_password_hashed: str = Field(
        default=GLOBAL_CONFIG_DEFAULTS["root_password_hashed"],
        description="Hashed root password for the Proxmox server",
        pattern=HASHED_PASSWORD_PATTERN.pattern,
        alias="root-password-hashed",
    )

    @field_validator("keyboard")
    def validate_keyboard_pattern(cls, keyboard_value: str) -> str:
        if not KEYBOARD_COUNTRY_PATTERN.match(keyboard_value):
            raise ValueError(f"Invalid keyboard pattern: {keyboard_value}")
        if keyboard_value not in PROXMOX_ALLOWED_KEYBOARDS:
            raise ValueError(f"Invalid keyboard layout: {keyboard_value}")
        return keyboard_value

    @field_validator("country")
    def validate_country_pattern(cls, country_value: str) -> str:
        if not COUNTRY_CODE_PATTERN.match(country_value):
            raise ValueError(f"Invalid country pattern: {country_value}")
        if country_value not in country_list:
            raise ValueError(f"Invalid country code: {country_value}")
        return country_value

    @field_validator("timezone")
    def validate_timezone_pattern(cls, timezone_value: str) -> str:
        if not TIMEZONE_PATTERN.match(timezone_value):
            raise ValueError(f"Invalid timezone pattern: {timezone_value}")
        if timezone_value not in timezone_list:
            raise ValueError(f"Invalid timezone: {timezone_value}")
        return timezone_value

    @field_validator("fqdn")
    def validate_fqdn_pattern(cls, fqdn_value: str) -> str:
        if not FQDN_PATTERN.match(fqdn_value):
            raise ValueError(f"Invalid fqdn pattern: {fqdn_value}")
        return fqdn_value

    @field_validator("mailto")
    def validate_mailto_pattern(cls, mailto_value: str) -> str:
        if not EMAIL_OR_LOCALHOST_PATTERN.match(mailto_value):
            raise ValueError(f"Invalid mailto pattern: {mailto_value}")
        return mailto_value

    @field_validator("root_password_hashed")
    def validate_root_password_hashed_pattern(cls, hashed_password_value: str) -> str:
        if not HASHED_PASSWORD_PATTERN.match(hashed_password_value):
            raise ValueError(
                f"Invalid root_password_hashed pattern: {hashed_password_value}"
            )
        return hashed_password_value

    @field_validator("keyboard")
    def validate_keyboard_allowed(cls, keyboard_value: str) -> str:
        if keyboard_value not in PROXMOX_ALLOWED_KEYBOARDS:
            raise ValueError(f"Invalid keyboard layout: {keyboard_value}")
        return keyboard_value

    @field_validator("timezone")
    def validate_timezone_allowed(cls, timezone_value: str) -> str:
        if timezone_value not in timezone_list:
            raise ValueError(f"Invalid timezone: {timezone_value}")
        return timezone_value
