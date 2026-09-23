"""Unit tests for AI Evidence Reasoning models."""

import pytest
from backend.ai.models import (
    AIReasoningResult,
    EvidenceFinding,
    EvidencePacket,
    EvidencePacketItem,
    FindingImportance,
    UncertaintyLevel,
)


def test_finding_importance_values():
    assert FindingImportance.HIGH.value == "HIGH"
    assert FindingImportance.MEDIUM.value == "MEDIUM"
    assert FindingImportance.LOW.value == "LOW"


def test_uncertainty_level_values():
    assert UncertaintyLevel.LOW.value == "LOW"
    assert UncertaintyLevel.MEDIUM.value == "MEDIUM"
    assert UncertaintyLevel.HIGH.value == "HIGH"


def test_evidence_finding_creation():
    finding = EvidenceFinding(
        text="Official agency confirmed report.",
        evidence_ids=["ev_1", "ev_2"],
        stance="SUPPORTING",
        importance=FindingImportance.HIGH,
        confidence=0.95,
    )
    assert finding.text == "Official agency confirmed report."
    assert finding.evidence_ids == ["ev_1", "ev_2"]
    assert finding.stance == "SUPPORTING"
    assert finding.importance == FindingImportance.HIGH
    assert finding.confidence == 0.95


def test_evidence_packet_item():
    item = EvidencePacketItem(
        evidence_id="ev_test",
        title="Test News Article",
        publisher="Reuters",
        domain="reuters.com",
        url="https://reuters.com/news/1",
        source_reliability="high",
        stance="SUPPORTING",
        snippet="Verified by independent audit.",
    )
    assert item.evidence_id == "ev_test"
    assert item.stance == "SUPPORTING"
    assert item.source_reliability == "high"


def test_ai_reasoning_result_defaults():
    res = AIReasoningResult(
        claim_id="claim_001",
        claim_text="Inflation dropped to 2%.",
        summary="Consistent reporting indicates inflation decreased.",
        uncertainty=UncertaintyLevel.LOW,
    )
    assert res.claim_id == "claim_001"
    assert res.key_findings == []
    assert res.supporting_findings == []
    assert res.contradicting_findings == []
    assert res.ai_used is False
    assert res.fallback_used is False
    assert res.uncertainty == UncertaintyLevel.LOW
