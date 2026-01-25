from app.common.usage_extractor import extract_output_tokens, extract_usage_details


def test_extract_usage_details_openai_prompt_completion():
    body = {"usage": {"prompt_tokens": 12, "completion_tokens": 7, "total_tokens": 19}}
    details = extract_usage_details(body)
    assert details is not None
    assert details.input_tokens == 12
    assert details.output_tokens == 7
    assert details.total_tokens == 19


def test_extract_usage_details_openai_details_fields():
    body = {
        "usage": {
            "input_tokens": 10,
            "output_tokens": 4,
            "input_tokens_details": {"cached_tokens": 2, "audio_tokens": 3},
            "output_tokens_details": {"image_tokens": 5, "reasoning_tokens": 1},
        }
    }
    details = extract_usage_details(body)
    assert details is not None
    assert details.input_tokens == 10
    assert details.output_tokens == 4
    assert details.cached_tokens == 2
    assert details.input_audio_tokens == 3
    assert details.output_image_tokens == 5
    assert details.reasoning_tokens == 1


def test_extract_usage_details_anthropic_cache_fields():
    body = {
        "usage": {
            "input_tokens": 20,
            "output_tokens": 5,
            "cache_creation_input_tokens": 3,
            "cache_read_input_tokens": 2,
        }
    }
    details = extract_usage_details(body)
    assert details is not None
    assert details.cache_creation_input_tokens == 3
    assert details.cache_read_input_tokens == 2


def test_extract_usage_details_gemini_metadata():
    body = {
        "usageMetadata": {
            "promptTokenCount": 8,
            "candidatesTokenCount": 6,
            "totalTokenCount": 14,
            "cachedContentTokenCount": 4,
        }
    }
    details = extract_usage_details(body)
    assert details is not None
    assert details.input_tokens == 8
    assert details.output_tokens == 6
    assert details.total_tokens == 14
    assert details.cached_tokens == 4


def test_extract_output_tokens_fallback_total_minus_input():
    body = {"usage": {"total_tokens": 20, "prompt_tokens": 12}}
    assert extract_output_tokens(body) == 8
