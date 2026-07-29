import os

import pytest

# Set before any module-level Settings() instantiation during collection.
os.environ.setdefault("TOGETHER_API_KEY", "test-api-key")


import io

import pytest


@pytest.fixture
def stream(monkeypatch):
    """Points the conversation log handler at a buffer.

    Neither capsys nor capfd sees these lines: the handler binds `sys.stdout` at
    import time, so it keeps writing to whatever object existed then. And caplog
    sees nothing either, because the logger sets `propagate = False` on purpose
    — that is what keeps uvicorn's `INFO:module:` prefix from breaking the JSON
    parsing. Swapping the handler's own stream is precise and leaves production
    code alone.

    Lives here, not in one test file, because the route tests need it too and
    four copies of a fixture is how four copies diverge.
    """
    from src.rag import conversation_log

    buffer = io.StringIO()
    monkeypatch.setattr(conversation_log._logger.handlers[0], "stream", buffer)
    return buffer


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
