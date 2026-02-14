from app.common.provider_protocols import (
    GEMINI_PROTOCOL,
    get_frontend_protocol_config,
    normalize_frontend_protocol,
    resolve_implementation_protocol,
)


def test_gemini_frontend_protocol_config_exists():
    config = get_frontend_protocol_config("gemini")
    assert config.frontend == "gemini"
    assert config.implementation == GEMINI_PROTOCOL
    assert config.base_url == "https://generativelanguage.googleapis.com"


def test_resolve_implementation_protocol_gemini():
    assert resolve_implementation_protocol("gemini") == GEMINI_PROTOCOL


def test_normalize_frontend_protocol_gemini():
    assert normalize_frontend_protocol("GeMiNi") == "gemini"
