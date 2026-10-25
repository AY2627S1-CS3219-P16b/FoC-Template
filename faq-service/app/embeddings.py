"""CPU embeddings loaded once; document encoding happens only during indexing."""

from threading import Lock

import numpy as np
from fastembed import TextEmbedding

from .config import EMBEDDING_DIMENSIONS, EMBEDDING_MODEL


class Embedder:
    def __init__(self, settings):
        self.model = TextEmbedding(
            model_name=EMBEDDING_MODEL, cache_dir=str(settings.model_cache),
            threads=settings.embedding_threads, local_files_only=settings.local_files_only,
        )
        self._lock = Lock()
        # Warm ONNX up before the API becomes ready, including on a cached model.
        self.query("How do I use Friend on Campus?")

    @staticmethod
    def _checked(vector):
        values = np.asarray(vector, dtype=np.float32)
        if values.shape != (EMBEDDING_DIMENSIONS,) or not np.isfinite(values).all():
            raise ValueError("Invalid embedding output.")
        return values.tolist()

    def query(self, question):
        with self._lock:
            return self._checked(next(iter(self.model.query_embed(question))))

    def documents(self, texts):
        with self._lock:
            texts = list(texts)
            if any(self.model.token_count(text) >= 512 for text in texts):
                raise ValueError("A FAQ chunk reaches the embedding model's 512-token limit. Split it into shorter questions.")
            return [self._checked(vector) for vector in self.model.passage_embed(texts, batch_size=32)]
