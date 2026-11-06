# FAQ retrieval evaluation

Latest run: 2026-11-07, inside the FAQ service Docker image, with
`FAQ_MIN_SIMILARITY=0.65` and 65 FAQ entries.

| Check | Result |
|---|---|
| Supported questions that found their expected FAQ entry in the top four | 16 / 18 |
| Unrelated questions rejected by the threshold | 3 / 3 |
| Warm embedding + in-memory search | 10.8 ms median, 14.45 ms p95 |

Timings exclude PostgreSQL and Claude and vary across machines.

## Known misses

Both are short, vague phrasings that score just under the threshold, so they get
the fallback answer instead of an FAQ answer:

| Question | Expected FAQ entry | Top score |
|---|---|---|
| The runner still hasn't arrived after an hour | My courier is late and my items haven't arrived. What can I do? | 0.629 |
| who are u | Who are you, and what can FoC Help do? | 0.602 |

They stay in the set as known limitations rather than being tuned away.

## Why the threshold stays at 0.65

Lowering it would catch these phrasings, but the margin over unrelated
questions is too small. Other ways of asking who the assistant is scored
0.58-0.63 ("who are you?" 0.578, "what can you do" 0.608, "are you a bot"
0.630), while unrelated questions scored up to 0.52-0.54 ("tell me a joke"
0.524, "Write a JavaScript sorting algorithm" 0.544).

Instead, the fallback answer says what FoC Help can help with and suggests
rephrasing, so a missed question still gets a useful reply. The order "Get help"
suggestions send exact FAQ questions, so they are not affected by the threshold.
