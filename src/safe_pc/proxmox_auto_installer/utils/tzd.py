import urllib.request as requests
from pathlib import Path
from locale import getlocale


from safe_pc.proxmox_auto_installer.utils.country_codes import ProxmoxCountryCodeHelper

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

    def get_timezones(self) -> list[str]|None:
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

    def get_local_timezone(self) -> str:
        """
        Determines and returns the local timezone as a string.
        First tries to detect the timezone using Unix system files.
        If unsuccessful, attempts to retrieve the timezone using an external IP-based API.
        If all methods fail, defaults to "America/New_York".
        Returns:
            str: The local timezone string, or "America/New_York" if detection fails.
        """
        if hasattr(self, "_local_timezone"):
            return self._local_timezone

        # Try Unix system files
        try:
            tz_path = Path("/etc/timezone")
            if tz_path.exists():
                with tz_path.open("r", encoding="utf-8") as f:
                    tz = f.read().strip()
                    if tz:
                        self._local_timezone = tz
                        return tz
            localtime_path = Path("/etc/localtime")
            if localtime_path.exists():
                # Try to resolve symlink to zoneinfo
                try:
                    resolved = localtime_path.resolve()
                    parts = resolved.parts
                    if "zoneinfo" in parts:
                        idx = parts.index("zoneinfo")
                        tz = "/".join(parts[idx+1:])
                        if tz:
                            self._local_timezone = tz
                            return tz
                except Exception:
                    pass
        except Exception:
            pass

        # Fallback to external API
        try:
            with requests.urlopen("https://ipapi.co/timezone", timeout=5) as resp:
                tz = resp.read().decode().strip()
                if tz:
                    self._local_timezone = tz
                    return tz
        except Exception:
            pass

        self._local_timezone = "America/New_York"
        return "America/New_York"  # last fallback

    def _ensure_initialized(self):
        if self._timezones is None:
            self._timezones = self.get_timezones()
            self._timezones = self.get_timezones()
