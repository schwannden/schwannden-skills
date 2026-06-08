#!/usr/bin/env python3
"""Refresh rolling baselines for the metrics this skill tracks.

RUN THIS to refresh baselines (it computes percentiles and prints JSON):

    python3 refresh_baselines.py > baselines_rolling.json

READ THIS AS REFERENCE for the self-refresh pattern: the only thing you must
adapt to your stack is the `fetch_metric` function. Everything else (windowing,
percentiles, per-hour diurnal buckets, error handling, output) is backend-
agnostic and pure standard library.

Why this exists
---------------
Baselines drift as the system grows. A static threshold becomes wrong the quarter
after you write it. Running this on a cadence (at least as often as the
`freshness_threshold_days` in references/baselines.md) keeps the skill's notion of
"normal" honest, so it stops flagging the new normal as an anomaly. This is the
"monitors its own evolution" loop expressed as code.

Dependencies
------------
- Standard library only for the framework below.
- The CloudWatch example backend shells out to the `aws` CLI (no Python SDK
  needed). If you wire a different backend you may need its client library; if so,
  list it here and import it inside `fetch_metric` so this file stays runnable
  with stdlib alone when using the CLI path.

Configuration is via constants and the METRICS list near the top. No magic
numbers are buried in the logic; every tunable is named here.
"""

from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------------------------------
# Configuration (edit these for your stack)
# ---------------------------------------------------------------------------

WINDOW_DAYS = 14          # rolling history window
SAMPLE_PERIOD_SECONDS = 3600  # one sample per hour
MAX_PARALLEL_FETCHES = 8  # how many metric fetches to run concurrently
FETCH_TIMEOUT_SECONDS = 120  # per-fetch timeout

END = datetime.now(timezone.utc).replace(microsecond=0)
START = END - timedelta(days=WINDOW_DAYS)


@dataclass(frozen=True)
class Metric:
    """One tracked metric.

    key:      stable identifier used in the output JSON and in baselines.md.
    diurnal:  if True, also emit a per-UTC-hour percentile breakdown. Set this
              for metrics with a strong daily cycle (cache hit rate, request
              rate, CPU, connection counts) so the agent compares a reading to
              the right hour-of-day band instead of the misleading 24h aggregate.
    backend:  free-form dict the chosen `fetch_metric` implementation understands
              (namespace/metric/dimensions for CloudWatch, a query for Prometheus,
              etc.). Kept opaque here so this framework is backend-agnostic.
    """

    key: str
    diurnal: bool = False
    backend: dict = field(default_factory=dict)


# Keep this list in sync with references/baselines.md and the per-service
# healthcheck files. The backend dicts below match the CloudWatch example
# fetch_metric; adapt them if you swap backends.
METRICS = [
    Metric(
        key="web-api.latency.p99",
        diurnal=False,
        backend={"namespace": "MyApp", "metric": "request-latency", "dims": {}, "stat": "p99"},
    ),
    Metric(
        key="web-api.error_rate",
        diurnal=False,
        backend={"namespace": "MyApp", "metric": "5xx-count", "dims": {}, "stat": "Sum"},
    ),
    Metric(
        key="web-api.cache_hit_rate",
        diurnal=True,
        backend={
            "namespace": "AWS/ElastiCache",
            "metric": "CacheHitRate",
            "dims": {"CacheClusterId": "web-api-cache-001"},
            "stat": "Average",
        },
    ),
    Metric(
        key="worker.queue_lag",
        diurnal=False,
        backend={
            "namespace": "AWS/Lambda",
            "metric": "IteratorAge",
            "dims": {"FunctionName": "worker-fn"},
            "stat": "Maximum",
        },
    ),
    Metric(
        key="auth-api.instance_count",
        diurnal=False,
        backend={
            "namespace": "ECS/ContainerInsights",
            "metric": "RunningTaskCount",
            "dims": {"ClusterName": "auth", "ServiceName": "auth-api"},
            "stat": "Average",
        },
    ),
]


# ---------------------------------------------------------------------------
# Pluggable metrics fetch  <-- THE ONE FUNCTION YOU ADAPT TO YOUR BACKEND
# ---------------------------------------------------------------------------

def fetch_metric(metric: Metric) -> list[tuple[str, float]]:
    """Return [(utc_iso_timestamp, value), ...] for `metric` over the window.

    Swap the body for your backend. The rest of this script only needs a list of
    (timestamp, value) pairs back. Below is a CloudWatch implementation via the
    `aws` CLI; Prometheus / Datadog / SQL sketches follow as comments.

    Credentials come from the environment (AWS_PROFILE / AWS_REGION here) so no
    secret is ever hardcoded in this file.
    """
    b = metric.backend
    stat = b["stat"]
    cmd = [
        "aws",
        "cloudwatch",
        "get-metric-statistics",
        "--namespace", b["namespace"],
        "--metric-name", b["metric"],
        "--start-time", START.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "--end-time", END.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "--period", str(SAMPLE_PERIOD_SECONDS),
    ]
    profile = os.environ.get("AWS_PROFILE")
    region = os.environ.get("AWS_REGION")
    if profile:
        cmd += ["--profile", profile]
    if region:
        cmd += ["--region", region]
    for name, value in b.get("dims", {}).items():
        cmd += ["--dimensions", f"Name={name},Value={value}"]
    if stat in {"p95", "p99"}:
        cmd += ["--extended-statistics", stat]
    else:
        cmd += ["--statistics", stat]

    out = subprocess.check_output(cmd, stderr=subprocess.PIPE, timeout=FETCH_TIMEOUT_SECONDS)
    data = json.loads(out)
    points = []
    for dp in data.get("Datapoints", []):
        value = dp["ExtendedStatistics"][stat] if stat in {"p95", "p99"} else dp[stat]
        points.append((dp["Timestamp"], float(value)))
    return points

    # --- Prometheus sketch -------------------------------------------------
    # import urllib.parse, urllib.request
    # url = os.environ["PROM_URL"] + "/api/v1/query_range?" + urllib.parse.urlencode({
    #     "query": metric.backend["query"],
    #     "start": START.timestamp(), "end": END.timestamp(), "step": SAMPLE_PERIOD_SECONDS,
    # })
    # with urllib.request.urlopen(url, timeout=FETCH_TIMEOUT_SECONDS) as r:
    #     series = json.load(r)["data"]["result"]
    # return [(datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), float(v))
    #         for t, v in series[0]["values"]] if series else []

    # --- Datadog sketch ----------------------------------------------------
    # Use the /api/v1/query timeseries endpoint with DD-API-KEY / DD-APPLICATION-KEY
    # from the environment; map each (epoch_ms, value) point the same way.

    # --- SQL sketch --------------------------------------------------------
    # Run a parameterized SELECT bucketed to SAMPLE_PERIOD_SECONDS against your
    # metrics warehouse and return (iso_timestamp, value) rows. Never interpolate
    # untrusted input into the SQL string; use bound parameters.


# ---------------------------------------------------------------------------
# Percentile + diurnal-bucket framework (backend-agnostic; no need to edit)
# ---------------------------------------------------------------------------

def _percentile(sorted_values: list[float], fraction: float) -> float:
    """Nearest-rank percentile on an already-sorted list."""
    if not sorted_values:
        raise ValueError("no values")
    idx = min(len(sorted_values) - 1, int(fraction * len(sorted_values)))
    return round(sorted_values[idx], 4)


def _summarize(values: list[float]) -> dict:
    s = sorted(values)
    return {
        "n": len(s),
        "min": round(s[0], 4),
        "p25": _percentile(s, 0.25),
        "p50": round(statistics.median(s), 4),
        "p75": _percentile(s, 0.75),
        "p95": _percentile(s, 0.95),
        "max": round(s[-1], 4),
        "mean": round(statistics.mean(s), 4),
    }


def _hour_of(ts) -> str:
    """UTC hour-of-day as a two-char string, from an ISO string or datetime."""
    if isinstance(ts, str):
        # tolerate 'Z' suffix and offset forms
        return ts[11:13]
    return ts.strftime("%H")


def compute_baseline(metric: Metric) -> tuple[str, dict]:
    """Fetch one metric and reduce it to a baseline summary. Never raises:
    failures are captured and returned so one bad metric cannot abort the run."""
    try:
        points = fetch_metric(metric)
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.decode()[:300] if exc.stderr else str(exc)[:300]
        return metric.key, {"error": detail}
    except Exception as exc:  # noqa: BLE001 - surface any failure mode, keep going
        return metric.key, {"error": str(exc)[:300]}

    if not points:
        return metric.key, {"n": 0, "note": "no datapoints in window"}

    summary = _summarize([v for _, v in points])

    if metric.diurnal:
        buckets: dict[str, list[float]] = defaultdict(list)
        for ts, value in points:
            buckets[_hour_of(ts)].append(value)
        summary["hourly"] = {
            hour: {
                "n": len(vals),
                "p25": _percentile(sorted(vals), 0.25),
                "p50": round(statistics.median(vals), 4),
                "p75": _percentile(sorted(vals), 0.75),
            }
            for hour, vals in sorted(buckets.items())
        }
    return metric.key, summary


def main() -> int:
    print(
        f"Window: {START.isoformat()} to {END.isoformat()} ({WINDOW_DAYS} days), "
        f"{len(METRICS)} metrics",
        file=sys.stderr,
    )
    results: dict[str, dict] = {}
    failures = 0
    with ThreadPoolExecutor(max_workers=MAX_PARALLEL_FETCHES) as pool:
        for key, summary in pool.map(compute_baseline, METRICS):
            results[key] = summary
            if "error" in summary:
                failures += 1
                print(f"  {key}: ERROR {summary['error']}", file=sys.stderr)
            elif not summary.get("n"):
                print(f"  {key}: no data", file=sys.stderr)
            else:
                hourly = f" [+{len(summary['hourly'])} hourly buckets]" if "hourly" in summary else ""
                print(
                    f"  {key}: n={summary['n']} p25={summary['p25']} "
                    f"p50={summary['p50']} p75={summary['p75']}{hourly}",
                    file=sys.stderr,
                )

    print(
        json.dumps(
            {
                "refreshed_at": END.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "source_window_days": WINDOW_DAYS,
                "sample_period_seconds": SAMPLE_PERIOD_SECONDS,
                "results": results,
            },
            indent=2,
        )
    )
    # Non-zero exit if every metric failed, so a cron job can alert on a total
    # outage while tolerating the odd missing series.
    return 1 if failures == len(METRICS) and METRICS else 0


if __name__ == "__main__":
    sys.exit(main())
