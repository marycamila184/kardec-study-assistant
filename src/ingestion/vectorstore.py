import chromadb


class VectorStore:
    def __init__(self, path: str, collection_name: str) -> None:
        self._client = chromadb.PersistentClient(path=path)
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict],
    ) -> None:
        self._collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    def query(self, embedding: list[float], n_results: int) -> list[dict]:
        result = self._collection.query(
            query_embeddings=[embedding],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )
        return [
            {"content": doc, "metadata": meta, "distance": dist}
            for doc, meta, dist in zip(
                result["documents"][0],
                result["metadatas"][0],
                result["distances"][0],
            )
        ]

    def get_by_filter(self, where: dict) -> list[dict]:
        result = self._collection.get(
            where=where,
            include=["documents", "metadatas"],
        )
        return [
            {"content": doc, "metadata": meta, "distance": 0.0}
            for doc, meta in zip(result["documents"], result["metadatas"])
        ]
