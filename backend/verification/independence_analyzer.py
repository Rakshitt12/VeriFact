"""Source independence analysis and evidence clustering.

Groups retrieved evidence into disjoint clusters of duplicates or syndicated reports,
identifies representative articles, and calculates the true independent source count.

Rule: Number of articles != number of independent confirmations.
"""

from __future__ import annotations

import hashlib
from typing import Dict, List, Optional, Set, Tuple

from backend.retrieval.models import Evidence
from backend.sources.models import SourceAnalysis, SourceCategory
from backend.verification.duplicate_detector import detect_duplicate_relationship
from backend.verification.models import (
    ClaimIndependenceResult,
    ClusterType,
    EvidenceCluster,
    EvidenceRelationship,
    IndependenceAnalysis,
    IndependenceStatus,
    RelationshipType,
)
from backend.verification.similarity import (
    compute_content_similarity,
    compute_title_similarity,
)
from backend.verification.syndication_detector import detect_syndication_relationship


def _find_representative_evidence_id(
    evidence_items: List[Evidence],
    source_analyses_by_id: Dict[str, SourceAnalysis],
) -> Optional[str]:
    """Select the best representative evidence item in a cluster.

    Heuristic priorities:
    1. Direct wire service or official/regulatory origin (reuters.com, pib.gov.in, etc.)
    2. Primary firsthand reporting indicators
    3. Earliest publication timestamp
    4. Longest content length
    """
    if not evidence_items:
        return None
    if len(evidence_items) == 1:
        return evidence_items[0].evidence_id

    scored_candidates: List[Tuple[float, Evidence]] = []

    for ev in evidence_items:
        score = 0.0
        sa = source_analyses_by_id.get(ev.evidence_id)

        # Wire service / Institutional origin bonus
        if sa:
            if sa.source_category in (SourceCategory.GOVERNMENT, SourceCategory.REGULATORY):
                score += 50.0
            elif sa.source_category == SourceCategory.FACT_CHECKER:
                score += 40.0
            elif sa.domain in ("reuters.com", "apnews.com", "afp.com"):
                score += 45.0
            if sa.primary_reporting.present:
                score += 20.0
            score += sa.metadata_quality.score * 10.0

        # Content length bonus (more comprehensive text preferred)
        content_len = len(ev.content or ev.snippet or "")
        score += min(content_len / 100.0, 15.0)

        # Earliest publication bonus
        if ev.published_at:
            score += 10.0

        scored_candidates.append((score, ev))

    scored_candidates.sort(key=lambda x: x[0], reverse=True)
    return scored_candidates[0][1].evidence_id


def evaluate_pair_independence(
    ev_a: Evidence,
    ev_b: Evidence,
) -> EvidenceRelationship:
    """Analyze the relationship between a pair of evidence items.

    Checks duplicates first, then syndication, then independent reporting signals.
    """
    # 1. Exact or near duplicate check
    dup_rel = detect_duplicate_relationship(ev_a, ev_b)
    if dup_rel:
        return dup_rel

    # 2. Syndication / wire agency / secondary derivation check
    syn_rel = detect_syndication_relationship(ev_a, ev_b)
    if syn_rel:
        return syn_rel

    # 3. Independent reporting evaluation
    text_a = f"{ev_a.title} {ev_a.snippet or ''}"
    text_b = f"{ev_b.title} {ev_b.snippet or ''}"
    title_sim = compute_title_similarity(ev_a.title, ev_b.title)
    content_sim = compute_content_similarity(text_a, text_b)

    signals = []
    limitations = []

    # Distinct domains and low textual overlap indicate independent reporting
    diff_domains = bool(ev_a.domain and ev_b.domain and ev_a.domain.lower() != ev_b.domain.lower())
    if diff_domains and content_sim < 0.40:
        signals.append("Published on independent domains with distinct phrasing and reporting angles")
        if title_sim < 0.50:
            signals.append("Different headline formulation")
        return EvidenceRelationship(
            evidence_id_a=ev_a.evidence_id,
            evidence_id_b=ev_b.evidence_id,
            relationship_type=RelationshipType.LIKELY_INDEPENDENT,
            similarity_score=round(max(title_sim, content_sim), 3),
            confidence=0.85,
            signals=signals,
            limitations=[],
        )

    # Moderate similarity on different domains with no shared wire detected
    signals.append(f"Moderate similarity ({max(title_sim, content_sim):.2f}) covering the same subject")
    limitations.append("Insufficient textual divergence to decisively prove full newsroom independence")
    return EvidenceRelationship(
        evidence_id_a=ev_a.evidence_id,
        evidence_id_b=ev_b.evidence_id,
        relationship_type=RelationshipType.UNKNOWN,
        similarity_score=round(max(title_sim, content_sim), 3),
        confidence=0.50,
        signals=signals,
        limitations=limitations,
    )


def cluster_and_analyze_independence(
    evidence_items: List[Evidence],
    source_analyses: Optional[List[SourceAnalysis]] = None,
    claim_id: str = "",
) -> ClaimIndependenceResult:
    """Analyze pairwise relationships, group evidence into clusters, and compute true independent count."""
    if not evidence_items:
        return ClaimIndependenceResult(
            claim_id=claim_id,
            total_evidence_count=0,
            independent_source_count=0,
            clusters=[],
            relationships=[],
            analyses=[],
        )

    source_analyses_by_id = {sa.evidence_id: sa for sa in (source_analyses or [])}
    evidence_by_id = {ev.evidence_id: ev for ev in evidence_items}

    # 1. Compute pairwise relationships
    relationships: List[EvidenceRelationship] = []
    n = len(evidence_items)
    for i in range(n):
        for j in range(i + 1, n):
            rel = evaluate_pair_independence(evidence_items[i], evidence_items[j])
            relationships.append(rel)

    # 2. Build connected components for duplicate / syndicated relationships
    # Disjoint-set / Union-Find over evidence_ids
    parent: Dict[str, str] = {ev.evidence_id: ev.evidence_id for ev in evidence_items}

    def find(x: str) -> str:
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def union(x: str, y: str):
        root_x = find(x)
        root_y = find(y)
        if root_x != root_y:
            parent[root_y] = root_x

    # Union pairs that are duplicates or syndicated
    for rel in relationships:
        if rel.relationship_type in (
            RelationshipType.EXACT_DUPLICATE,
            RelationshipType.NEAR_DUPLICATE,
            RelationshipType.SYNDICATED,
            RelationshipType.LIKELY_DERIVED,
        ):
            union(rel.evidence_id_a, rel.evidence_id_b)

    # Group into clusters
    groups: Dict[str, List[str]] = {}
    for ev in evidence_items:
        root = find(ev.evidence_id)
        groups.setdefault(root, []).append(ev.evidence_id)

    # 3. Create EvidenceCluster objects
    clusters: List[EvidenceCluster] = []
    analyses: List[IndependenceAnalysis] = []

    cluster_counter = 1
    for root_id, member_ids in groups.items():
        member_evidences = [evidence_by_id[mid] for mid in member_ids]
        cluster_id = f"cluster_{claim_id[:8]}_{cluster_counter}"
        cluster_counter += 1

        # Determine cluster type and relationships inside cluster
        internal_rels = [
            r for r in relationships
            if r.evidence_id_a in member_ids and r.evidence_id_b in member_ids
        ]
        has_dup = any(
            r.relationship_type in (RelationshipType.EXACT_DUPLICATE, RelationshipType.NEAR_DUPLICATE)
            for r in internal_rels
        )
        has_syn = any(
            r.relationship_type in (RelationshipType.SYNDICATED, RelationshipType.LIKELY_DERIVED)
            for r in internal_rels
        )

        if len(member_ids) == 1:
            cluster_type = ClusterType.INDEPENDENT
            indep_status = IndependenceStatus.LIKELY_INDEPENDENT
            cluster_confidence = 0.90
            signals = ["Single standalone reporting source with distinct provenance"]
            limitations = []
        elif has_dup and has_syn:
            cluster_type = ClusterType.MIXED
            indep_status = IndependenceStatus.LIKELY_DERIVED
            cluster_confidence = 0.85
            signals = [f"Cluster contains {len(member_ids)} articles sharing duplicate and syndicated content"]
            limitations = ["Represents a single underlying story republished across multiple outlets"]
        elif has_dup:
            cluster_type = ClusterType.DUPLICATE
            indep_status = IndependenceStatus.LIKELY_DERIVED
            cluster_confidence = 0.92
            signals = [f"Cluster of {len(member_ids)} exact or near-duplicate articles"]
            limitations = ["Multiple URLs correspond to the same underlying article"]
        else:
            cluster_type = ClusterType.SYNDICATION
            indep_status = IndependenceStatus.LIKELY_DERIVED
            cluster_confidence = 0.88
            signals = [f"Syndication network of {len(member_ids)} outlets sharing common wire or reporting copy"]
            limitations = ["Multiple outlets reporting from the same wire release"]

        # Select representative evidence
        rep_id = _find_representative_evidence_id(member_evidences, source_analyses_by_id)

        cluster = EvidenceCluster(
            cluster_id=cluster_id,
            evidence_ids=member_ids,
            cluster_type=cluster_type,
            representative_evidence_id=rep_id,
            independence_status=indep_status,
            confidence=cluster_confidence,
            signals=signals,
            limitations=limitations,
        )
        clusters.append(cluster)

        # Formulate per-item IndependenceAnalysis
        for mid in member_ids:
            related = [oid for oid in member_ids if oid != mid]
            if len(member_ids) == 1:
                item_status = IndependenceStatus.LIKELY_INDEPENDENT
                item_conf = 0.90
                item_signals = ["Distinct reporting source not derived from other retrieved articles"]
                item_limits = []
            elif mid == rep_id:
                item_status = IndependenceStatus.LIKELY_INDEPENDENT
                item_conf = 0.80
                item_signals = [f"Selected as representative origin for {len(member_ids)}-article cluster"]
                item_limits = ["Multiple republished or syndicated versions detected"]
            else:
                item_status = IndependenceStatus.LIKELY_DERIVED
                item_conf = 0.85
                item_signals = [f"Republished / syndicated variant of cluster representative ({rep_id})"]
                item_limits = ["Does not count as an independent additional confirmation"]

            analyses.append(
                IndependenceAnalysis(
                    evidence_id=mid,
                    cluster_id=cluster_id,
                    independence_status=item_status,
                    independence_confidence=item_conf,
                    related_evidence_ids=related,
                    signals=item_signals,
                    limitations=item_limits,
                )
            )

    # Crucial metric: count of independent reporting sources is the count of clusters
    independent_count = len(clusters)

    return ClaimIndependenceResult(
        claim_id=claim_id,
        total_evidence_count=len(evidence_items),
        independent_source_count=independent_count,
        clusters=clusters,
        relationships=relationships,
        analyses=analyses,
    )
