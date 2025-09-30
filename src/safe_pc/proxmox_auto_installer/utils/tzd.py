from pathlib import Path
from locale import getlocale


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

    def get_local_timezone(self) -> str:
        """Attempt to determine the local timezone based on the system locale.

        Returns:
            str: The detected timezone string, or "America/New_York" if detection fails.
        """
        self._ensure_initialized()
        loc = getlocale()
        if loc and loc[0]:
            country_code = loc[0].split("_")[-1]
            for tz in self._timezones:
                if tz.endswith(f"/{country_code}"):
                    return tz
        return "America/New_York"

    def regional(self, partial: str) -> list[str]:
        """Get a list of timezones that start with the same region as the provided timezone.

        Args:
            partial (str): A timezone string like 'America/New_York'.

        Returns:
            list[str]: List of timezones in the same region.
        """
        self._ensure_initialized()
        print(self._timezones)
        print(f"Finding timezones similar to: {partial}")
        if "/" in partial:
            region = partial.split("/")[0].strip()
            print(f"Finding timezones similar to region: {region}")
            return [tz for tz in self._timezones if tz.startswith(f"{region}")]
        return []

    def get_tz_indexes(self, tz: str) -> list[int]:
        """Get the indexes of a timezone in the timezone list.

        Args:
            tz (str): The timezone string to find.

        Returns:
            list[int]: List of indexes where the timezone is found.
        """
        self._ensure_initialized()
        return [i for i, t in enumerate(self._timezones) if t == tz]

    def get_surrounding_tz_indexes(self, tz: str, range_size: int = 2) -> list[int]:
        """Get the indexes of timezones surrounding a given timezone.

        Args:
            tz (str): The timezone string to find.
            range_size (int, optional): Number of surrounding indexes to include on each side. Defaults to 2.

        Returns:
            list[int]: List of surrounding indexes.
        """
        self._ensure_initialized()
        indexes = self.get_tz_indexes(tz)
        surrounding_indexes = set()
        for index in indexes:
            start = max(0, index - range_size)
            end = min(len(self._timezones), index + range_size + 1)
            surrounding_indexes.update(range(start, end))
        return sorted(surrounding_indexes)

    def _ensure_initialized(self):
        if self._timezones is None:
            self._timezones = get_timezones()
