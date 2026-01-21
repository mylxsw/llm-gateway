"""
Proxy Configuration Helpers

Builds httpx proxy configuration for provider-specific forwarding.
"""

from typing import Optional
from urllib.parse import urlparse


def build_proxy_config(enabled: bool, proxy_url: Optional[str]) -> Optional[dict[str, str]]:
    if not enabled:
        return None
    if not proxy_url:
        return None

    parsed = urlparse(proxy_url)
    if parsed.scheme not in {"socks5", "http"}:
        return None
    if not parsed.hostname or not parsed.port:
        return None

    return {"all://": proxy_url}
