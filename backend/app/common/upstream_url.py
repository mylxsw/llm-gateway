"""
Helpers for composing upstream URLs consistently across forwarding and logging.
"""


def build_upstream_url(base_url: str, path: str) -> str:
    """
    Build an upstream URL using the repository's current path normalization rule.

    OpenAI/Anthropic style paths are stored as `/v1/...`, while many provider base
    URLs already include `/v1`. To avoid duplicated `/v1` in logs and request
    forwarding, strip the leading `/v1` segment from the path before appending.
    """
    cleaned_base = base_url.rstrip("/")
    cleaned_path = path
    if cleaned_path.startswith("/v1/"):
        cleaned_path = cleaned_path[3:]
    elif cleaned_path == "/v1":
        cleaned_path = ""
    return f"{cleaned_base}{cleaned_path}"
