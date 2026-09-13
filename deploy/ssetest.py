#!/usr/bin/env python3
"""Gate / load test for long-lived SSE connections — no third-party deps.

Opens N connections to the SSE ping endpoint and keeps them open for the given
duration. It answers the questions the deployment gate asks before the live
updates may go on air (see docs/live-updates-sse.md):

  * Does the proxy pass the stream through *live*, or does it buffer it?
    (time to first byte, spacing of the heartbeats)
  * How many connections stay open at the same time? (a cap shows up as
    aborts at a fixed count)
  * Does the proxy kill idle connections, and after how long?
    (histogram of the abort times — run with a large --interval for this)

stdlib only (urllib + threads) on purpose, same as loadtest.py: it must run
straight from the server or a laptop without a second environment.

Usage:
    deploy/ssetest.py --url https://conference.example.org --conns 300 --duration 600 --interval 20
    deploy/ssetest.py --url https://conference.example.org --conns 20 --duration 400 --interval 300
    deploy/ssetest.py --url http://127.0.0.1:8131 --conns 50 --duration 30 --interval 2

Exit code 0 only if every connection survived until the end, TTFB p95 < 2 s
and no heartbeat gap exceeded 2 × --interval. Otherwise 1 with a verdict.

IMPORTANT: only run this against your own installations, and against
production sensibly BEFORE the conference, not during.
"""

from __future__ import annotations

import argparse
import threading
import time
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import dataclass, field


@dataclass
class Connection:
    ttfb: float | None = None          # seconds until the first body line
    max_gap: float = 0.0               # largest spacing between two heartbeats
    heartbeats: int = 0
    ended_at: float | None = None      # seconds after test start, if aborted
    reason: str | None = None          # why it ended early (None = survived)


@dataclass
class Results:
    lock: threading.Lock = field(default_factory=threading.Lock)
    connections: list[Connection] = field(default_factory=list)
    open_now: int = 0
    max_open: int = 0

    def opened(self) -> None:
        with self.lock:
            self.open_now += 1
            self.max_open = max(self.max_open, self.open_now)

    def closed(self, conn: Connection) -> None:
        with self.lock:
            self.open_now -= 1
            self.connections.append(conn)


def stream_loop(url: str, started_at: float, deadline: float, read_timeout: float,
                results: Results, stop: threading.Event,
                extra_headers: list[tuple[str, str]]) -> None:
    """One SSE client: connect, read heartbeats until the deadline."""
    conn = Connection()
    opener = urllib.request.build_opener()
    opener.addheaders = [
        ("User-Agent", "lma-connect-ssetest/1.0"),
        ("Accept", "text/event-stream"),
        ("Cache-Control", "no-cache"),
        *extra_headers,
    ]
    opened = time.monotonic()
    try:
        response = opener.open(url, timeout=read_timeout)
    except urllib.error.HTTPError as exc:
        conn.ended_at, conn.reason = time.monotonic() - started_at, f"HTTP {exc.code}"
        results.closed(conn)
        return
    except Exception as exc:  # noqa: BLE001 — everything else is a transport error
        conn.ended_at, conn.reason = time.monotonic() - started_at, f"{type(exc).__name__}: {exc}"
        results.closed(conn)
        return

    results.opened()
    last_beat = opened
    try:
        with response:
            while not stop.is_set():
                try:
                    line = response.readline()
                except TimeoutError:
                    conn.ended_at = time.monotonic() - started_at
                    conn.reason = f"timeout (no data for {read_timeout:.0f}s)"
                    break
                except Exception as exc:  # noqa: BLE001
                    conn.ended_at = time.monotonic() - started_at
                    conn.reason = f"{type(exc).__name__}: {exc}"
                    break
                now = time.monotonic()
                if not line:
                    if now < deadline:
                        conn.ended_at, conn.reason = now - started_at, "EOF"
                    break
                if line.strip():
                    if conn.ttfb is None:
                        conn.ttfb = now - opened
                    else:
                        conn.max_gap = max(conn.max_gap, now - last_beat)
                    conn.heartbeats += 1
                    last_beat = now
                if now >= deadline:
                    break
    finally:
        results.closed(conn)


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(int(len(ordered) * pct / 100), len(ordered) - 1)
    return ordered[index]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", required=True,
                        help="Base URL, e.g. https://conference.example.org")
    parser.add_argument("--path", default="/events/ping/",
                        help="SSE endpoint path (default /events/ping/)")
    parser.add_argument("--conns", type=int, default=300,
                        help="Concurrent connections (default 300)")
    parser.add_argument("--duration", type=int, default=600,
                        help="Seconds to keep the connections open (default 600)")
    parser.add_argument("--ramp", type=float, default=30.0,
                        help="Seconds over which the connections are opened (default 30)")
    parser.add_argument("--interval", type=int, default=20,
                        help="Expected heartbeat interval in seconds; passed as ?interval= "
                             "(default 20). Use a large value to find the proxy's idle timeout.")
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

    url = f"{args.url.rstrip('/')}{args.path}?interval={args.interval}"
    # A missing heartbeat must surface as a timeout, not hang forever.
    read_timeout = args.interval * 2 + 5
    results = Results()
    stop = threading.Event()
    started_at = time.monotonic()
    deadline = started_at + args.ramp + args.duration

    print(f"SSE test against {url}")
    print(f"  {args.conns} connections, {args.duration}s duration, {args.ramp}s ramp-up, "
          f"heartbeat every {args.interval}s\n")

    threads = []
    for _ in range(args.conns):
        thread = threading.Thread(
            target=stream_loop,
            args=(url, started_at, deadline, read_timeout, results, stop, extra_headers),
            daemon=True,
        )
        thread.start()
        threads.append(thread)
        if args.ramp > 0:
            time.sleep(args.ramp / args.conns)

    try:
        for thread in threads:
            thread.join(timeout=max(0.0, deadline - time.monotonic()) + read_timeout + 5)
    except KeyboardInterrupt:
        print("\nAborting — closing connections ...")
        stop.set()
        for thread in threads:
            thread.join(timeout=5)

    conns = results.connections
    aborted = [c for c in conns if c.reason]
    survived = [c for c in conns if not c.reason]
    ttfbs = [c.ttfb for c in conns if c.ttfb is not None]
    max_gap = max((c.max_gap for c in conns), default=0.0)

    print("── Result ───────────────────────────────────────────")
    print(f"Connections     : {args.conns} requested, {len(survived)} survived, "
          f"{len(aborted)} aborted")
    print(f"Max open at once: {results.max_open}")
    print(f"Heartbeats total: {sum(c.heartbeats for c in conns)}")
    print()
    print("TTFB (seconds):")
    print(f"  p50 : {percentile(ttfbs, 50):.3f}")
    print(f"  p95 : {percentile(ttfbs, 95):.3f}")
    print(f"  max : {max(ttfbs, default=0.0):.3f}")
    print(f"Max heartbeat gap: {max_gap:.1f}s (expected ~{args.interval}s)")

    if aborted:
        reasons = Counter(c.reason for c in aborted)
        print("\nAbort reasons:")
        for reason, count in reasons.most_common(10):
            print(f"  {count:>5}x  {reason}")
        # Histogram of abort times: a proxy idle timeout shows up as one
        # sharp peak, a connection cap as aborts right at ramp-up.
        width = 10 if args.duration <= 600 else 30
        buckets = Counter(int(c.ended_at // width) for c in aborted if c.ended_at is not None)
        print("\nAbort time after test start:")
        for bucket in sorted(buckets):
            print(f"  {bucket * width:>5}–{(bucket + 1) * width:<5}s  {buckets[bucket]}")
    print()

    p95 = percentile(ttfbs, 95)
    verdicts = []
    if aborted:
        verdicts.append(f"{len(aborted)} connections did not survive")
    if len(survived) < args.conns:
        verdicts.append(f"only {len(survived)} of {args.conns} connections stayed open")
    if p95 >= 2.0:
        verdicts.append(f"TTFB p95 {p95:.1f}s ≥ 2 s — the proxy is probably buffering")
    if max_gap >= 2 * args.interval:
        verdicts.append(f"heartbeat gap {max_gap:.0f}s ≥ 2 × interval — stream is being bundled")

    if not verdicts:
        print("PASSED — all connections open until the end, live delivery, no gaps.")
        return 0
    print("NOT PASSED — " + "; ".join(verdicts) + ".")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
