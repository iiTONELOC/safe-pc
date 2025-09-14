"""
Description: This module provides reusable utilities.

Modules exported by this package:

- `logs`: Logging utils.

- `crypto`: Cryptographic utilities for hashing and verification.

Functions exported by this package:

- `IS_VERBOSE()`: Checks if verbose mode is enabled via environment variable.

- `IS_TESTING()`: Checks if testing mode is enabled via environment variable.

"""

from os import getenv

# lambdas to ensure they are always up to date with env vars
IS_VERBOSE = lambda: getenv("CAPSTONE_VERBOSE", "0") == "1"
IS_TESTING = lambda: getenv("CAPSTONE_TESTING", "0") == "1"
