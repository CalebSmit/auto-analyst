# fixtures/llm/

**What belongs here.** Recorded model responses, one JSON file per call, named by the
first 32 characters of the request's content hash. The fake LLM adapter replays these,
which is how phases 4-10 build the whole engine with no API key and no cost.

**What does not.** Client data. A recording is made from a masked payload or a synthetic
one, always - the same rule as every other fixture directory.

## The format

```json
{
  "request_hash": "sha256:...",
  "model": "claude-sonnet-5",
  "text": "the response",
  "stop_reason": "end_turn",
  "usage": {"input_tokens": 120, "output_tokens": 8}
}
```

A missing fixture is an error naming the hash and this directory - never an invented
response. Every test downstream of a made-up answer is meaningless, and nothing about it
looks wrong.

A changed prompt hashes differently, so it is a miss rather than a stale answer quietly
reused. That is the intended behaviour: a changed prompt is a different call.
