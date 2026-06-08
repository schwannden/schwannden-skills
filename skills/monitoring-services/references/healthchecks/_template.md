# Per-service healthcheck template

Copy this file to `references/healthchecks/<service>.md` (one per service) and
fill in the placeholders. It is the single source of truth for *what to query*
and *how* for one service. The monitoring workflow loads this file first.

> Replace every `<...>` placeholder. The example below uses placeholder services
> `web-api`, `worker`, and `auth-api` and synthetic resource names — none of these
> are real.

## Table of contents

1. [Service identity](#1-service-identity)
2. [Metrics backend](#2-metrics-backend)
3. [Components to check](#3-components-to-check)
4. [Tracked metrics and query templates](#4-tracked-metrics-and-query-templates)
5. [Dynamic resource discovery](#5-dynamic-resource-discovery)
6. [Service-specific baselines and chronic patterns](#6-service-specific-baselines-and-chronic-patterns)

---

## 1. Service identity

| Resource | Value |
|----------|-------|
| Service name | `<web-api>` |
| Compute (cluster/service, deployment, function) | `<compute id>` |
| Load balancer / ingress | `<lb id>` |
| Primary datastore | `<db id>` |
| Cache | `<cache id>` |
| Queue / stream | `<queue id>` |

## 2. Metrics backend

State exactly how to reach metrics for this service. Keep credentials out of the
file — reference an env var or a named profile.

| Field | Value |
|-------|-------|
| Backend | `<CloudWatch | Prometheus | Datadog | SQL>` |
| Endpoint / profile / region | `<e.g. profile=my-profile region=<your-region>>` |
| Auth | `<env var or profile name — never an inline secret>` |

## 3. Components to check

List only the components this service actually uses, and the user-impact signal
for each. Do not load reference material for components the service does not use.

- User-impact signals (check FIRST): `<error rate metric>`, `<p99 latency metric>`,
  `<DLQ depth / failed records / lag metric>`.
- Infra: `<load balancer>`, `<compute>`, `<datastore>`, `<cache>`, `<queue>`.

## 4. Tracked metrics and query templates

For each metric give a copy-paste-ready command. One CloudWatch example:

```bash
# web-api p99 request latency, last 2h, 60s resolution
START=$(date -u -v-2H "+%Y-%m-%dT%H:%M:%SZ")   # GNU date: date -u -d '2 hours ago'
END=$(date -u "+%Y-%m-%dT%H:%M:%SZ")
aws --profile "$AWS_PROFILE" --region "$AWS_REGION" cloudwatch get-metric-statistics \
  --namespace "<YourNamespace>" --metric-name "<request-latency>" \
  --start-time "$START" --end-time "$END" --period 60 \
  --extended-statistics p99
```

A Prometheus example for the same idea:

```bash
# web-api p99 over the last 2h
curl -sG "$PROM_URL/api/v1/query" \
  --data-urlencode 'query=histogram_quantile(0.99, sum by (le) (rate(http_request_duration_seconds_bucket{service="web-api"}[5m])))'
```

Repeat one block per tracked metric. Keep the metric list in sync with
`baselines.md` and with the `METRICS` list in `scripts/refresh_baselines.py`.

## 5. Dynamic resource discovery

If a resource id changes between deploys (e.g. a blue/green target group flips on
each release), DO NOT hardcode it — discover it at the start of each run:

```bash
# Example: resolve the currently-active target group before querying it
aws --profile "$AWS_PROFILE" --region "$AWS_REGION" ecs describe-services \
  --cluster "<cluster>" --services "<service>" \
  --query 'services[0].loadBalancers[0].targetGroupArn' --output text
```

If a resource-scoped query returns zero datapoints while the service-level signal
shows healthy traffic, suspect a stale id from a deploy flip and re-discover.

## 6. Service-specific baselines and chronic patterns

- Baselines: `references/baselines.md` (the `<web-api>` section).
- Known-chronic patterns: `references/known-chronic.md` (the `<web-api>` entries).
- When you close an investigation, write the lesson back into those two files so
  the next run inherits it.
