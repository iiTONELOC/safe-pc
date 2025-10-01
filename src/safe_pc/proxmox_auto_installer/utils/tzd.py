import json
import urllib.request as requests
from pathlib import Path
from locale import getlocale


from safe_pc.proxmox_auto_installer.utils.country_codes import _get_country_codes

TZ_FILE = Path(__file__).parent / "tzs.txt"


def _get_timezones() -> list[str]:
    """Read the timezone file and return a list of timezones."""
    if not TZ_FILE.exists():
        raise FileNotFoundError(f"Timezone file not found: {TZ_FILE}")
    with TZ_FILE.open("r", encoding="utf-8") as f:
        # read the file
        file = f.read()
        # split by white space and filter out empty lines
        timezones = [line.strip() for line in file.split(" ") if line.strip()]
    return timezones


class ProxmoxTimezoneHelper:
    _instance = None
    _timezones = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ProxmoxTimezoneHelper, cls).__new__(cls)
            cls._timezones = _get_timezones()
        return cls._instance

    def get_timezones(self) -> list[str]:
        self._ensure_initialized()
        return self._timezones

    def get_local_country_code(self) -> str:
        """Attempt to determine the local country code based on the system locale.

        Returns:
            str: The detected country code, or "US" if detection fails.
        """
        self._ensure_initialized()
        loc = getlocale()
        codes = _get_country_codes()
        if loc and loc[0]:
            country_code = loc[0].split("_")[-1]
            return codes.get(country_code, "US")

        return "US"

    def get_local_timezone(self) -> str:
        """
        Determines and returns the local timezone as a string.
        Attempts to retrieve the timezone using an external IP-based API. If successful,
        caches and returns the timezone. If the API call fails or no timezone is found,
        defaults to "UTC".
        Returns:
            str: The local timezone string, or "UTC" if detection fails.

        """

        if hasattr(self, "_local_timezone"):
            return self._local_timezone
        try:
            with requests.urlopen("https://ipapi.co/timezone", timeout=5) as resp:
                tz = resp.read().decode().strip()
                if tz:
                    self._local_timezone = tz
                    return tz
        except Exception:
            pass
        self._local_timezone = "UTC"
        return "UTC"  # last fallback

    def _ensure_initialized(self):
        if self._timezones is None:
            self._timezones = self.get_timezones()
