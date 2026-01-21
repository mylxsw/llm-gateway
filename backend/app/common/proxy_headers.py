"""
Proxy response header utilities.

This gateway proxies upstream providers. Some upstream responses (especially streaming/SSE)
may include transport/framing headers that must not be forwarded as-is because the gateway
re-frames the response body (e.g. via Starlette StreamingResponse and httpx auto-decompression).
"""

from __future__ import annotations

from collections.abc import Mapping


# RFC 7230 hop-by-hop headers, plus response framing headers we must not forward.
_DROP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
    # Body framing / encoding headers that become invalid after proxying/transforming.
    "content-length",
    "content-encoding",
}


def sanitize_upstream_response_headers(headers: Mapping[str, str] | None) -> dict[str, str]:
    """
    Remove hop-by-hop and body framing headers from upstream response headers.

    This prevents invalid combinations like `Content-Length` + `Transfer-Encoding` on streamed
    responses and avoids forwarding `Content-Encoding` when the body may be decompressed by httpx.
    """
    if not headers:
        return {}

    sanitized: dict[str, str] = {}
    for key, value in headers.items():
        if key.lower() in _DROP_HEADERS:
            continue
        sanitized[key] = value
    return sanitized

