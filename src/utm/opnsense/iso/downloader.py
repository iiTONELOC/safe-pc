from pathlib import Path
from base64 import b64decode
from logging import getLogger
from collections.abc import Callable, Awaitable

from utm.utils import ISODownloader, fetch_text_from_url, remove_bz2_compression, run_command_async

LOGGER = getLogger(__name__)


# https://docs.opnsense.org/manual/install.html#download-and-verification


class OpnSenseDownloadError(Exception):
    """Raised when OPNSense download or verification fails."""


TParent = tuple[str, str]
TChild = tuple[str, str, str]


class OpnSenseISODownloader(ISODownloader):
    """Context-managed or direct OPNSense ISO downloader and verifier."""

    def __init__(
        self,
        get_iso_info: Callable[[], Awaitable[TChild]],
        dest_dir: Path,
        on_update: Callable[[int, int, str], None] | None = None,
    ):
        # Wrap it so parent sees a no-arg async callable
        super().__init__(self._wrap_get_iso_info(get_iso_info), dest_dir, on_update)

        self.public_key: str = ""
        self.downloaded_from: str = ""
        self.expected_sha256: str = ""
        self.downloaded_files: list[Path] = []
        self.verification_status: bool = False

    # Wrap the original callable to match parent type
    def _wrap_get_iso_info(
        self, original_get_iso_info: Callable[[], Awaitable[TChild]]
    ) -> Callable[[], Awaitable[TParent]]:
        async def wrapper() -> TParent:
            url, sha256, pub_key = await original_get_iso_info()
            self.downloaded_from = url
            self.expected_sha256 = sha256
            self.public_key = pub_key
            return url, sha256

        return wrapper

    # Overrides

    async def run(self, dl_if_exists: bool = False) -> "OpnSenseISODownloader":
        # call the parent to download the ISO - this will verify the sha256
        # see @get_latest_opns_url_w_hash
        # but does not perform signature verification
        downloaded = await super().run(dl_if_exists)

        # ensure we downloaded
        if not downloaded.verified or not self.dest_path:
            raise OpnSenseDownloadError("Failed to download OPNSense ISO")

        # Handle verification of the DL. If we make it this far the public key and sha matches our expected
        # HOWEVER, signatures have not been verified yet

        # get the signature file from the same location as the downloaded ISO
        LOGGER.info(f"Downloading OPNSense ISO signature file from: {self.downloaded_from.replace('.iso.bz2', '.iso.sig')}")
        signature_file_text = await fetch_text_from_url(self.downloaded_from.replace(".iso.bz2", ".iso.sig"))
        if not signature_file_text:
            raise OpnSenseDownloadError("Failed to download OPNSense ISO signature file")

        # decompress the iso before verifying the signature - OPNSense uses bz2 compression
        # And calculates the sha256 of the decompressed file
        LOGGER.info(f"Decompressing OPNSense ISO file: {self.dest_path}")
        decompressed_path = await remove_bz2_compression(self.dest_path)

        if not decompressed_path or not decompressed_path.exists():
            raise OpnSenseDownloadError("Failed to decompress OPNSense ISO file")


        # decode and write the signature file
        sig_bytes = b64decode(signature_file_text)
        sig_path = decompressed_path.with_suffix(".sig")
        sig_path.write_bytes(sig_bytes)
        self.downloaded_files.append(sig_path)

        # write the public key to a file too
        pub_key_path = decompressed_path.with_suffix(".pub")
        pub_key_path.write_text(self.public_key)
        self.downloaded_files.append(pub_key_path)

        # verify the signature using openssl
        cmd_result = await run_command_async(
            "openssl",
            "dgst",
            "-sha256",
            "-verify",
            str(decompressed_path.with_suffix(".pub")),
            "-signature",
            str(decompressed_path.with_suffix(".sig")),
            str(decompressed_path),
            check=False,
        )

        if cmd_result.returncode != 0 or "Verified OK" not in cmd_result.stdout:  # type: ignore
            LOGGER.error(f"Signature verification failed: {cmd_result.stderr}")  # type: ignore
            LOGGER.error(f"Signature verification output: {cmd_result.stdout}")  # type: ignore
            raise OpnSenseDownloadError("Failed to verify OPNSense ISO signature")
        self.verification_status = True
        LOGGER.info(f"OPNSense ISO signature verified successfully: {decompressed_path}")
        return self


    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object | None,
    ) -> None:
        await super().__aexit__(exc_type, exc, tb)

    def __await__(self, dl_if_exists: bool = False):
        return self.run(dl_if_exists).__await__()
