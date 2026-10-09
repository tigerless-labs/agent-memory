import pytest
from agent_memory.core.chunking import Chunk
from agent_memory.core.database import Database
from agent_memory.core.vector_index import VectorIndex


class Embedder:
    def __init__(self, values):
        self.values = values

    def embed_documents(self, texts):
        return self.values

    def embed_query(self, text):
        return self.values[0]


@pytest.mark.parametrize("values", [[[]], [[float("nan")]], [[float("inf")]], [[1e100]]])
def test_bad_backend_output_preserves_previous_vectors(store, values):
    record = store.record(type="decision", name="vector-fixture", abstract="Vector fixture")
    chunks = [Chunk("abstract", "", "", "Vector fixture")]
    with Database(store.layout).connect() as connection:
        index = VectorIndex(connection, Embedder([[1.0]]), "synthetic")
        index.upsert("decision/vector-fixture.md", "original", record, chunks)
        index._embedder = Embedder(values)
        with pytest.raises((ValueError, OverflowError)):
            index.upsert("decision/vector-fixture.md", "replacement", record, chunks)
        assert index.known()["decision/vector-fixture.md"][0] == "original"


def test_model_dimensions_cannot_change_between_batches_or_queries(store):
    first = store.record(type="decision", name="first", abstract="First fixture")
    second = store.record(type="decision", name="second", abstract="Second fixture")
    chunks = [Chunk("abstract", "", "", "Fixture")]
    with Database(store.layout).connect() as connection:
        index = VectorIndex(connection, Embedder([[1.0, 0.0]]), "synthetic")
        index.upsert("first.md", "original", first, chunks)
        index._embedder = Embedder([[1.0, 0.0, 0.0]])
        with pytest.raises(ValueError, match="dimensions"):
            index.upsert("second.md", "new", second, chunks)
        assert "second.md" not in index.known()
        assert index.known()["first.md"][0] == "original"
        with pytest.raises(ValueError, match="dimensions"):
            index.match("fixture", 5)
