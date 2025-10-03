from pathlib import Path
from threading import Lock
from logging import getLogger
from requests import get, head
from concurrent.futures import ThreadPoolExecutor, as_completed

from tqdm import tqdm

HTTP_CHUNK_SIZE = 1024 * 1024  # 1 MB chunks
LOGGER = getLogger("capstone.utils.downloader" if __name__ == "__main__" else __name__)


def _thread_safe_downloader(
    start: int,
    end: int,
    url: str,
    dest_path: Path,
    file_lock: Lock,
    progress: tqdm,  # type: ignore
):
    """
    Downloads a specific byte range from a URL and writes it to a file in a thread-safe manner.
    This function is intended to be used in a multi-threaded context, where each thread downloads
    a different segment of a file. It uses a file lock to ensure that writes to the destination
    file are thread-safe. Progress is updated using a tqdm progress bar.

    Args:
        start (int): The starting byte position of the range to download.
        end (int): The ending byte position of the range to download.
        url (str): The URL to download the file segment from.
        dest_path (Path): The path to the destination file to write the downloaded data.
        file_lock (Lock): A threading lock to synchronize file writes between threads.
        progress (tqdm[NoReturn]): A tqdm progress bar instance to update download progress.

    Raises:
        requests.HTTPError: If the HTTP request fails.
    """
    # fetch data, raise error on failure
    headers = {"Range": f"bytes={start}-{end}"}
    resp = get(url, headers=headers, stream=True, timeout=30)
    resp.raise_for_status()

    # buffer data for less i/o operations
    buffer = bytearray()
    offset = start

    # read the response in chunks and write to file in a thread-safe manner
    for chunk in resp.iter_content(chunk_size=HTTP_CHUNK_SIZE):
        if chunk:
            # add the chunk to the buffer
            buffer.extend(chunk)
            # flush every 4 MB
            if len(buffer) >= HTTP_CHUNK_SIZE * 4:
                with file_lock, open(dest_path, "r+b") as f:
                    f.seek(offset)
                    f.write(buffer)
                offset += len(buffer)
                progress.update(len(buffer))
                buffer.clear()

    # flush any leftovers from the buffer
    if buffer:
        with file_lock, open(dest_path, "r+b") as f:
            f.seek(offset)
            f.write(buffer)
            progress.update(len(buffer))


def _parallel_downloader(
    url: str, dest_path: Path, size: int, num_threads: int = 4
) -> None:
    """
    Downloads a file from the specified URL in parallel using multiple threads.
    The file is split into chunks, each downloaded by a separate thread, and written to
    the destination path.

    A progress bar is displayed during the download. The function ensures thread-safe
    writes and handles cleanup in case of errors or interruptions.
    Args:
        url (str): The URL of the file to download.
        dest_path (Path): The local file path where the downloaded file will be saved.
        size (int): The total size of the file in bytes.
        num_threads (int, optional): The number of threads to use for parallel
                                     downloading. Defaults to 4.
    Raises:
        Exception: Propagates any exception encountered during download,
        except KeyboardInterrupt, which is handled gracefully.
    """

    executor = None  # declare here for cleanup in except block
    file_lock = Lock()  # lock for thread-safe file writes

    LOGGER.info(
        f"Starting Parallel download of {url}: {size} bytes in {num_threads} threads"
    )

    # pre-allocate the file
    with open(dest_path, "wb") as f:
        f.truncate(size)

    # split the chunks between the threads
    chunk_size: int = size // num_threads

    # generate a list of byte ranges for each thread
    ranges: list[tuple[int, int]] = [
        # Generate (start, end) byte ranges for each thread to download a chunk of the file
        (i * chunk_size, (i + 1) * chunk_size - 1)
        for i in range(num_threads)
    ]

    # Adjust the last chunk to cover any remaining bytes
    ranges[-1] = (ranges[-1][0], size - 1)

    # Generate the progress bar to STD_OUT, note this bar isn't logged with the logger
    progress = tqdm(total=size, unit="B", unit_scale=True, desc="Downloading")

    try:
        # Use ThreadPoolExecutor to download chunks in parallel
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [
                executor.submit(
                    _thread_safe_downloader,  # type: ignore
                    start,
                    end,
                    url,
                    dest_path,
                    file_lock,
                    progress,
                )
                for start, end in ranges
            ]
            for fut in as_completed(futures):
                fut.result()

    # Handle exceptions and cleanup
    except Exception as e:

        if dest_path.exists():
            dest_path.unlink()

        if executor is not None:
            executor.shutdown(cancel_futures=True)
            progress.close()

        if isinstance(e, KeyboardInterrupt):
            LOGGER.warning("Download cancelled by user (KeyboardInterrupt).")
            # Attempt to cancel all running futures and close the progress bar
            return
        else:
            raise

    finally:
        progress.close()


def _single_downloader(url: str, dest_path: Path, size: int) -> None:
    """
    Downloads a file from the specified URL to the given destination path using a single connection.
    Args:
        url (str): The URL of the file to download.
        dest_path (Path): The local file path where the downloaded file will be saved.
        size (int): The expected size of the file in bytes, used for progress tracking.
    Raises:
        Exception: If any error occurs during the download process, except for KeyboardInterrupt.
        KeyboardInterrupt: If the download is cancelled by the user.
    Notes:
        - Uses streaming to download the file in chunks and displays a progress bar.
        - Buffers data before writing to disk for efficiency.
        - Cleans up partially downloaded files in case of errors.
    """

    LOGGER.info("Falling back to single connection download")
    # fetch data w/ GET request, streaming enabled, raise error on failure
    with get(url, stream=True) as resp, open(dest_path, "wb") as f:
        resp.raise_for_status()
        buffer = bytearray()  # buffer chunks for less i/o operations
        progress = tqdm(total=size, unit="B", unit_scale=True, desc="Downloading")

        try:
            # process incoming data in chunks
            for chunk in resp.iter_content(chunk_size=HTTP_CHUNK_SIZE):
                if chunk:
                    # add the chunk to the buffer
                    buffer.extend(chunk)
                    # flush every 4 MB
                    if len(buffer) >= HTTP_CHUNK_SIZE * 4:
                        f.write(buffer)
                        progress.update(len(buffer))
                        buffer.clear()

            # flush any leftovers from the buffer
            if buffer:
                f.write(buffer)
                progress.update(len(buffer))
        # handle errors, ignore KeyboardInterrupt
        except Exception as e:

            if dest_path.exists():
                dest_path.unlink()

            if isinstance(e, KeyboardInterrupt):
                LOGGER.warning("Download cancelled by user (KeyboardInterrupt).")
                progress.close()
                return
            raise
        finally:
            progress.close()


def handle_download(url: str, dest_path: Path, num_threads: int = 4) -> None:
    """
    Downloads a file from the specified URL to the given destination path.

    The function attempts to download the file using parallel chunking if the server supports
    byte-range requests and the file size is known. Otherwise, it falls back to a single-threaded
    download. The number of parallel threads can be specified.

    If the download fails, the partially downloaded file is removed and the error is logged.

    Args:
        url (str): The URL of the file to download.
        dest_path (Path): The local path where the downloaded file will be saved.
        num_threads (int, optional): Number of parallel threads to use for downloading. Defaults to 4.

    Raises:
        Exception: If the download fails for any reason other than KeyboardInterrupt.

    Notes:
        - In testing, more than 4 threads caused 503 errors on some servers.
    """
    try:
        # fetch headers with HEAD request to check for byte-range support and get file size
        _head = head(url, allow_redirects=True)
        _head.raise_for_status()

        size_str: str = _head.headers.get("Content-Length", "0")
        size: int = int(size_str)
        accept_ranges: str = _head.headers.get("Accept-Ranges", "none")

        # if we can use parallel downloading, do so
        if accept_ranges.lower() == "bytes" and size > 0 and num_threads > 1:
            _parallel_downloader(url, dest_path, size, num_threads)
        # otherwise fall back to single connection download
        else:
            _single_downloader(url, dest_path, size)

        LOGGER.info(f"Download complete: {dest_path}")

    except Exception as e:
        if isinstance(e, KeyboardInterrupt):
            return
        LOGGER.error(f"Download failed: {e}")
        if dest_path.exists():
            dest_path.unlink()
        raise
