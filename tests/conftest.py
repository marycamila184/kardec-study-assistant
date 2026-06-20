import os
import pytest


@pytest.fixture(autouse=True, scope="session")
def set_test_env():
    os.environ.setdefault("ANTHROPIC_API_KEY", "test-api-key")
