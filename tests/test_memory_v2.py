"""Tests for vector memory module."""
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def mock_chromadb():
    with patch("memory_v2.VECTOR_AVAILABLE", True), patch("memory_v2.Settings", create=True), patch("memory_v2.chromadb") as mock:
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock.PersistentClient.return_value = mock_client
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_collection.count.return_value = 0
        yield mock_client, mock_collection


@pytest.fixture
def mock_embedder():
    with patch("memory_v2.SentenceTransformer") as mock:
        mock_instance = MagicMock()
        import numpy as np
        mock_instance.encode.return_value = np.array([0.1] * 384)
        mock.return_value = mock_instance
        yield mock_instance


def test_vector_memory_init(mock_chromadb, mock_embedder):
    from memory_v2 import VectorMemory
    vm = VectorMemory()
    vm._init()
    assert vm.is_available() is True


def test_add_conversation(mock_chromadb, mock_embedder):
    from memory_v2 import VectorMemory
    vm = VectorMemory()
    vm._init()

    mock_client, mock_collection = mock_chromadb
    doc_id = vm.add_conversation("Hello", "Hi there!")

    assert doc_id != ""
    mock_collection.add.assert_called_once()
    call_args = mock_collection.add.call_args
    assert call_args[1]["ids"][0] == doc_id
    assert "User: Hello" in call_args[1]["documents"][0]
    assert "Assistant: Hi there!" in call_args[1]["documents"][0]


def test_add_fact(mock_chromadb, mock_embedder):
    from memory_v2 import VectorMemory
    vm = VectorMemory()
    vm._init()

    doc_id = vm.add_fact("Python is a programming language", "tech")

    assert doc_id != ""
    mock_chromadb[1].add.assert_called_once()
    call_args = mock_chromadb[1].add.call_args
    assert call_args[1]["documents"][0] == "Python is a programming language"
    assert call_args[1]["metadatas"][0]["type"] == "fact"
    assert call_args[1]["metadatas"][0]["category"] == "tech"


def test_add_code_snippet(mock_chromadb, mock_embedder):
    from memory_v2 import VectorMemory
    vm = VectorMemory()
    vm._init()

    code = "print('hello')"
    doc_id = vm.add_code_snippet(code, "python", "Print hello")

    assert doc_id != ""
    call_args = mock_chromadb[1].add.call_args
    assert "Description: Print hello" in call_args[1]["documents"][0]
    assert "print('hello')" in call_args[1]["documents"][0]
    assert call_args[1]["metadatas"][0]["type"] == "code"
    assert call_args[1]["metadatas"][0]["language"] == "python"


def test_search(mock_chromadb, mock_embedder):
    from memory_v2 import VectorMemory
    vm = VectorMemory()
    vm._init()

    mock_client, mock_collection = mock_chromadb
    mock_collection.query.return_value = {
        "ids": [["id1", "id2"]],
        "documents": [["doc1", "doc2"]],
        "metadatas": [[{"type": "fact"}, {"type": "conversation"}]],
        "distances": [[0.1, 0.3]]
    }

    results = vm.search("test query", n_results=2)

    assert len(results) == 2
    assert results[0]["id"] == "id1"
    assert results[0]["similarity"] == 0.9  # 1 - 0.1
    assert results[1]["similarity"] == 0.7  # 1 - 0.3
    mock_collection.query.assert_called_once()


def test_search_with_filter(mock_chromadb, mock_embedder):
    from memory_v2 import VectorMemory
    vm = VectorMemory()
    vm._init()

    mock_collection = mock_chromadb[1]
    mock_collection.query.return_value = {
        "ids": [["id1"]],
        "documents": [["fact doc"]],
        "metadatas": [[{"type": "fact"}]],
        "distances": [[0.2]]
    }

    results = vm.search("query", n_results=5, filter_type="fact")

    assert len(results) == 1
    call_args = mock_collection.query.call_args
    assert call_args[1]["where"] == {"type": "fact"}


def test_search_conversations(mock_chromadb, mock_embedder):
    from memory_v2 import VectorMemory
    vm = VectorMemory()
    vm._init()

    mock_collection = mock_chromadb[1]
    mock_collection.query.return_value = {
        "ids": [["id1"]],
        "documents": [["User: Hi\nAssistant: Hello"]],
        "metadatas": [[{"type": "conversation"}]],
        "distances": [[0.1]]
    }

    results = vm.search_conversations("hi")

    assert len(results) == 1
    call_args = mock_collection.query.call_args
    assert call_args[1]["where"] == {"type": "conversation"}


def test_search_facts(mock_chromadb, mock_embedder):
    from memory_v2 import VectorMemory
    vm = VectorMemory()
    vm._init()

    mock_collection = mock_chromadb[1]
    mock_collection.query.return_value = {
        "ids": [["id1"]],
        "documents": [["Python is great"]],
        "metadatas": [[{"type": "fact"}]],
        "distances": [[0.1]]
    }

    results = vm.search_facts("python")

    assert len(results) == 1
    call_args = mock_collection.query.call_args
    assert call_args[1]["where"] == {"type": "fact"}


def test_search_code(mock_chromadb, mock_embedder):
    from memory_v2 import VectorMemory
    vm = VectorMemory()
    vm._init()

    mock_collection = mock_chromadb[1]
    mock_collection.query.return_value = {
        "ids": [["id1"]],
        "documents": [["Code snippet"]],
        "metadatas": [[{"type": "code"}]],
        "distances": [[0.1]]
    }

    results = vm.search_code("python")

    assert len(results) == 1
    call_args = mock_collection.query.call_args
    assert call_args[1]["where"] == {"type": "code"}


def test_get_recent_context(mock_chromadb, mock_embedder):
    from memory_v2 import VectorMemory
    vm = VectorMemory()
    vm._init()

    mock_client, mock_collection = mock_chromadb
    mock_collection.get.return_value = {
        "ids": ["id1", "id2"],
        "documents": ["doc1", "doc2"],
        "metadatas": [
            {"timestamp": "2024-01-02T00:00:00", "type": "conversation"},
            {"timestamp": "2024-01-01T00:00:00", "type": "conversation"},
        ]
    }

    results = vm.get_recent_context(2)

    assert len(results) == 2
    # Should be sorted by timestamp descending (most recent first)
    assert results[0]["metadata"]["timestamp"] == "2024-01-02T00:00:00"
    assert results[1]["metadata"]["timestamp"] == "2024-01-01T00:00:00"


def test_delete(mock_chromadb, mock_embedder):
    from memory_v2 import VectorMemory
    vm = VectorMemory()
    vm._init()

    result = vm.delete("test-id")

    assert result is True
    mock_chromadb[1].delete.assert_called_once_with(ids=["test-id"])


def test_clear_all(mock_chromadb, mock_embedder):
    from memory_v2 import VectorMemory
    vm = VectorMemory()
    vm._init()

    mock_client, mock_collection = mock_chromadb

    result = vm.clear_all()

    assert result is True
    mock_client.delete_collection.assert_called_once_with("barq_memory")


def test_stats(mock_chromadb, mock_embedder):
    from memory_v2 import VectorMemory
    vm = VectorMemory()
    vm._init()

    mock_client, mock_collection = mock_chromadb
    mock_collection.count.return_value = 10
    mock_collection.get.return_value = {
        "metadatas": [
            {"type": "conversation"},
            {"type": "fact"},
            {"type": "fact"},
            {"type": "code"},
        ]
    }

    stats = vm.stats()

    assert stats["available"] is True
    assert stats["total_documents"] == 10
    assert stats["by_type"]["conversation"] == 1
    assert stats["by_type"]["fact"] == 2
    assert stats["by_type"]["code"] == 1


def test_unavailable_when_not_installed():
    """Test graceful degradation when chromadb not installed."""
    with patch("memory_v2.VECTOR_AVAILABLE", False):
        from memory_v2 import VectorMemory
        vm = VectorMemory()
        assert vm.is_available() is False
        assert vm.add_conversation("a", "b") == ""
        assert vm.add_fact("fact") == ""
        assert vm.search("query") == []
        assert vm.stats() == {"available": False}
