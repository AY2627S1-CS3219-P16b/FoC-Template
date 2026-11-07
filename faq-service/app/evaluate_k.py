# AI Assistance Disclosure:
# Tool: Claude Code (Claude Opus 5.5), date: 2026-11-07
# Scope: Generated this retrieval-depth comparison script from app/evaluate.py.
# Author review: Chong Yi Jie reviewed the script and its results.
"""Compare retrieval depth (top-k) on the curated questions.

Run with `python -m app.evaluate_k` inside the FAQ image. Like app.evaluate, it
needs no PostgreSQL or Anthropic calls: it embeds the FAQ chunks locally and
applies the same cosine similarity and FAQ_MIN_SIMILARITY threshold as the API.
"""

import json
from pathlib import Path

import numpy as np

from .config import Settings
from .embeddings import Embedder
from .knowledge import load_corpus

DEPTHS = (1, 2, 3, 4, 5, 8)


def main():
    settings = Settings.from_env()
    corpus = load_corpus(settings.docs_dir)
    cases = json.loads((Path(__file__).resolve().parents[1] / "evaluation/questions.json").read_text())
    embedder = Embedder(settings)
    vectors = np.array(embedder.documents([chunk.text for chunk in corpus.chunks]))
    norms = np.linalg.norm(vectors, axis=1)
    questions = [chunk.question for chunk in corpus.chunks]

    rows = []
    for case in cases:
        query = np.array(embedder.query(case["question"]))
        scores = vectors @ query / (norms * np.linalg.norm(query))
        order = np.argsort(-scores)
        rank = None
        if case["expected"]:
            rank = 1 + int(np.where(np.array(questions)[order] == case["expected"])[0][0])
        rows.append({
            "question": case["question"], "expected": case["expected"], "rank": rank,
            "kind": case.get("kind", "clear"),
            "expected_score": round(float(scores[questions.index(case["expected"])]), 3) if case["expected"] else None,
            "sorted_scores": [float(scores[i]) for i in order],
        })
        print(json.dumps({key: rows[-1][key] for key in ("question", "kind", "expected", "rank", "expected_score")}))

    supported = [row for row in rows if row["expected"]]
    unrelated = [row for row in rows if not row["expected"]]
    threshold = settings.min_similarity
    summary = []
    for k in DEPTHS:
        in_rank = sum(row["rank"] <= k for row in supported)
        retrieved = sum(row["rank"] <= k and row["expected_score"] >= threshold for row in supported)
        sent = [sum(score >= threshold for score in row["sorted_scores"][:k]) for row in supported]
        rejected = sum(not any(score >= threshold for score in row["sorted_scores"][:k]) for row in unrelated)
        summary.append({
            "k": k,
            "expected_in_top_k": f"{in_rank}/{len(supported)}",
            "retrieved_after_threshold": f"{retrieved}/{len(supported)}",
            "avg_chunks_sent_to_claude": round(float(np.mean(sent)), 2),
            "max_chunks_sent_to_claude": int(max(sent)),
            **{f"retrieved_{kind}": "{}/{}".format(
                sum(row["rank"] <= k and row["expected_score"] >= threshold for row in group), len(group))
               for kind in ("clear", "vague")
               for group in [[row for row in supported if row["kind"] == kind]]},
            "unrelated_rejected": f"{rejected}/{len(unrelated)}",
        })
    mrr = float(np.mean([1 / row["rank"] for row in supported]))
    print(json.dumps({"chunks": len(corpus.chunks), "threshold": threshold, "mrr": round(mrr, 3)}))
    for line in summary:
        print(json.dumps(line))


if __name__ == "__main__":
    main()
