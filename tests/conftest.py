from os import environ
import pytest

from safe_pc.utm.utils.logs import setup_logging


@pytest.fixture(scope="session", autouse=True)
def init_testing():
    environ["CAPSTONE_TESTING"] = "1"
    setup_logging()
