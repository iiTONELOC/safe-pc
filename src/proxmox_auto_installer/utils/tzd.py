import os
from pathlib import Path
from shutil import which
from locale import getlocale


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

    def get_local_timezone(self) -> str:
        """
        Resolve system timezone as robustly as possible.
        Works on host systems (systemd) and inside Docker (no timedatectl).
        """

        # 1. timedatectl (systemd hosts)
        if which("timedatectl"):
            tz_show_out = os.popen("timedatectl show -p Timezone").read().strip()
            if tz_show_out and "=" in tz_show_out:
                tz = tz_show_out.split("=")[-1].strip()
                if tz in self._timezones:  # type: ignore
                    return tz

        # 2. /etc/timezone (Debian/Ubuntu style)
        etc_tz = Path("/etc/timezone")
        if etc_tz.exists():
            tz = etc_tz.read_text().strip()
            if tz in self._timezones:  # type: ignore
                return tz

        # 3. /etc/localtime symlink (Alpine, Docker, most distros)
        etc_localtime = Path("/etc/localtime")
        if etc_localtime.exists():
            try:
                real_path = etc_localtime.resolve()
                if "zoneinfo" in str(real_path):
                    tz = str(real_path).split("zoneinfo/")[-1]
                    if tz in self._timezones:  # type: ignore
                        return tz
            except Exception:
                pass

        # 4. Last resort
        self._local_timezone = "America/New_York"
        return "America/New_York"

    def _ensure_initialized(self):
        if self._timezones is None:
            self._timezones = self.get_timezones()
            self._timezones = self.get_timezones()
