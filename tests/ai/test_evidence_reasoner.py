"""Unit tests for EvidenceReasoner and AIReasoningService."""

import pytest
from backend.ai.evidence_reasoner import EvidenceReasoner
from backend.ai.llm_client import MockLLMClient
from backend.ai.models import UncertaintyLevel
from backend.ai.service import (
    AIReasoningService,
    reason_about_claim_evidence,
    reason_about_claim_evidence_sync,
)
from backend.claim.models import Claim, ClaimImportance, ClaimType
from backend.config.settings import settings
from backend.retrieval.models import Evidence, SourceType


def _make_claim():
    return Claim(
        claim_id="c_ai_01",
        original_text="Mars rover discovered liquid water yesterday.",
        normalized_text="Mars rover discovered liquid water yesterday.",
        claim_text="Mars rover discovered liquid water yesterday.",
        source_sentence="Mars rover discovered liquid water yesterday.",
        claim_type=ClaimType.EVENT,
        importance=ClaimImportance.HIGH,
        confidence=0.92,
    )


def _make_evidence():
    return Evidence(
        evidence_id="ev_mars_1",
        claim_id="c_ai_01",
        title="NASA Rover Update",
        url="https://nasa.gov/rover-update",
        publisher="NASA",
        domain="nasa.gov",
        snippet="Perseverance rover examined sedimentary rock samples.",
        source_type=SourceType.OFFICIAL,
        provider="tavily",
        query_used="mars rover liquid water",
    )


@pytest.mark.anyio
async def test_reasoner_fallback_when_llm_disabled(monkeypatch):
    monkeypatch.setattr(settings, "LLM_ENABLED", False)

    claim = _make_claim()
    ev = _make_evidence()
    reasoner = EvidenceReasoner()

    result = await reasoner.reason(claim=claim, evidence_items=[ev])

    assert result.claim_id == claim.claim_id
    assert result.fallback_used is True
    assert result.ai_used is False
    assert result.provider == "deterministic_rule_engine"


@pytest.mark.anyio
async def test_reasoner_with_mock_client():
    claim = _make_claim()
    ev = _make_evidence()

    mock_response = {
        "summary": "NASA reports indicate findings are sedimentary, not liquid water.",
        "key_findings": [
            {
                "text": "NASA statement refers to rock samples.",
                "evidence_ids": ["ev_mars_1"],
                "stance": "CONTRADICTING",
                "importance": "HIGH",
                "confidence": 0.95,
            }
        ],
        "supporting_findings": [],
        "contradicting_findings": [
            {
                "text": "NASA statement refers to rock samples.",
                "evidence_ids": ["ev_mars_1"],
                "stance": "CONTRADICTING",
                "importance": "HIGH",
                "confidence": 0.95,
            }
        ],
        "important_discrepancies": [],
        "source_observations": ["NASA is primary government source."],
        "independence_observations": [],
        "fact_check_observations": [],
        "verification_gaps": [],
        "uncertainty": "LOW",
        "reasoning_steps": ["Parsed NASA update snippet."],
        "limitations": [],
    }

    mock_client = MockLLMClient(response_data=mock_response)
    reasoner = EvidenceReasoner(llm_client=mock_client)

    result = await reasoner.reason(claim=claim, evidence_items=[ev])

    assert result.claim_id == claim.claim_id
    assert result.ai_used is True
    assert result.fallback_used is False
    assert result.uncertainty == UncertaintyLevel.LOW
    assert len(result.key_findings) == 1
    assert result.key_findings[0].evidence_ids == ["ev_mars_1"]


def test_service_facade_sync():
    claim = _make_claim()
    ev = _make_evidence()

    result = reason_about_claim_evidence_sync(claim=claim, evidence_items=[ev])
    assert result.claim_id == claim.claim_id
    assert result.summary != ""


@pytest.mark.anyio
async def test_service_facade_async():
    claim = _make_claim()
    ev = _make_evidence()

    result = await reason_about_claim_evidence(claim=claim, evidence_items=[ev])
    assert result.claim_id == claim.claim_id
    assert result.summary != ""
