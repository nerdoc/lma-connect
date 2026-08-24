"""Small helpers shared across plugins. No models of their own."""


def client_ip(request) -> str:
    """Determine the client IP behind a reverse proxy.

    X-Forwarded-For has the form ``client, proxy1, proxy2`` — each proxy
    appends at the end. The **rightmost** entry is therefore the one our
    trusted proxy set; the leftmost is client-controlled and can be forged.
    So we take the last entry, not the first: otherwise any IP-based rate
    limit is trivially bypassed with a fabricated X-Forwarded-For header.

    NOTE: this assumes exactly one trusted proxy in front of the app. With a
    different topology (a CDN plus a proxy, say), take the appropriate entry
    from the right instead.
    """
    fwd = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if fwd:
        return fwd.split(",")[-1].strip()
    return request.META.get("REMOTE_ADDR", "0.0.0.0")
