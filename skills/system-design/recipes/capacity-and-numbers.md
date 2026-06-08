# Recipe: capacity and numbers

**Rule:** when a design needs a number, get one — measure it if it's
measurable, estimate it from first principles if it isn't — and name *which*
decision the number drove. A design choice with no number behind it is a guess
wearing a suit.

## Measure when you can

If a real system exists, pull the real number instead of guessing:

- **Live traffic / latency** — metrics backend (CloudWatch, Prometheus,
  Datadog, ...): QPS, p50/p99, error rate, payload size distribution.
- **User/activity volumes** — analytics or logs (DAU/MAU, adoption, read:write
  ratio).
- **Storage growth** — current size + growth rate per table/bucket.
- **Bound every time-ranged query.** Loop in windows over an indexed column;
  don't issue an unbounded "ever happened" scan over a huge table.

If a repo exists, a code-exploration subagent can find the models, hot paths,
and existing limits that pin the numbers down.

## Estimate from first principles when you can't

Greenfield or interview: state the assumption, do the napkin math, and mark it
for validation. The skeleton:

```
DAU × actions/user/day            → writes/day
writes/day ÷ 86,400               → avg write QPS
avg QPS × peak factor (5–10×)     → peak QPS   (size for peak, not average)
peak QPS × payload bytes          → bytes/s, then ÷ shard throughput → shard count
writes/day × payload × retention  → storage; × replication factor   → provisioned
reads:writes ratio                → read QPS → cache hit rate → origin QPS
```

Useful anchors to keep in your head: 1 day ≈ 86.4k s; "millions/day" ≈ tens of
QPS; a single primary RDBMS comfortably does low-thousands of writes/s; one
cache node does ~100k+ ops/s; RAM is ~$/GB-month, object storage is ~cents/GB.

## Close the loop

Bring the number back into the design and say the decision it changed:
"at 10k QPS × 200-byte payload that's 2 MB/s per shard, so one shard covers it —
sharding is for blast-radius, not throughput." A number that didn't change a
decision didn't need computing; the one that did is the one to call out.
