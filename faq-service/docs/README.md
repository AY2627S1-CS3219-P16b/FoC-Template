# FAQ knowledge base

Source documents for the RAG-based FAQ assistant (N2H1). The indexer
splits each content file into one chunk per `##` question. This README is not
indexed. See [service setup](../README.md) for startup and index refresh commands.

| File                 | Covers                                                              |
| -------------------- | ------------------------------------------------------------------- |
| `getting-started.md` | What FoC is, registering, logging in, requester vs courier mode     |
| `credits.md`         | Starting credits, reserve / transfer / release, balance and history |
| `requesting.md`      | Creating, tracking, cancelling and confirming errand requests       |
| `couriers.md`        | Finding, accepting and completing errands                           |
| `suppliers.md`       | Suppliers, locations, opening hours                                 |
| `account.md`         | Profile, account status, admin access                               |

## Writing rules

- One question per `##` heading, phrased the way a student would ask it.
- Each answer must make sense on its own: it may be retrieved without the rest
  of the file, so don't write "as above".
- Use the names shown in the UI ("My Requests", "Courier Mode"), not internal
  names such as `RESERVING` (add the internal name only in brackets if useful).
- Keep answers to 2–6 sentences.

## Review comments

`<!-- REVIEW: … -->` marks an answer that depends on behaviour that is unfinished,
differs from the backlog, or may change. Update the answer when the code
changes, then delete the comment.

**Ingestion must strip HTML comments** (`<!-- … -->`) before chunking, so review
notes and the disclosure header never reach the assistant.
