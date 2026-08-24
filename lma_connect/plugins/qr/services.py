"""QR generation without a view or auth layer, so that both the qr plugin and
the ops frontend (access.ops_views) share the same PNG/SVG logic."""

import io

import qrcode
import qrcode.image.svg
from django.http import HttpResponse


def abs_url(request, path: str) -> str:
    """Turn a relative path into an absolute URL. External URLs are passed
    through unchanged."""
    if path.startswith(("http://", "https://")):
        return path
    if not path.startswith("/"):
        path = "/" + path
    return request.build_absolute_uri(path)


def qr_svg_response(url: str) -> HttpResponse:
    factory = qrcode.image.svg.SvgPathImage
    img = qrcode.make(url, image_factory=factory, box_size=10, border=2)
    buf = io.BytesIO()
    img.save(buf)
    return HttpResponse(buf.getvalue(), content_type="image/svg+xml")


def qr_png_response(url: str, box_size: int = 10) -> HttpResponse:
    img = qrcode.make(url, box_size=box_size, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return HttpResponse(buf.getvalue(), content_type="image/png")
