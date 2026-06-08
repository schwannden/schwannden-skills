# Recipe: fundamentals over products

**Rule:** design in fundamentals first; name a branded product only as an
example, and never without the trade-off it buys. "X because Y at Z scale," not
a bare service name. Relying on a pre-built product without understanding its
internals is the single most-flagged anti-signal in a senior design.

## Think in primitives, not brands

Reach for the capability; the product is an instance of it.

| You need... | The primitive | Products are just instances |
|---|---|---|
| Durable, ordered, replayable event transport | append-only log / partitioned queue | Kafka, Kinesis, Pub/Sub, RabbitMQ |
| Single-digit-ms KV at scale, tunable consistency | partitioned KV store | DynamoDB, Cassandra, Bigtable, Redis |
| Cross-region strong consistency / transactions | consensus-backed CP store | Spanner, CockroachDB, etcd/Raft |
| Cheap, durable, high-throughput blobs | object store | S3, GCS, Azure Blob |
| Low-latency global reads of static/semi-static data | CDN / edge cache | CloudFront, Fastly, Cloudflare |
| Approximate counting in a stream | sketch | Count-Min Sketch, HyperLogLog |
| Fair, bounded request admission | token/leaky bucket | per-key counters in any fast KV |

Pick the primitive from the requirement, then justify the product by the
trade-off it makes vs the obvious alternative (cost, consistency, ops burden).

## Confirm currency before committing (any cloud)

Capabilities, limits, and pricing drift. When a design leans on a specific
service, confirm its **current** behavior rather than trusting memory:

1. **Read the official docs** for the candidate service — capability, the
   relevant limit/quota that affects capacity (throughput caps, payload sizes,
   partition limits, regional availability), and current pricing. Use the
   provider's docs tooling if available (e.g. an AWS-docs MCP server), otherwise
   `WebSearch` the official docs domain.
2. **Check for recent changes** — a "what's new" / release-notes page; a
   feature released last quarter can change the design.
3. **Cite the doc URL** for any limit or capability the design relies on.
4. **Flag anything unconfirmed** as an assumption to validate.

## What to record per choice

- The capability you're relying on + the doc URL.
- The current relevant limit/quota.
- The trade-off vs the obvious alternative (cost, consistency, ops).

Output looks like: "On-demand KV here — single-digit-ms reads, no capacity
planning, ~$X/M reads; the trade-off vs provisioned is cost at steady high QPS.
[doc URL]"
