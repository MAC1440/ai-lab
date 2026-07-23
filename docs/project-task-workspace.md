# Project task workspace

Project tasks use a backend-owned staged lifecycle. The frontend displays and
controls that lifecycle; it does not ask a general chat model to coordinate it.

```text
create
  -> planning model
  -> deterministic context freeze
  -> generation model
  -> source validation
  -> atomic review
  -> transactional apply
  -> verification
  -> complete | bounded repair
```

## Stream endpoints

- `POST /project-tasks/{task_id}/run/stream`
- `POST /project-tasks/{task_id}/approve-and-verify/stream`
- `POST /project-tasks/{task_id}/repair/stream`

All return `application/x-ndjson`. They are not ordinary JSON responses.

The shared browser parser handles arbitrary chunk boundaries, CRLF/LF, a final
line without a newline, malformed events, missing response bodies, HTTP errors,
and request cancellation.

## Approval boundary

The task workspace renders individual diffs in review-only mode. A project task
is approved as one complete change set. The approval endpoint applies the set
transactionally and starts verification immediately.

If verification was cancelled after application, retrying checks validates that
all proposals are already approved and skips application. This prevents a
second write of the same change set.

## Repair boundary

A repair model receives:

- the original bounded goal;
- captured verification output;
- the current contents of paths from the applied change set.

It may return only complete-file `update` operations for those paths. A repair
cannot create, delete, move, or modify unrelated files.
