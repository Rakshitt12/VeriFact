from backend.verification.consensus_analyzer import analyze_consensus
from backend.verification.discrepancy_detector import detect_discrepancies, extract_quantities
from backend.verification.duplicate_detector import detect_duplicate_relationship
from backend.verification.evidence_comparator import compare_all_evidence_for_claim
from backend.verification.factcheck_mapper import (
    is_fact_check_evidence,
    map_fact_check_comparison,
    map_raw_rating_to_verdict_and_stance,
)
from backend.verification.independence_analyzer import (
    cluster_and_analyze_independence,
    evaluate_pair_independence,
)
from backend.verification.models import (
    AspectMatch,
    AspectType,
    ClaimEvidenceComparisonResult,
    ClaimIndependenceResult,
    ClusterType,
    Discrepancy,
    DiscrepancyType,
    EvidenceCluster,
    EvidenceComparison,
    EvidenceRelationship,
    EvidenceStance,
    FactCheckComparison,
    IndependenceAnalysis,
    IndependenceStatus,
    RelationshipType,
)
from backend.verification.service import (
    VerificationService,
    analyze_evidence_independence,
    compare_evidence_for_claim,
)
from backend.verification.similarity import (
    compute_content_similarity,
    compute_title_similarity,
    extract_distinctive_phrases,
    jaccard_similarity,
    normalize_text_for_similarity,
)
from backend.verification.stance_detector import classify_evidence_stance
from backend.verification.syndication_detector import detect_syndication_relationship

__all__ = [
    # Part 6
    "RelationshipType",
    "ClusterType",
    "IndependenceStatus",
    "EvidenceRelationship",
    "EvidenceCluster",
    "IndependenceAnalysis",
    "ClaimIndependenceResult",
    "detect_duplicate_relationship",
    "detect_syndication_relationship",
    "evaluate_pair_independence",
    "cluster_and_analyze_independence",
    "VerificationService",
    "analyze_evidence_independence",
    "normalize_text_for_similarity",
    "jaccard_similarity",
    "compute_title_similarity",
    "compute_content_similarity",
    "extract_distinctive_phrases",
    # Part 7
    "EvidenceStance",
    "AspectType",
    "AspectMatch",
    "DiscrepancyType",
    "Discrepancy",
    "EvidenceComparison",
    "FactCheckComparison",
    "ClaimEvidenceComparisonResult",
    "detect_discrepancies",
    "extract_quantities",
    "classify_evidence_stance",
    "compare_all_evidence_for_claim",
    "analyze_consensus",
    "compare_evidence_for_claim",
    "is_fact_check_evidence",
    "map_fact_check_comparison",
    "map_raw_rating_to_verdict_and_stance",
]
