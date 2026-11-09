# FAQ retrieval evaluation

Run: 2026-11-09 inside the FAQ service Docker image, with 65 FAQ entries and
`FAQ_MIN_SIMILARITY=0.65`. The test set in `evaluation/questions.json` has 100
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
| 1 | 57 / 85 | 50 / 85 | 42 / 71 | 8 / 14 | 0.85 | 13 / 15 |
| 2 | 70 / 85 | 61 / 85 | 52 / 71 | 9 / 14 | 1.56 | 13 / 15 |
| 3 | 78 / 85 | 67 / 85 | 58 / 71 | 9 / 14 | 2.15 | 13 / 15 |
| 4 | 79 / 85 | 68 / 85 | 59 / 71 | 9 / 14 | 2.66 | 13 / 15 |
| 5 (current) | 81 / 85 | 70 / 85 | 61 / 71 | 9 / 14 | 3.09 | 13 / 15 |
| 8 | 82 / 85 | 70 / 85 | 61 / 71 | 9 / 14 | 4.25 | 13 / 15 |

Mean reciprocal rank of the expected entry: 0.790.

- Of the 70 expected entries that pass the threshold, 50 rank 1st, 11 rank 2nd,
  6 rank 3rd, 1 ranks 4th and 2 rank 5th. Recall stops improving at k = 5.
- 15 supported questions miss because their expected entry scores below 0.65,
  whatever k is. Vague wording is the main cause: 5 of the 14 vague questions miss
  this way ("cancel" 0.615, "balance" 0.579, "profile" 0.512), compared with 10 of
  the 71 clear ones.
- Two unrelated questions pass the threshold by matching "How do I create an
  account?": "How do I reset my NUSNET password?" (0.727) and "How do I apply for a
  hostel at NUS?" (0.671). Claude is then the second check (see below).

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

LLM output varies between runs, so this is a spot check, not a guarantee.
