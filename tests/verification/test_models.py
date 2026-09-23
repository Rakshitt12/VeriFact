"""Unit tests for verification data models and enums."""

import pytest
from pydantic import ValidationError

from backend.verification.models import (
    ClaimIndependenceResult,
    ClusterType,
    EvidenceCluster,
    EvidenceRelationship,
    IndependenceAnalysis,
    IndependenceStatus,
    RelationshipType,
)


def test_relationship_type_enum():
    """Verify supported relationship types."""
    assert RelationshipType.EXACT_DUPLICATE == "EXACT_DUPLICATE"
    assert RelationshipType.NEAR_DUPLICATE == "NEAR_DUPLICATE"
    assert RelationshipType.SYNDICATED == "SYNDICATED"
    assert RelationshipType.LIKELY_DERIVED == "LIKELY_DERIVED"
    assert RelationshipType.LIKELY_INDEPENDENT == "LIKELY_INDEPENDENT"
    assert RelationshipType.UNKNOWN == "UNKNOWN"


def test_cluster_type_enum():
    """Verify supported cluster types."""
    assert ClusterType.DUPLICATE == "DUPLICATE"
    assert ClusterType.SYNDICATION == "SYNDICATION"
    assert ClusterType.MIXED == "MIXED"
    assert ClusterType.INDEPENDENT == "INDEPENDENT"
    assert ClusterType.UNKNOWN == "UNKNOWN"


def test_independence_status_enum():
    """Verify independence status levels."""
    assert IndependenceStatus.LIKELY_INDEPENDENT == "LIKELY_INDEPENDENT"
    assert IndependenceStatus.LIKELY_DERIVED == "LIKELY_DERIVED"
    assert IndependenceStatus.POSSIBLY_DERIVED == "POSSIBLY_DERIVED"
    assert IndependenceStatus.UNKNOWN == "UNKNOWN"


def test_evidence_relationship_valid():
    """Verify EvidenceRelationship creation and bounds."""
    rel = EvidenceRelationship(
        evidence_id_a="ev_1",
        evidence_id_b="ev_2",
        relationship_type=RelationshipType.SYNDICATED,
        similarity_score=0.88,
        confidence=0.92,
        signals=["Common wire agency attribution"],
        limitations=["Published on different domains"],
    )
    assert rel.evidence_id_a == "ev_1"
    assert rel.relationship_type == RelationshipType.SYNDICATED
    assert rel.similarity_score == 0.88


def test_evidence_relationship_invalid_score():
    """Verify bounds checking for similarity and confidence (0.0 to 1.0)."""
    with pytest.raises(ValidationError):
        EvidenceRelationship(
            evidence_id_a="ev_1",
            evidence_id_b="ev_2",
            relationship_type=RelationshipType.NEAR_DUPLICATE,
            similarity_score=1.5,  # Exceeds 1.0
            confidence=0.9,
        )


def test_evidence_cluster_and_claim_result():
    """Verify EvidenceCluster and ClaimIndependenceResult packaging."""
    cluster = EvidenceCluster(
        cluster_id="cl_01",
        evidence_ids=["ev_1", "ev_2"],
        cluster_type=ClusterType.DUPLICATE,
        representative_evidence_id="ev_1",
        independence_status=IndependenceStatus.LIKELY_DERIVED,
        confidence=0.95,
        signals=["Same canonical URL"],
    )
    result = ClaimIndependenceResult(
        claim_id="claim_001",
        total_evidence_count=2,
        independent_source_count=1,
        clusters=[cluster],
        relationships=[],
        analyses=[],
    )
    assert result.total_evidence_count == 2
    assert result.independent_source_count == 1
    assert len(result.clusters) == 1
    assert result.clusters[0].representative_evidence_id == "ev_1"
