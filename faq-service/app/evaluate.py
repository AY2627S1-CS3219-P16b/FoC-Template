"""Local retrieval smoke evaluation; no PostgreSQL or Anthropic calls needed."""

import json
from pathlib import Path
from time import perf_counter

import numpy as np

from .config import Settings
from .embeddings import Embedder
from .knowledge import load_corpus


def main():
    settings = Settings.from_env()
    corpus = load_corpus(settings.docs_dir)
    cases = json.loads((Path(__file__).resolve().parents[1] / "evaluation/questions.json").read_text())
    embedder = Embedder(settings)
    started = perf_counter()
    vectors = np.array(embedder.documents([chunk.text for chunk in corpus.chunks]))
    indexing_ms = (perf_counter() - started) * 1000
    latencies, hits, supported, ood_rejected, ood_count = [], 0, 0, 0, 0
    for case in cases:
        started = perf_counter()
        query = np.array(embedder.query(case["question"]))
        scores = vectors @ query / (np.linalg.norm(vectors, axis=1) * np.linalg.norm(query))
        best = np.argsort(-scores)[:4]
        latencies.append((perf_counter() - started) * 1000)
        selected = [corpus.chunks[i].question for i in best if scores[i] >= settings.min_similarity]
        if case["expected"]:
            supported += 1
            hits += case["expected"] in selected
        else:
            ood_count += 1
            ood_rejected += not selected
        print(json.dumps({"question": case["question"], "expected": case["expected"],
                          "top_score": round(float(scores[best[0]]), 4), "retrieved": selected}))
    print(json.dumps({"chunks": len(corpus.chunks), "indexing_ms": round(indexing_ms, 2),
                      "supported_recall_at_4": f"{hits}/{supported}",
                      "out_of_scope_rejected_by_threshold": f"{ood_rejected}/{ood_count}",
                      "embedding_and_in_memory_search_p50_ms": round(float(np.median(latencies)), 2),
                      "embedding_and_in_memory_search_p95_ms": round(float(np.percentile(latencies, 95)), 2)}))
    if hits != supported:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
