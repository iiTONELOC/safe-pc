import os
from pathlib import Path
from locale import getlocale
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from proxmox_auto_installer.utils.country_codes import ProxmoxCountryCodeHelper

TZ_FILE = Path(__file__).parent / "tzs.txt"


def _get_timezones() -> list[str]:
    """Read the timezone file and return a list of timezones."""
    if not TZ_FILE.exists():
        raise FileNotFoundError(f"Timezone file not found: {TZ_FILE}")
    with TZ_FILE.open("r", encoding="utf-8") as f:
        # read the file
        file = f.read()
        # split by white space and filter out empty lines
        timezones = [line.strip() for line in file.split("\n") if line.strip()]
    return timezones


class ProxmoxTimezoneHelper:
    _instance = None
    _timezones = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ProxmoxTimezoneHelper, cls).__new__(cls)
            cls._timezones = _get_timezones()
        return cls._instance

    def get_timezones(self) -> list[str] | None:
        self._ensure_initialized()
        return self._timezones

    def get_local_country_code(self) -> str:
        """Attempt to determine the local country code based on the system locale.

        Returns:
            str: The detected country code, or "US" if detection fails.
        """
        self._ensure_initialized()
        loc = getlocale()
        code_dict = ProxmoxCountryCodeHelper().get_country_codes()
        if loc and loc[0]:
            country_code = loc[0].split("_")[-1]
            return code_dict.get(country_code, "US")

        return "US"

    def _canonical_tz(self, tz: str) -> str:
        try:
            return ZoneInfo(tz).key  # turns Etc/UTC -> UTC
        except ZoneInfoNotFoundError:
            return tz

    def get_local_timezone(self) -> str:
        # default to environment variable PROX_TZ or America/New_York
        # this will be set by the client
        return os.environ.get("PROX_TZ", "America/New_York")

    def _ensure_initialized(self):
        if self._timezones is None:
            self._timezones = self.get_timezones()
            self._timezones = self.get_timezones()
