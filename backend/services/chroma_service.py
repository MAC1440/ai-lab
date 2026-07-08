import chromadb
from typing import List, Dict, Any, Optional


class ChromaService:
    def __init__(self, db_path: str = "./chroma_db", collection_name: str = "unity_docs"):
        self.client = chromadb.PersistentClient(path=db_path)
        self.collection = self.client.get_or_create_collection(name=collection_name)

    def add_chunks(
        self,
        chunks: List[str],
        embeddings: List[List[float]],
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ):
        ids = [f"chunk_{i}" for i in range(len(chunks))]

        self.collection.add(
            ids=ids,
            documents=chunks,
            embeddings=embeddings,
            metadatas=metadatas or [{} for _ in chunks],
        )

        return {
            "added": len(chunks),
            "ids": ids,
        }

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 3,
    ):
        return self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
        )

    def clear(self):
        self.client.delete_collection(name=self.collection.name)
        self.collection = self.client.get_or_create_collection(name=self.collection.name)

        return {"cleared": True}