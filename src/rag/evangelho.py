import datetime
import random

from src.rag.retriever import _get_store

EVANGELHO_BOOK = "O Evangelho segundo o Espiritismo"

def get_daily_passage() -> dict | None:
    chunks = _get_store().get_by_filter({"book": {"$eq": EVANGELHO_BOOK}})
    if not chunks:
        return None
    chunks.sort(
        key=lambda c: (
            c["metadata"].get("item_number", ""),
            c["metadata"].get("subchunk_index", 0),
        )
    )
    today = datetime.date.today().isoformat()
    random.seed(today)
    chunk = random.choice(chunks)
    meta = chunk["metadata"]
    return {
        "date": today,
        "content": chunk["content"],
        "source": {
            "book": EVANGELHO_BOOK,
            "chapter_title": meta.get("chapter_title"),
            "item_number": meta.get("item_number"),
            "subchunk_index": meta.get("subchunk_index"),
            "total_subchunks": meta.get("total_subchunks"),
        },
    }
