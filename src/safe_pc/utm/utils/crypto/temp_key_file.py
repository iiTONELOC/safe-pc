import os
import atexit
import signal
import tempfile
from pathlib import Path
from types import FrameType

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePrivateKey


class TempKeyFile:
    """
    Context manager that writes key_bytes to a secure temporary file,
    locks the file to the current user, and ensures cleanup on exit/signals.

    This is useful for passing private keys to external tools that require
    a file path, while minimizing the risk of leaving sensitive data on disk.
    """

    def __init__(
        self,
        key_input: bytes | bytearray | EllipticCurvePrivateKey,
        prefix: str = "safe-pc-key-",
        suffix: str = ".pem",
    ):
        """
        key_input may be:
          - bytes (already PEM-encoded)
          - a cryptography private key object (e.g., EllipticCurvePrivateKey)
        """
        if isinstance(key_input, (bytes, bytearray)):
            self.key_bytes = bytes(key_input)
        elif isinstance(key_input, EllipticCurvePrivateKey):
            self.key_bytes = key_input.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        else:
            raise TypeError(f"Unsupported type for key_input: {type(key_input)}")

        self.prefix = prefix
        self.suffix = suffix
        self._path: Path | None = None
        self._registered = False

    def _make_tempfile(self) -> Path:
        fd, path_str = tempfile.mkstemp(prefix=self.prefix, suffix=self.suffix)
        try:
            # write and flush then close handle so other code can open it
            os.write(fd, self.key_bytes)
            os.fsync(fd)
        except Exception:
            os.close(fd)
            os.unlink(path_str)
            raise
        finally:
            os.close(fd)

        p = Path(path_str)

        try:
            p.chmod(0o600)
        except Exception:
            pass

        return p

    def __enter__(self) -> Path:
        self._path = self._make_tempfile()

        # ensure cleanup on normal program exit
        if not self._registered:
            atexit.register(self._cleanup)
            # also handle signals
            for sig in (signal.SIGINT, signal.SIGTERM):
                try:
                    signal.signal(sig, self._signal_handler)
                except Exception:
                    pass
            self._registered = True

        return self._path

    def _signal_handler(self, signum: int, frame: FrameType | None) -> None:
        self._cleanup()
        # re-raise default behavior after cleanup
        raise SystemExit(0)

    def _cleanup(self):
        if self._path and self._path.exists():
            try:
                # attempt to zero file contents before unlinking (best-effort)
                try:
                    with open(self._path, "r+b") as f:
                        length = f.seek(0, os.SEEK_END)
                        f.seek(0)
                        f.write(b"\x00" * (length if length else 0))
                        f.flush()
                        os.fsync(f.fileno())
                except Exception:
                    pass
                self._path.unlink()
            except Exception:
                pass
        self._path = None

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object | None,
    ) -> None:
        self._cleanup()
