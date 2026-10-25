"""Run explicitly after editing FAQ answers: python -m app.ingest."""

import argparse
import json

from .config import EMBEDDING_MODEL, Settings
from .database import Store, create_database
from .embeddings import Embedder
from .knowledge import load_corpus


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Re-embed even if the index is current.")
    args = parser.parse_args()
    settings = Settings.from_env()
    corpus = load_corpus(settings.docs_dir)
    engine = create_database(settings.database_url)
    try:
        store = Store(engine)
        store.initialize()
        if not args.force and store.status(corpus.version):
            print(json.dumps({"event": "faq_index_unchanged", "version": corpus.version}))
            return
        embedder = Embedder(settings)
        vectors = embedder.documents([chunk.text for chunk in corpus.chunks])
        store.replace_index(corpus, vectors)
        print(json.dumps({"event": "faq_index_updated", "chunks": len(corpus.chunks),
                          "model": EMBEDDING_MODEL, "version": corpus.version}))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
