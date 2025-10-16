from pathlib import Path

CC_FILE = Path(__file__).parent / "ccodes.txt"


def _get_country_codes() -> dict[str, str]:
    """Read the country codes file and return a dictionary of country codes to country names."""
    if not CC_FILE.exists():
        raise FileNotFoundError(f"Country codes file not found: {CC_FILE}")
    with CC_FILE.open("r", encoding="utf-8") as f:
        # read the file
        file = f.read()
        # split by new lines and filter out empty lines
        lines = [line.strip() for line in file.split("\n") if line.strip()]
        # split each line by comma and create a dictionary
        country_codes: dict[str, str] = {}
        for line in lines:
            parts = line.split(":")
            if len(parts) == 2:
                code, name = parts
                country_codes[code.strip()] = name.strip()
    return country_codes


class ProxmoxCountryCodeHelper:
    _instance = None
    _country_codes = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ProxmoxCountryCodeHelper, cls).__new__(cls)
            cls._country_codes = _get_country_codes()
        return cls._instance

    def get_country_codes(self) -> dict[str, str]:
        self._ensure_initialized()
        if self._country_codes is None:
            raise RuntimeError("Country codes not initialized properly.")
        return self._country_codes

    def get_country_codes_list(self) -> list[str]:
        """Get a list of all country codes.

        Returns:
            list[str]: List of country codes (e.g., ['US', 'GB', 'FR']).
        """
        self._ensure_initialized()
        return [v.lower() for v in self._country_codes.values()] #type: ignore

    def get_country_name(self, code: str) -> str | None:
        """Get the country name for a given country code.

        Args:
            code (str): The country code (e.g., 'US').
        Returns:
            str | None: The country name if found, otherwise None.
        """
        self._ensure_initialized()
        return self._country_codes.get(code) #type: ignore

    def _ensure_initialized(self):
        if self._country_codes is None:
            self._country_codes = _get_country_codes()
        if self._country_codes is None: #type: ignore
            raise RuntimeError("Country codes not initialized properly.")
