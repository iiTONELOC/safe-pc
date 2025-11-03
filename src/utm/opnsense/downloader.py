from collections.abc import Callable
from logging import getLogger
from typing import Any
from utm.opnsense.iso import (
    OpnSenseConstants,
    OpnSenseISODownloader,
    get_latest_opns_url_w_hash,
)
from utm.utils.utils import handle_keyboard_interrupt

LOGGER = getLogger(__name__)


async def download_and_verify_opnsense_iso(on_update: Callable[[int, int, str], Any] | None = None) -> bool:
    try:
        await OpnSenseISODownloader(get_latest_opns_url_w_hash, OpnSenseConstants.ISO_DIR, on_update)
        return True
    except Exception as e:
        LOGGER.error(f"OPNSense ISO download/verification failed: {e}")
        return False


@handle_keyboard_interrupt
def main():
    import asyncio
    from utm.__main__ import setup_logging

    setup_logging()
    result = asyncio.run(download_and_verify_opnsense_iso())
    if result:
        exit(0)
    else:
        exit(1)


if __name__ == "__main__":
    main()
