"""Server-Sent Events for live updates — served by a separate ASGI process.

The streams here are long-lived and only work under ASGI (uvicorn). Under WSGI
(runserver, the main gunicorn) Django collects async iterators into a list, so
an endless stream would block a thread forever — the guard below turns that
into an immediate 503 instead, and EventSource retries with backoff.
"""

import asyncio
from collections.abc import AsyncIterator

from django.http import HttpRequest, HttpResponse, StreamingHttpResponse

HEARTBEAT_SECONDS = 20
WATCH_INTERVAL_SECONDS = 1.0


def _sse_response(agen: AsyncIterator[str]) -> StreamingHttpResponse:
    response = StreamingHttpResponse(agen, content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    # nginx-style proxies honour this and stop buffering; harmless elsewhere.
    response["X-Accel-Buffering"] = "no"
    return response


def _is_asgi(request: HttpRequest) -> bool:
    """ASGIRequest carries the raw `scope`; WSGIRequest does not."""
    return hasattr(request, "scope")


async def _ping(interval: int) -> AsyncIterator[str]:
    n = 0
    while True:
        n += 1
        yield f": ping {n}\n\n"
        await asyncio.sleep(interval)


async def ping_stream(request):
    """Unauthenticated heartbeat stream for the deployment gate.

    `?interval=` (seconds, clamped to 1..300) lets the gate script measure the
    proxy's idle timeout — that is the only reason it is a parameter.
    """
    if not _is_asgi(request):
        return HttpResponse(status=503)
    try:
        interval = int(request.GET.get("interval", HEARTBEAT_SECONDS))
    except ValueError:
        interval = HEARTBEAT_SECONDS
    interval = max(1, min(interval, 300))
    return _sse_response(_ping(interval))
