from src.core.config import settings
from src.ingestion.embeddings import encode
from src.ingestion.vectorstore import VectorStore

_store: VectorStore | None = None


def _get_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore(settings.chroma_path, settings.chroma_collection)
    return _store


def retrieve(query: str, top_k: int | None = None) -> list[dict]:
    if top_k is None:
        top_k = settings.top_k
    embedding = encode([query])[0]
    results = _get_store().query(embedding, n_results=top_k)
    return [r for r in results if r["distance"] <= settings.max_distance]


def retrieve_by_item(book: str, item_number: str) -> list[dict]:
    where = {"$and": [{"book": {"$eq": book}}, {"item_number": {"$eq": item_number}}]}
    return _get_store().get_by_filter(where)
