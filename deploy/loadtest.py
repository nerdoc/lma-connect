#!/usr/bin/env python3
"""Load test against a running LMA Connect instance — no third-party deps.

Simulates N concurrent attendees moving through the app the way they would at
a conference: home, program, speakers, sponsors, abstracts. Each virtual user
has its own session (cookie jar), pauses to "think" between clicks and loops
for the given duration.

stdlib only (urllib + threads) on purpose: the script has to run even when
nobody feels like installing locust, and it should point at production or at a
local runserver straight from a laptop without a second environment.

It reports throughput, error rate and latency percentiles. The interesting
number is p95: if that stays below ~1 s and errors are at 0, the installation
carries the load.

Usage:
    deploy/loadtest.py --url https://conference.example.org --users 100 --duration 60
    deploy/loadtest.py --url http://127.0.0.1:8000 --users 50 --duration 30

IMPORTANT: only run this against your own installations, and against
production sensibly BEFORE the conference, not during.
"""

from __future__ import annotations

import argparse
import http.cookiejar
import random
import statistics
import threading
import time
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import dataclass, field

# A realistic reading path through the app. The weights roughly match what
# attendees actually look at — the program dominates by a wide margin.
PATHS = [
    ("/home/", 5),
    ("/program/", 8),
    ("/speakers/", 3),
    ("/sponsors/", 2),
    ("/abstracts/", 2),
    ("/info/", 1),
    ("/healthz", 1),
]

WEIGHTED_PATHS = [path for path, weight in PATHS for _ in range(weight)]


@dataclass
class Results:
    lock: threading.Lock = field(default_factory=threading.Lock)
    latencies: list[float] = field(default_factory=list)
    statuses: Counter = field(default_factory=Counter)
    errors: Counter = field(default_factory=Counter)

    def record(self, latency: float, status: int | None, error: str | None) -> None:
        with self.lock:
            self.latencies.append(latency)
            if error:
                self.errors[error] += 1
            else:
                self.statuses[status] += 1


def user_loop(base_url: str, deadline: float, results: Results,
              stop: threading.Event, extra_headers: list[tuple[str, str]]) -> None:
    """One virtual attendee: own session, own click path."""
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    opener.addheaders = [
        ("User-Agent", "lma-connect-loadtest/1.0"),
        ("Accept", "text/html,application/xhtml+xml"),
        ("Accept-Encoding", "gzip, deflate"),
        *extra_headers,
    ]

    while time.monotonic() < deadline and not stop.is_set():
        path = random.choice(WEIGHTED_PATHS)
        started = time.monotonic()
        status: int | None = None
        error: str | None = None
        try:
            with opener.open(base_url + path, timeout=30) as response:
                response.read()
                status = response.status
        except urllib.error.HTTPError as exc:
            status = exc.code
            # 4xx/5xx count as a status, not a transport error — for the
            # evaluation a 500 is something different from a timeout.
            if exc.code >= 500:
                error = f"HTTP {exc.code} {path}"
        except Exception as exc:  # noqa: BLE001 — everything else is a transport error
            error = f"{type(exc).__name__}: {exc}"

        results.record(time.monotonic() - started, status, error)

        # Think time between two clicks. Without it this would be a hammer
        # test, not a picture of 100 people using an app.
        stop.wait(random.uniform(0.5, 3.0))


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(int(len(ordered) * pct / 100), len(ordered) - 1)
    return ordered[index]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True,
                        help="Base URL, e.g. https://conference.example.org")
    parser.add_argument("--users", type=int, default=100, help="Concurrent users (default 100)")
    parser.add_argument("--duration", type=int, default=60, help="Test duration in seconds (default 60)")
    parser.add_argument("--ramp", type=float, default=10.0,
                        help="Seconds over which the users are ramped up (default 10)")
    parser.add_argument("--header", action="append", default=[], metavar="NAME:VALUE",
                        help="Extra header, repeatable. Needed when testing straight "
                             "against the backend port: --header 'Host: conference.example.org' "
                             "--header 'X-Forwarded-Proto: https' (otherwise 400 resp. 301).")
    args = parser.parse_args()

    extra_headers = []
    for raw in args.header:
        name, _, value = raw.partition(":")
        if not value:
            parser.error(f"header must look like 'Name: Value' — got: {raw!r}")
        extra_headers.append((name.strip(), value.strip()))

    base_url = args.url.rstrip("/")
    results = Results()
    stop = threading.Event()
    deadline = time.monotonic() + args.duration + args.ramp

    print(f"Load test against {base_url}")
    print(f"  {args.users} users, {args.duration}s duration, {args.ramp}s ramp-up\n")

    threads = []
    started_at = time.monotonic()
    for _ in range(args.users):
        thread = threading.Thread(
            target=user_loop, args=(base_url, deadline, results, stop, extra_headers),
            daemon=True,
        )
        thread.start()
        threads.append(thread)
        # Stagger the start so that not all 100 knock within the same
        # millisecond — otherwise this measures the ramp-up, not operation.
        if args.ramp > 0:
            time.sleep(args.ramp / args.users)

    try:
        for thread in threads:
            thread.join(timeout=max(0.0, deadline - time.monotonic()) + 35)
    except KeyboardInterrupt:
        print("\nAborting — waiting for in-flight requests ...")
        stop.set()
        for thread in threads:
            thread.join(timeout=5)

    elapsed = time.monotonic() - started_at
    latencies = results.latencies
    total = len(latencies)
    if not total:
        print("No requests were issued.")
        return 1

    failures = sum(results.errors.values())
    print("── Result ───────────────────────────────────────────")
    print(f"Requests total : {total}")
    print(f"Duration       : {elapsed:.1f}s")
    print(f"Throughput     : {total / elapsed:.1f} req/s")
    print(f"Errors         : {failures} ({failures / total * 100:.2f} %)")
    print()
    print("Status codes:")
    for status, count in sorted(results.statuses.items(), key=lambda kv: (kv[0] is None, kv[0])):
        print(f"  {status}: {count}")
    if results.errors:
        print("\nErrors:")
        for error, count in results.errors.most_common(10):
            print(f"  {count:>5}x  {error}")
    print()
    print("Latency (seconds):")
    print(f"  min    : {min(latencies):.3f}")
    print(f"  median : {statistics.median(latencies):.3f}")
    print(f"  p95    : {percentile(latencies, 95):.3f}")
    print(f"  p99    : {percentile(latencies, 99):.3f}")
    print(f"  max    : {max(latencies):.3f}")
    print()

    p95 = percentile(latencies, 95)

    # Expected throughput if ONLY the think time were the brake (avg 1.75 s
    # per click). If the measured value is far below that while even the
    # fastest response was noticeably slow, the bottleneck is most likely the
    # machine running the test, not the server: 100 Python threads negotiating
    # TLS and unpacking large pages in parallel is more work for a laptop than
    # for the app being queried.
    expected = args.users / 1.75
    achieved = total / elapsed
    client_bound = achieved < expected * 0.6 and min(latencies) > 0.2

    if failures == 0 and p95 < 1.0:
        print("PASSED — no errors, p95 below 1 s.")
        return 0

    print("NOT PASSED — errors occurred or p95 above 1 s.")
    if client_bound:
        print()
        print("CAUTION: this result is probably NOT meaningful.")
        print(f"  ~{expected:.0f} req/s would be expected, {achieved:.1f} req/s were measured,")
        print(f"  and even the fastest response took {min(latencies):.3f}s.")
        print("  Both point at this machine (or its uplink) being the")
        print("  bottleneck rather than the server.")
        print("  Cross-check: repeat the run directly on the server — see")
        print("  docs/backup-und-lastfestigkeit.md, section 'Wenn ein Lauf")
        print("  NICHT BESTANDEN meldet'.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
