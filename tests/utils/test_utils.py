"""
Author: Anthony Tropeano
CYBV498: Senior Capstone in Cyber Operations
Date: 2025-09-13
Description: This module verifies functions from the utils module.
"""

from pathlib import Path
import capstone.utils.logs as logs
import capstone.utils.crypto as crypto


def test_project_log_dir():
    log_dir = logs._project_log_dir()  # type: ignore
    assert log_dir.exists() and log_dir.is_dir()
    assert log_dir.name == "logs"
    assert log_dir.parent.name == "safe_pc"


def test_project_log_file():
    log_file = logs._project_log_file()  # type: ignore
    assert log_file.exists() and log_file.is_file()
    assert log_file.suffix == ".log"
    assert log_file.parent.name == "logs"
    assert log_file.parent.parent.name == "safe_pc"
    assert (
        log_file.name == "capstone_tests.log"
        if logs.IS_TESTING()
        else log_file.name == "capstone.log"
    )


def test_setup_logging():
    logger = logs.setup_logging()  # type: ignore
    assert logger is not None
    assert logger.name == "capstone"
    logger.info("This is a test log message from test_setup_logging.")
    logger.warning("This is a test warning message from test_setup_logging.")
    logger.error("This is a test error message from test_setup_logging.")
    logger.debug("This is a test debug message from test_setup_logging.")
    # Check the log for the messages and expected format.

    with open(logs._project_log_file(), "r") as f:  # type: ignore
        log_contents = f.read()
        # Check for the expected format (timestamp, logger name, level, message)
        assert (
            " - [capstone] - INFO - This is a test log message from test_setup_logging."
            in log_contents
        )
        assert (
            " - [capstone] - WARNING - This is a test warning message from test_setup_logging."
            in log_contents
        )
        assert (
            " - [capstone] - ERROR - This is a test error message from test_setup_logging."
            in log_contents
        )
        assert (
            " - [capstone] - DEBUG - This is a test debug message from test_setup_logging."
            in log_contents
        )


def test_compute_sha256():
    # Create a temporary file with known content
    test_file = Path("./data/test_file.txt")

    # Ensure the directory exists
    if not test_file.parent.exists():
        test_file.parent.mkdir(parents=True, exist_ok=True)

    # ensure the file exists
    test_file.touch()
    test_file.write_bytes(b"Hello, Capstone!")

    # Compute SHA-256 using the utility function
    computed_hash = crypto.compute_sha256(str(test_file))

    # Verify the computed hash against the expected value
    expected_hash = "66586dd7455b95696626745cbfca765fcdacbf11ecc6825adceac75090c3d336"
    assert computed_hash == expected_hash

    # Clean up the temporary file
    test_file.unlink(missing_ok=True)


def test_verify_sha256():
    # Create a temporary file with known content
    test_file = Path("./data/test_file_verify.txt")

    # Ensure the directory exists
    if not test_file.parent.exists():
        test_file.parent.mkdir(parents=True, exist_ok=True)

    # ensure the file exists
    test_file.touch()
    test_file.write_bytes(b"Verify Capstone!")

    # Precomputed SHA-256 for "Verify Capstone!"
    expected_hash = "7cd3ff64a6c9f757ea18f53a8e8004e54a339347f352f6d9e9fa97bd4bd4f976"

    # Verify the hash using the utility function
    is_valid = crypto.verify_sha256(str(test_file), expected_hash)
    assert is_valid

    # Test with an incorrect hash
    incorrect_hash = "7cd3ff64a6c9f757ea18f53a8e8004e54a339347f352f6d9e9fa97bd4bd4f97b"
    is_valid = crypto.verify_sha256(str(test_file), incorrect_hash)
    assert not is_valid

    # Clean up the temporary files
    test_file.unlink(missing_ok=True)
