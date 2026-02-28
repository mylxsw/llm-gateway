"""
URL Security Validator

Provides SSRF (Server-Side Request Forgery) protection for external URLs.
"""

import ipaddress
import logging
import socket
from urllib.parse import urlparse

from app.common.errors import ValidationError
from app.config import get_settings

logger = logging.getLogger(__name__)

# Allowed domains for provider base URLs
# These are official API endpoints for supported LLM providers
ALLOWED_DOMAINS = {
    # OpenAI
    "api.openai.com",
    # Anthropic
    "api.anthropic.com",
    # Google Gemini
    "generativelanguage.googleapis.com",
    # Zhipu (ChatGLM)
    "open.bigmodel.cn",
    # Aliyun (Qwen)
    "dashscope.aliyuncs.com",
    # Moonshot (Kimi)
    "api.moonshot.cn",
    # DeepSeek
    "api.deepseek.com",
    # Baidu (ERNIE)
    "aip.baidubce.com",
    # Tencent (Hunyuan)
    "hunyuan.tencentcloudapi.com",
    # Minimax
    "api.minimax.chat",
    # ByteDance (Doubao)
    "ark.cn-beijing.volces.com",
    # SiliconFlow
    "api.siliconflow.cn",
    # Groq
    "api.groq.com",
    # Together AI
    "api.together.xyz",
    # Azure OpenAI (common pattern)
    "openai.azure.com",
    # Perplexity
    "api.perplexity.ai",
    # Cohere
    "api.cohere.ai",
    # Replicate
    "api.replicate.com",
    # Mistral
    "api.mistral.ai",
}

# Private IP ranges that should be blocked
PRIVATE_IP_RANGES = [
    ipaddress.ip_network("127.0.0.0/8"),      # Loopback
    ipaddress.ip_network("10.0.0.0/8"),       # Class A private
    ipaddress.ip_network("172.16.0.0/12"),    # Class B private
    ipaddress.ip_network("192.168.0.0/16"),   # Class C private
    ipaddress.ip_network("169.254.0.0/16"),   # Link-local
    ipaddress.ip_network("::1/128"),          # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),         # IPv6 private
    ipaddress.ip_network("fe80::/10"),        # IPv6 link-local
]


def is_private_ip(ip_str: str) -> bool:
    """
    Check if an IP address is private/internal

    Args:
        ip_str: IP address string

    Returns:
        bool: True if the IP is private
    """
    try:
        ip = ipaddress.ip_address(ip_str)
        for network in PRIVATE_IP_RANGES:
            if ip in network:
                return True
        return False
    except ValueError:
        return False


def resolve_ip(hostname: str) -> str | None:
    """
    Resolve hostname to IP address

    Args:
        hostname: Hostname to resolve

    Returns:
        str | None: IP address or None if resolution fails
    """
    try:
        return socket.gethostbyname(hostname)
    except socket.gaierror:
        return None


def validate_provider_url(url: str, strict: bool = False) -> str:
    """
    Validate provider base URL for SSRF protection

    Args:
        url: The URL to validate
        strict: If True, only allow whitelisted domains

    Returns:
        str: The validated URL

    Raises:
        ValidationError: If the URL is invalid or potentially dangerous
    """
    if not url:
        raise ValidationError(
            message="URL cannot be empty",
            code="invalid_url",
        )

    # Parse URL
    try:
        parsed = urlparse(url)
    except Exception as e:
        raise ValidationError(
            message="Invalid URL format",
            code="invalid_url",
            details={"error": str(e)},
        )

    # Check scheme
    if parsed.scheme not in ("http", "https"):
        raise ValidationError(
            message="URL must use http or https scheme",
            code="invalid_url_scheme",
            details={"scheme": parsed.scheme},
        )

    # Extract hostname
    hostname = parsed.hostname
    if not hostname:
        raise ValidationError(
            message="URL must contain a valid hostname",
            code="invalid_url_hostname",
        )

    # In strict mode, check domain whitelist
    if strict:
        # Check if hostname is in allowed domains or is a subdomain
        is_allowed = False
        for allowed_domain in ALLOWED_DOMAINS:
            if hostname == allowed_domain or hostname.endswith(f".{allowed_domain}"):
                is_allowed = True
                break

        if not is_allowed:
            logger.warning(
                "URL validation failed: hostname '%s' not in whitelist",
                hostname,
            )
            raise ValidationError(
                message="URL domain is not allowed",
                code="url_domain_not_allowed",
            )

    # Check for private IP in hostname (direct IP URL)
    if is_private_ip(hostname):
        logger.warning(
            "URL validation failed: private IP '%s' detected",
            hostname,
        )
        raise ValidationError(
            message="Private IP addresses are not allowed",
            code="private_ip_not_allowed",
        )

    # Resolve hostname and check if it resolves to private IP
    resolved_ip = resolve_ip(hostname)
    if resolved_ip and is_private_ip(resolved_ip):
        logger.warning(
            "URL validation failed: hostname '%s' resolves to private IP '%s'",
            hostname,
            resolved_ip,
        )
        raise ValidationError(
            message="URL resolves to a private IP address",
            code="private_ip_resolution",
        )

    return url


def validate_provider_url_loose(url: str) -> str:
    """
    Validate provider URL with loose restrictions

    Only blocks internal/private IP addresses but allows any public domain.
    Use this for more flexibility while still preventing SSRF.

    Args:
        url: The URL to validate

    Returns:
        str: The validated URL
    """
    return validate_provider_url(url, strict=False)


def validate_provider_url_strict(url: str) -> str:
    """
    Validate provider URL with strict whitelist

    Only allows predefined domains and blocks all internal IPs.
    Use this for maximum security.

    Args:
        url: The URL to validate

    Returns:
        str: The validated URL
    """
    return validate_provider_url(url, strict=True)
