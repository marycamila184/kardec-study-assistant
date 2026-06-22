import os
import pytest

# Set before any module-level Settings() instantiation during collection.
os.environ.setdefault("GROQ_API_KEY", "test-api-key")
