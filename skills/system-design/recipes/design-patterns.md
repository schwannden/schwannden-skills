# Recipe: reusable design patterns

Reach for these proven primitives before inventing new ones. Each is a distilled,
vendor-neutral pattern; the `guides/` column points at a worked design that uses
it in full depth.

| Pattern | Reach for it when... | Worked in |
|---|---|---|
| **Epoch-bump revocation** — monotonic per-user integer; tokens carry the epoch at issue, server rejects any lower epoch. O(1) "log out everywhere" without enumerating sessions. | You need fast, cheap global revocation of stateless tokens. | `10-session-management`, `06-sso-auth-service` |
| **Session-authority vs delegation** — after a third party attests identity, re-issue your *own* identity; never pass raw external claims through. | A federated / third-party identity enters the system. | `06-sso-auth-service`, `07-oauth-oidc` |
| **Fail-closed routing with per-dependency circuit breakers** — when an external endpoint is down, refuse rather than guess; isolate the breaker per tenant-type so one bad dependency can't take the fleet down. | A request path depends on an external/per-tenant endpoint. | `06-sso-auth-service`, `09-multi-tenant-saas` |
| **Pub/sub → queue → consumer with monotonic last-write-wins** — producer stamps a timestamp; consumer keeps the max; stale/out-of-order events log+ack (not DLQ). Structural idempotency + ordering. | Cross-service state must sync reliably with idempotency + ordering. | `08-webhook-delivery`, `09-multi-tenant-saas` |
| **`state` token double duty** — one nonce binds the browser session (login-CSRF guard) *and* binds a cross-flow handoff. | A browser-redirect flow needs CSRF defense + session binding. | `07-oauth-oidc` |
| **Opaque single-use code, server-to-server redemption** — claims never ride a URL/fragment/Referer; the browser hop is PII-free; an atomic get-and-delete is the replay guard. | Sensitive claims must not traverse the browser. | `07-oauth-oidc`, `06-sso-auth-service` |
| **Hosts pinned to a code-level namespace** — per-tenant routing chosen from a code-level template map, never a payload/config-injected host. | Per-tenant routing could otherwise become SSRF / open-redirect. | `09-multi-tenant-saas`, `15-realtime-chat-security` |
| **Hybrid fan-out** — fan-out-on-write for the common case, fan-out-on-read for the few high-fan-out producers (celebrities); pick per-producer by a threshold. | A feed/notification system has a heavy-tailed fan-out distribution. | `02-news-feed`, `13-realtime-chat` |
| **Sketch-based approximate counting** — Count-Min Sketch / HyperLogLog with a watermark for late arrivals, instead of exact per-key counters. | Top-K / cardinality over a high-volume stream, exactness not required. | `03-top-k-trending` |
| **Single-flight / request coalescing** — collapse concurrent misses for the same key into one origin fetch. | A hot key would otherwise stampede the origin on cache miss. | `01-url-shortener`, `05-rate-limiter` |
| **Pseudonymous routing key** — `HMAC(normalize(identifier), secret)` as a routing/partition key so the directory holds no plaintext PII and resists dictionary attack. | A global directory must route by an identifier without storing it in the clear. | `11-data-residency-migration` |
| **Step-up assurance via a secondary short-lived credential** — elevate assurance for sensitive ops in a separate cookie/token, cleared on revoke. | One operation needs higher assurance than the base session. | `10-session-management`, `06-sso-auth-service` |

These are distilled patterns — load the matching guide for the full worked
design, the numbers, and the failure analysis. Cite the pattern, don't reinvent
it.
