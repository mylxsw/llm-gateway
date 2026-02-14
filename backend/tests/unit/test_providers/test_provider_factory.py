import pytest

from app.providers.anthropic_client import AnthropicClient
from app.providers.factory import _clients, get_provider_client
from app.providers.gemini_client import GeminiClient
from app.providers.openai_client import OpenAIClient


def setup_function():
    _clients.clear()


def test_factory_openai_and_responses_share_openai_client_type():
    openai_client = get_provider_client("openai")
    responses_client = get_provider_client("openai_responses")
    assert isinstance(openai_client, OpenAIClient)
    assert isinstance(responses_client, OpenAIClient)


def test_factory_anthropic_client():
    client = get_provider_client("anthropic")
    assert isinstance(client, AnthropicClient)


def test_factory_gemini_client():
    client = get_provider_client("gemini")
    assert isinstance(client, GeminiClient)


def test_factory_unsupported_protocol():
    with pytest.raises(ValueError):
        get_provider_client("unknown")
