import pytest

from app.common.errors import ServiceError
from app.common.reasoning import force_disable_reasoning_for_supplier


@pytest.mark.parametrize("protocol", ["openai", "openai_responses"])
def test_force_disable_openai_overrides_conflicting_controls(protocol):
    result = force_disable_reasoning_for_supplier(
        {
            "reasoning": {"effort": "high"},
            "thinking": {"type": "enabled"},
            "enable_thinking": True,
            "output_config": {"effort": "max"},
        },
        supplier_protocol=protocol,
        target_model="gpt-test",
    )

    assert result["reasoning"] == {"effort": "none"}
    assert "thinking" not in result
    assert "enable_thinking" not in result
    assert "output_config" not in result


@pytest.mark.parametrize("protocol", ["deepseek", "zhipu", "moonshot", "ark"])
def test_force_disable_deepseek_compatible_protocols(protocol):
    result = force_disable_reasoning_for_supplier(
        {"reasoning": {"effort": "high"}, "thinking": {"type": "enabled"}},
        supplier_protocol=protocol,
        target_model="reasoning-model",
    )

    assert result["thinking"] == {"type": "disabled"}
    assert "reasoning" not in result


def test_force_disable_anthropic_removes_effort():
    result = force_disable_reasoning_for_supplier(
        {
            "thinking": {"type": "enabled", "budget_tokens": 4096},
            "output_config": {"effort": "high"},
        },
        supplier_protocol="anthropic",
        target_model="claude-test",
    )

    assert result["thinking"] == {"type": "disabled"}
    assert "output_config" not in result


def test_force_disable_preserves_unrelated_output_config_fields():
    result = force_disable_reasoning_for_supplier(
        {"output_config": {"effort": "high", "format": "json"}},
        supplier_protocol="openai",
        target_model="gpt-test",
    )

    assert result["output_config"] == {"format": "json"}


def test_force_disable_dashscope():
    result = force_disable_reasoning_for_supplier(
        {"enable_thinking": True, "reasoning": {"effort": "high"}},
        supplier_protocol="aliyun",
        target_model="qwen-test",
    )

    assert result["enable_thinking"] is False
    assert "reasoning" not in result


def test_force_disable_gemini_25_flash_preserves_generation_config():
    result = force_disable_reasoning_for_supplier(
        {
            "generationConfig": {
                "temperature": 0.5,
                "thinkingConfig": {"thinkingBudget": 1024},
            }
        },
        supplier_protocol="gemini",
        target_model="gemini-2.5-flash-preview",
    )

    assert result["generationConfig"]["temperature"] == 0.5
    assert result["generationConfig"]["thinkingConfig"] == {
        "includeThoughts": False,
        "thinkingBudget": 0,
    }


def test_force_disable_gemini_3_flash_uses_minimal_level():
    result = force_disable_reasoning_for_supplier(
        {"generationConfig": {"thinkingConfig": {"thinkingLevel": "high"}}},
        supplier_protocol="gemini",
        target_model="models/gemini-3-flash-preview",
    )

    assert result["generationConfig"]["thinkingConfig"] == {
        "includeThoughts": False,
        "thinkingLevel": "minimal",
    }


@pytest.mark.parametrize(
    "model",
    [
        "gemini-2.5-pro",
        "gemini-3-pro-preview",
        "gemini-3.7-flash",
        "gemini-future",
    ],
)
def test_force_disable_rejects_gemini_models_without_supported_off_control(model):
    with pytest.raises(ServiceError) as exc_info:
        force_disable_reasoning_for_supplier(
            {}, supplier_protocol="gemini", target_model=model
        )

    assert exc_info.value.code == "thinking_disable_unsupported"


def test_force_disable_does_not_mutate_input():
    source = {"reasoning": {"effort": "high"}}

    force_disable_reasoning_for_supplier(
        source, supplier_protocol="openai", target_model="gpt-test"
    )

    assert source == {"reasoning": {"effort": "high"}}
