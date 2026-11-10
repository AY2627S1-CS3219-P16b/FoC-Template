# FAQ retrieval evaluation

Run: 2026-11-11 inside the FAQ service Docker image, with 65 FAQ entries and
`FAQ_MIN_SIMILARITY=0.60`. The test set in `evaluation/questions.json` has 100
questions:

- 85 supported questions covering all 65 FAQ entries: 71 clearly worded and 14
  vague ones (marked `"kind": "vague"`, e.g. "cancel", "balance", "stuck pending").
- 15 unrelated questions, including NUS questions that look close to FoC topics
  (NUSNET password, hostel applications) and a prompt-injection attempt.

## Retrieval depth (top-k)

From `python -m app.evaluate_k`. "Retrieved" means the expected entry is in the
top k and passes the threshold, which is what the API sends to Claude.

| k | Expected entry in top k | Retrieved (all) | Clear | Vague | Avg chunks sent to Claude | Unrelated rejected by threshold |
|---|---|---|---|---|---|---|
| 1 | 57 / 85 | 56 / 85 | 47 / 71 | 9 / 14 | 0.95 | 11 / 15 |
| 2 | 71 / 85 | 68 / 85 | 57 / 71 | 11 / 14 | 1.81 | 11 / 15 |
| 3 | 78 / 85 | 74 / 85 | 62 / 71 | 12 / 14 | 2.61 | 11 / 15 |
| 4 | 79 / 85 | 75 / 85 | 63 / 71 | 12 / 14 | 3.35 | 11 / 15 |
| 5 (current) | 81 / 85 | 77 / 85 | 65 / 71 | 12 / 14 | 4.07 | 11 / 15 |
| 8 | 82 / 85 | 77 / 85 | 65 / 71 | 12 / 14 | 5.99 | 11 / 15 |

Mean reciprocal rank of the expected entry: 0.792.

- Of the 77 expected entries that are retrieved, 56 rank 1st, 12 rank 2nd,
  6 rank 3rd, 1 ranks 4th and 2 rank 5th. Recall stops improving at k = 5.
- 8 supported questions miss at k = 5. Six score below 0.60 whatever k is
  ("balance" 0.579, "profile" 0.504, "who are u" 0.541, "When does the canteen
  close?" 0.538); the other two have an expected entry above the threshold but
  ranked below 5th.
- Four unrelated questions pass the threshold: "How do I reset my NUSNET
  password?" (0.727), "How do I apply for a hostel at NUS?" (0.671), "What time
  does the library close?" (0.612) and "Can you do my CS3219 assignment?" (0.602).
  Claude is then the second check; all four were refused live (see below).

### Threshold comparison (k = 5)

The same run at three thresholds. Lowering the threshold retrieves more vague
questions but lets more unrelated questions reach Claude.

| Threshold | Retrieved (all) | Clear | Vague | Unrelated rejected by threshold |
|---|---|---|---|---|
| 0.65 | 70 / 85 | 61 / 71 | 9 / 14 | 13 / 15 |
| 0.60 (current) | 77 / 85 | 65 / 71 | 12 / 14 | 11 / 15 |
| 0.55 | 80 / 85 | 67 / 71 | 13 / 14 | 10 / 15 |

The team chose 0.60.

## End-to-end evaluation (retrieval + generation)

The retrieval table above measures only what reaches Claude. This check measures
what the user actually receives: 20 questions were sent to the running service
(`claude-haiku-5-5`, threshold 0.65, run at k = 4 before the change to k = 5). The
sample was weighted towards hard cases (vague phrasing, out-of-scope NUS
questions), so it is a stress test rather than a picture of typical traffic.

The first run exposed two prompt issues:

- **Meta-references:** one answer described its own knowledge ("The information I
  have covers creating a FoC account") instead of stating the information.
- **Out-of-scope leakage:** the two unrelated NUS questions that passed the
  threshold received a refusal followed by unrelated FoC account-creation steps,
  with a citation.

The system prompt in `app/support.py` now requires Claude to first classify
whether the question concerns FoC and, if not, to cite no sources, so the fixed
fallback is returned. It also explicitly forbids meta-references. Results after
the change:

| Question type | Count | System behaviour | Expected behaviour? |
|---|---|---|---|
| In-scope, relevant entry retrieved | 8 | Grounded answer with citations | Yes |
| Out-of-scope | 4 | Fixed fallback (abstained) | Yes |
| Assistant identity ("who are u") | 1 | Fixed fallback, which describes FoC Help | Acceptable |
| In-scope, relevant entry below threshold | 7 | Fixed fallback (abstained) | No (false negative) |
| Meta-references in any answer | 0 / 20 | | Yes |

No answer was incorrect or ungrounded. The 7 false negatives are retrieval
failures, not generation failures: their expected entry scored below 0.65 (for
example "cancel", "balance", "Can I use it if I'm from NTU?"), so Claude never
received it and correctly abstained rather than answering without evidence. These
are the same threshold misses shown in the retrieval results.

### Live check after lowering the threshold to 0.60

All 15 unrelated questions and the 7 supported questions that 0.60 newly
retrieves were sent to the running service (`claude-haiku-5-5`, k = 5,
threshold 0.60) on 2026-11-09.

| Question type | Count | System behaviour | Expected behaviour? |
|---|---|---|---|
| Unrelated, including the 4 that pass the threshold | 15 | Fixed fallback, no sources | Yes |
| Newly retrieved supported questions ("cancel", "refund", "where is my stuff", "Can I use it if I'm from NTU?", …) | 7 | Grounded answer with citations | Yes |

LLM output varies between runs, so this is a spot check, not a guarantee.
