"""Unit tests for GroundingValidator."""

from backend.ai.grounding_validator import validate_and_sanitize_reasoning
from backend.ai.models import (
    AIReasoningResult,
    EvidenceFinding,
    EvidencePacket,
    EvidencePacketItem,
    FindingImportance,
    UncertaintyLevel,
)


def _make_packet():
    return EvidencePacket(
        claim_id="c_100",
        claim_text="Quantum computer factored RSA-2048.",
        evidence=[
            EvidencePacketItem(
                evidence_id="ev_valid_1",
                title="MIT Tech Review",
                publisher="MIT Tech Review",
                domain="technologyreview.com",
                url="https://technologyreview.com/article1",
                source_reliability="high",
                stance="CONTRADICTING",
                snippet="No quantum computer has factored RSA-2048 to date.",
            ),
            EvidencePacketItem(
                evidence_id="ev_valid_2",
                title="Nature Physics",
                publisher="Nature",
                domain="nature.com",
                url="https://nature.com/article2",
                source_reliability="high",
                stance="CONTRADICTING",
                snippet="RSA-2048 remains unbroken by existing quantum hardware.",
            ),
        ],
    )


def test_validator_preserves_grounded_findings():
    packet = _make_packet()

    raw_result = AIReasoningResult(
        claim_id=packet.claim_id,
        claim_text=packet.claim_text,
        summary="Independent scientific sources contradict the claim.",
        key_findings=[
            EvidenceFinding(
                text="MIT Tech Review reports no quantum machine has factored RSA-2048.",
                evidence_ids=["ev_valid_1"],
                stance="CONTRADICTING",
                importance=FindingImportance.HIGH,
                confidence=0.95,
            )
        ],
        supporting_findings=[],
        contradicting_findings=[
            EvidenceFinding(
                text="Nature Physics confirms RSA-2048 remains unbroken.",
                evidence_ids=["ev_valid_2"],
                stance="CONTRADICTING",
                importance=FindingImportance.HIGH,
                confidence=0.98,
            )
        ],
        important_discrepancies=[],
        source_observations=["Sources are reputable peer-reviewed / tech journalism."],
        independence_observations=["Multiple separate research outlets."],
        fact_check_observations=[],
        verification_gaps=["Experimental proof from other labs."],
        uncertainty=UncertaintyLevel.LOW,
        reasoning_steps=["Checked reports against physics literature."],
        limitations=["Hardware advances are ongoing."],
    )

    sanitized, warnings = validate_and_sanitize_reasoning(raw_result, packet)
    assert sanitized.claim_id == packet.claim_id
    assert len(sanitized.key_findings) == 1
    assert sanitized.key_findings[0].evidence_ids == ["ev_valid_1"]
    assert len(sanitized.contradicting_findings) == 1
    assert sanitized.contradicting_findings[0].evidence_ids == ["ev_valid_2"]
    assert sanitized.uncertainty == UncertaintyLevel.LOW
    assert len(warnings) == 0


def test_validator_prunes_hallucinated_ids():
    packet = _make_packet()

    raw_result = AIReasoningResult(
        claim_id=packet.claim_id,
        claim_text=packet.claim_text,
        summary="Summary with hallucinated evidence IDs.",
        key_findings=[
            EvidenceFinding(
                text="Some invented claim.",
                evidence_ids=["ev_valid_1", "ev_hallucinated_99", "ghost_id"],
                stance="CONTRADICTING",
                importance=FindingImportance.HIGH,
                confidence=0.9,
            )
        ],
        uncertainty=UncertaintyLevel.MEDIUM,
    )

    sanitized, warnings = validate_and_sanitize_reasoning(raw_result, packet)
    assert len(sanitized.key_findings) == 1
    # Only valid ID must remain
    assert sanitized.key_findings[0].evidence_ids == ["ev_valid_1"]
    assert "ev_hallucinated_99" not in sanitized.key_findings[0].evidence_ids
    assert "ghost_id" not in sanitized.key_findings[0].evidence_ids
    assert len(warnings) > 0
