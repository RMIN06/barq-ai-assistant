import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

try:
    import chromadb
    from chromadb.config import Settings
    from sentence_transformers import SentenceTransformer
    VECTOR_AVAILABLE = True
except ImportError:
    VECTOR_AVAILABLE = False
    chromadb = None
    SentenceTransformer = None

from config import DATA_DIR
from barqlog import get_logger

log = get_logger("vector_memory")

COLLECTION_NAME = "barq_memory"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # Fast, 384-dim, good quality
PERSIST_DIR = DATA_DIR / "vector_db"


class VectorMemory:
    """Semantic memory using ChromaDB + sentence-transformers."""

    def __init__(self):
        self._client = None
        self._collection = None
        self._embedder = None
        self._initialized = False

    def _init(self):
        """Lazy initialization."""
        if self._initialized:
            return

        if not VECTOR_AVAILABLE:
            log.warning("Vector dependencies not available (chromadb, sentence-transformers)")
            return

        try:
            PERSIST_DIR.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(
                path=str(PERSIST_DIR),
                settings=Settings(anonymized_telemetry=False)
            )
            self._collection = self._client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"}
            )
            self._embedder = SentenceTransformer(EMBEDDING_MODEL, local_files_only=True)
            self._initialized = True
            log.info(f"Vector memory initialized: {self._collection.count()} documents")
        except Exception as e:
            log.error(f"Vector memory init failed: {e}")
            self._initialized = False

    def is_available(self) -> bool:
        return VECTOR_AVAILABLE and self._initialized

    def add_conversation(self, user_msg: str, assistant_msg: str, metadata: Dict = None) -> str:
        """Store a conversation turn."""
        self._init()
        if not self.is_available():
            return ""

        doc_id = str(uuid.uuid4())
        content = f"User: {user_msg}\nAssistant: {assistant_msg}"
        embedding = self._embedder.encode(content).tolist()

        meta = {
            "type": "conversation",
            "timestamp": datetime.now().isoformat(),
            "user_msg": user_msg[:500],
            "assistant_msg": assistant_msg[:500],
        }
        if metadata:
            meta.update(metadata)

        try:
            self._collection.add(
                ids=[doc_id],
                documents=[content],
                embeddings=[embedding],
                metadatas=[meta]
            )
            return doc_id
        except Exception as e:
            log.error(f"Failed to add conversation: {e}")
            return ""

    def add_fact(self, fact: str, category: str = "general", metadata: Dict = None) -> str:
        """Store a fact/knowledge item."""
        self._init()
        if not self.is_available():
            return ""

        doc_id = str(uuid.uuid4())
        embedding = self._embedder.encode(fact).tolist()

        meta = {
            "type": "fact",
            "category": category,
            "timestamp": datetime.now().isoformat(),
            "content": fact[:500],
        }
        if metadata:
            meta.update(metadata)

        try:
            self._collection.add(
                ids=[doc_id],
                documents=[fact],
                embeddings=[embedding],
                metadatas=[meta]
            )
            return doc_id
        except Exception as e:
            log.error(f"Failed to add fact: {e}")
            return ""

    def add_code_snippet(self, code: str, language: str, description: str, metadata: Dict = None) -> str:
        """Store a code snippet with description."""
        self._init()
        if not self.is_available():
            return ""

        doc_id = str(uuid.uuid4())
        content = f"Description: {description}\nCode:\n{code}"
        embedding = self._embedder.encode(content).tolist()

        meta = {
            "type": "code",
            "language": language,
            "description": description[:200],
            "timestamp": datetime.now().isoformat(),
        }
        if metadata:
            meta.update(metadata)

        try:
            self._collection.add(
                ids=[doc_id],
                documents=[content],
                embeddings=[embedding],
                metadatas=[meta]
            )
            return doc_id
        except Exception as e:
            log.error(f"Failed to add code snippet: {e}")
            return ""

    def search(self, query: str, n_results: int = 5, filter_type: str = None) -> List[Dict]:
        """Semantic search over memory."""
        self._init()
        if not self.is_available():
            return []

        try:
            query_embedding = self._embedder.encode(query).tolist()

            where = {}
            if filter_type:
                where["type"] = filter_type

            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where if where else None,
                include=["documents", "metadatas", "distances"]
            )

            items = []
            for i in range(len(results["ids"][0])):
                items.append({
                    "id": results["ids"][0][i],
                    "content": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "distance": results["distances"][0][i],
                    "similarity": 1 - results["distances"][0][i],
                })
            return items
        except Exception as e:
            log.error(f"Search failed: {e}")
            return []

    def search_conversations(self, query: str, n_results: int = 3) -> List[Dict]:
        """Search conversation history."""
        return self.search(query, n_results, filter_type="conversation")

    def search_facts(self, query: str, n_results: int = 3) -> List[Dict]:
        """Search facts."""
        return self.search(query, n_results, filter_type="fact")

    def search_code(self, query: str, n_results: int = 3) -> List[Dict]:
        """Search code snippets."""
        return self.search(query, n_results, filter_type="code")

    def get_recent_context(self, n: int = 5) -> List[Dict]:
        """Get most recent conversation turns (by timestamp)."""
        self._init()
        if not self.is_available():
            return []

        try:
            results = self._collection.get(
                where={"type": "conversation"},
                include=["documents", "metadatas"],
                limit=n
            )
            items = []
            for i in range(len(results["ids"])):
                items.append({
                    "id": results["ids"][i],
                    "content": results["documents"][i],
                    "metadata": results["metadatas"][i],
                })
            # Sort by timestamp descending
            items.sort(key=lambda x: x["metadata"].get("timestamp", ""), reverse=True)
            return items[:n]
        except Exception as e:
            log.error(f"Get recent context failed: {e}")
            return []

    def delete(self, doc_id: str) -> bool:
        """Delete a memory entry."""
        self._init()
        if not self.is_available():
            return False
        try:
            self._collection.delete(ids=[doc_id])
            return True
        except Exception as e:
            log.error(f"Delete failed: {e}")
            return False

    def clear_all(self) -> bool:
        """Clear all memory (use with caution)."""
        self._init()
        if not self.is_available():
            return False
        try:
            self._client.delete_collection(COLLECTION_NAME)
            self._collection = self._client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"}
            )
            return True
        except Exception as e:
            log.error(f"Clear all failed: {e}")
            return False

    def stats(self) -> Dict:
        """Get memory statistics."""
        self._init()
        if not self.is_available():
            return {"available": False}

        try:
            count = self._collection.count()
            # Get type distribution
            all_meta = self._collection.get(include=["metadatas"], limit=10000)
            types = {}
            for meta in all_meta.get("metadatas", []):
                t = meta.get("type", "unknown")
                types[t] = types.get(t, 0) + 1
            return {
                "available": True,
                "total_documents": count,
                "by_type": types,
                "embedding_model": EMBEDDING_MODEL,
            }
        except Exception as e:
            log.error(f"Stats failed: {e}")
            return {"available": False, "error": str(e)}


# Global instance
vector_memory = VectorMemory()


# Convenience functions
def add_conversation(user_msg: str, assistant_msg: str, **metadata) -> str:
    return vector_memory.add_conversation(user_msg, assistant_msg, metadata)


def add_fact(fact: str, category: str = "general", **metadata) -> str:
    return vector_memory.add_fact(fact, category, metadata)


def search_memory(query: str, n_results: int = 5, filter_type: str = None) -> List[Dict]:
    return vector_memory.search(query, n_results, filter_type)


def get_memory_stats() -> Dict:
    return vector_memory.stats()