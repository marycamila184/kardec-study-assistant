"""The only place in the project that builds a Firestore client.

Exists because there are now two collections — the push subscriptions and
today's reflection cache — and two separate seams would give two
`lru_cache`s, two places for tests to swap, and the chance of the two
diverging.

The import stays INSIDE the function on purpose: at module scope it would
force the library to be importable during collection of every test in this
repo.
"""

from functools import lru_cache


@lru_cache(maxsize=1)
def client():
    from google.cloud import firestore

    return firestore.Client()
