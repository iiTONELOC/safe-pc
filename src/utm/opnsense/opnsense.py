from utm.opnsense.iso import (
    OpnSenseISODownloader,
    OpnSenseDownloadError,
    OpnSenseConstants,
    get_latest_opns_url_w_hash,
)
from utm.utils.utils import handle_keyboard_interrupt

async def download_and_verify_opnsense_iso() -> bool:
    try:
        download = await OpnSenseISODownloader(get_latest_opns_url_w_hash, OpnSenseConstants.ISO_DIR)
        return download.verification_status
    except OpnSenseDownloadError:
        return False

@handle_keyboard_interrupt
def main ():
    import asyncio
    from utm.utils.logs import setup_logging
    setup_logging()
    result = asyncio.run(download_and_verify_opnsense_iso())
    if result:
        print(f"Result: {result}")
if __name__ == "__main__":
    main()