from os import environ
import pytest

from utm.__main__ import setup_logging


@pytest.fixture(scope="session", autouse=True)
def init_testing():
    environ["CAPSTONE_TESTING"] = "1"
    setup_logging()
