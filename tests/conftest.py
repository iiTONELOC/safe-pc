"""
Author: Anthony Tropeano
CYBV498: Senior Capstone in Cyber Operations
Date: 2025-09-13
Description: Test configurations.
"""

# tests/conftest.py
from os import environ
import pytest
from capstone.utils.logs import setup_logging


@pytest.fixture(scope="session", autouse=True)
def init_testing():
    environ["CAPSTONE_TESTING"] = "1"
    setup_logging()
