"""Unit tests for LLM client abstractions and mock client."""

import pytest
from backend.ai.llm_client import MockLLMClient, get_llm_client
from backend.ai.models import AIReasoningResult, UncertaintyLevel


@pytest.mark.anyio
async def test_mock_llm_client_default_response():
    client = MockLLMClient()
    response = await client.generate_structured(
        system_instruction="Test system prompt",
        user_prompt="Analyze claim: Water boils at 100C.",
        response_model=AIReasoningResult,
    )

    assert isinstance(response, AIReasoningResult)
    assert response.summary != ""
    assert response.uncertainty in [UncertaintyLevel.LOW, UncertaintyLevel.MEDIUM, UncertaintyLevel.HIGH]


@pytest.mark.anyio
async def test_mock_llm_client_custom_response():
    custom_data = {
        "summary": "Custom mock summary.",
        "key_findings": [
            {
                "text": "Finding text",
                "evidence_ids": ["ev_1"],
                "stance": "SUPPORTING",
                "importance": "HIGH",
                "confidence": 0.9,
            }
        ],
        "supporting_findings": [],
        "contradicting_findings": [],
        "important_discrepancies": [],
        "source_observations": [],
        "independence_observations": [],
        "fact_check_observations": [],
        "verification_gaps": [],
        "uncertainty": "LOW",
        "reasoning_steps": [],
        "limitations": [],
    }
    client = MockLLMClient(response_data=custom_data)
    response = await client.generate_structured(
        system_instruction="sys",
        user_prompt="user",
        response_model=AIReasoningResult,
    )

    assert isinstance(response, AIReasoningResult)
    assert response.summary == "Custom mock summary."
    assert len(response.key_findings) == 1
    assert response.key_findings[0].evidence_ids == ["ev_1"]


def test_get_llm_client_factory():
    client = get_llm_client("mock")
    assert isinstance(client, MockLLMClient)
