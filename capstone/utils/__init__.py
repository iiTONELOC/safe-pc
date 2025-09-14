"""
Author: Anthony Tropeano
CYBV498: Senior Capstone in Cyber Operations
Date: 2025-09-13
Description: This module provides modular utilities.
"""

from os import getenv

# lambdas to ensure they are always up to date with env vars
IS_VERBOSE = lambda: getenv("CAPSTONE_VERBOSE", "0") == "1"
IS_TESTING = lambda: getenv("CAPSTONE_TESTING", "0") == "1"
