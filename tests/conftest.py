import os

import pytest

# Set before any module-level Settings() instantiation during collection.
os.environ.setdefault("TOGETHER_API_KEY", "test-api-key")


import pytest


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """The limiter counts in a module-level dict, so without this the suite
    becomes order-dependent: enough /chat tests in one file and the next one
    starts getting 429s for reasons that have nothing to do with what it tests.
    """
    from src.api import limits

    limits.reset()
    yield
    limits.reset()
