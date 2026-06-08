# Reference library — 15 canonical system designs

Each guide is a complete golden answer for a 1-hour senior/staff (L5/L6-calibrated)
system-design round, in the 7-section format defined by `GUIDE-FORMAT.md`. Use a
guide as a worked exemplar for its archetype in any mode, or as the private answer
key in Interview mode.

## Archetype map

The five classic archetypes a design rubric tests, plus an identity/security
cluster this library adds. Pick the guide whose shape matches the problem in
front of you.

| Archetype | What it stresses | Guides |
|---|---|---|
| **Stateless scale + storage** | ID generation, hot keys, read-skew, multi-region reads | `01-url-shortener` |
| **Stateful consistency + fan-out** | fan-out-on-write vs -read, ranking, freshness SLOs | `02-news-feed`, `13-realtime-chat` |
| **Real-time / streaming** | windowing, sketches, watermarks, connection management, media transport | `03-top-k-trending`, `12-voice-video-calling`, `14-live-streaming` |
| **Storage / indexing** | chunking, dedup, metadata-index sharding, shared-folder consistency | `04-drive-storage` |
| **Operational / multi-tenant** | quotas, noisy-neighbor, fail-open vs fail-closed, idempotency, DLQ | `05-rate-limiter`, `08-webhook-delivery`, `09-multi-tenant-saas` |
| **Identity / security** | session authority vs delegation, revocation, protocol attacks, E2E crypto, residency | `06-sso-auth-service`, `07-oauth-oidc`, `10-session-management`, `11-data-residency-migration`, `15-realtime-chat-security` |

## Index

| # | Guide | Archetype tag |
|---|---|---|
| 01 | [Distributed URL Shortener](./01-url-shortener.md) | stateless scale + storage |
| 02 | [News Feed (fan-out trade-offs)](./02-news-feed.md) | stateful consistency + fan-out |
| 03 | [Real-Time Top-K / Trending](./03-top-k-trending.md) | real-time / streaming |
| 04 | [Drive-like File Storage](./04-drive-storage.md) | storage / indexing |
| 05 | [Distributed Rate Limiter / Quota](./05-rate-limiter.md) | operational / multi-tenant |
| 06 | [SSO / Authentication Service](./06-sso-auth-service.md) | federated identity / auth platform |
| 07 | [OAuth 2.0 / OIDC Auth-Code Flow](./07-oauth-oidc.md) | protocol security / browser-redirect |
| 08 | [Webhook / Event Delivery](./08-webhook-delivery.md) | async delivery (at-least-once, idempotency, DLQ) |
| 09 | [Multi-Tenant SaaS Platform](./09-multi-tenant-saas.md) | tenant isolation / noisy-neighbor / routing |
| 10 | [Distributed Session Store](./10-session-management.md) | session lifecycle / revocation / multi-device |
| 11 | [Data-Residency Routing & Live Migration](./11-data-residency-migration.md) | geo-partitioned multi-region + live migration |
| 12 | [Real-Time Voice/Video Calling](./12-voice-video-calling.md) | WebRTC media transport |
| 13 | [Real-Time Chat / Messaging](./13-realtime-chat.md) | long-lived connections + fan-out |
| 14 | [Live Video Streaming](./14-live-streaming.md) | ingest → transcode → fan-out |
| 15 | [Securing Real-Time Chat (E2E)](./15-realtime-chat-security.md) | transport security + end-to-end encryption |

Adding a guide? Follow `GUIDE-FORMAT.md` and add a row here.
