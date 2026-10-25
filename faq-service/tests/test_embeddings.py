from threading import Lock
from unittest.mock import MagicMock

import pytest

from app.embeddings import Embedder


def test_oversized_chunks_fail_instead_of_being_silently_truncated():
    embedder = Embedder.__new__(Embedder)
    embedder._lock = Lock()
    embedder.model = MagicMock()
    embedder.model.token_count.return_value = 512
    with pytest.raises(ValueError, match="512-token"):
        embedder.documents(["An overly long FAQ answer."])
    embedder.model.passage_embed.assert_not_called()


@pytest.mark.parametrize("values", [[0.0] * 383, [float("nan")] * 384, [float("inf")] * 384])
def test_invalid_embedding_vectors_are_rejected(values):
    with pytest.raises(ValueError, match="Invalid embedding"):
        Embedder._checked(values)
