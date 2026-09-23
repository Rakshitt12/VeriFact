"""FastAPI route handlers for verification, health, config, and analysis."""

import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status

from backend.api.schemas import (
    AIReasoningResponse,
    ClassificationLabel,
    ClaimResult,
    DuplicateCluster,
    EvidenceFindingItem,
    EvidenceItem,
    EvidenceStance,
    FactCheckItem,
    HealthResponse,
    InputSummary,
    InputType,
    RetrievedEvidenceItem,
    SourceAnalysisItem,
    VerificationGap,
    VerificationRequest,
    VerificationResponse,
)
from backend.ai import reason_about_claim_evidence
from backend.claim.claim_extractor import extract_claims
from backend.retrieval.service import retrieve_evidence
from backend.sources.source_analyzer import analyze_sources
from backend.scoring import CredibilityScoringService
from backend.report import VerificationReportService
from backend.verification import (
    IndependenceStatus,
    analyze_evidence_independence,
    compare_evidence_for_claim,
)
from backend.config.settings import settings
from backend.config.scoring_config import (
    CLASSIFICATION_THRESHOLDS,
    MIN_INDEPENDENT_SOURCES,
    SCORING_WEIGHTS,
)
from backend.ingestion.errors import IngestionError
from backend.ingestion.service import ingest_input
from backend.logging_config import logger


router = APIRouter()
scoring_service = CredibilityScoringService()
report_service = VerificationReportService()


@router.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check() -> HealthResponse:
    """Check service health and operational status."""
    return HealthResponse(
        status="ok",
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.APP_ENV,
    )


@router.get("/config", tags=["System"])
async def get_config():
    """Retrieve non-sensitive public scoring configuration."""
    return {
        "scoring_weights": SCORING_WEIGHTS,
        "classification_thresholds": CLASSIFICATION_THRESHOLDS,
        "min_independent_sources": MIN_INDEPENDENT_SOURCES,
        "min_input_length": settings.MIN_INPUT_LENGTH,
        "max_input_length": settings.MAX_INPUT_LENGTH,
    }


@router.post(
    "/analyze",
    response_model=VerificationResponse,
    status_code=status.HTTP_200_OK,
    tags=["Verification"],
)
async def analyze_claim_or_article(request: VerificationRequest) -> VerificationResponse:
    """Analyze news claim or article URL.

    Part 2 implementation:
    - Validates request length constraints
    - Executes ingestion (text normalization or secure URL extraction)
    - Returns structured response with verified InputSummary populated from ingested article
    - Returns INSUFFICIENT EVIDENCE status pending downstream claim extraction (Part 3) and retrieval
    """
    cleaned_content = request.content.strip()

    if len(cleaned_content) < settings.MIN_INPUT_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Input content is too short. Minimum required length is {settings.MIN_INPUT_LENGTH} characters.",
        )

    if len(cleaned_content) > settings.MAX_INPUT_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Input content exceeds maximum length of {settings.MAX_INPUT_LENGTH} characters.",
        )

    logger.info(
        "Processing verification request (type=%s, length=%d)",
        request.input_type.value,
        len(cleaned_content),
    )

    # Ingest text or URL
    try:
        article = ingest_input(request.input_type, cleaned_content)
    except IngestionError as exc:
        logger.warning("Ingestion failed: [%s] %s", exc.error_code, exc.message)
        raise HTTPException(
            status_code=exc.status_code,
            detail={
                "error": exc.error_code,
                "message": exc.message,
            },
        )
    except Exception as exc:
        logger.error("Unexpected ingestion error: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while ingesting the submitted content.",
        )

    request_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    # Populate verified input summary from normalized article
    input_summary = InputSummary(
        title=article.title,
        publisher=article.publisher,
        author=article.author,
        published_at=article.published_at,
        domain=article.domain,
        url=article.url or (cleaned_content if request.input_type == InputType.URL else None),
    )

    # Extract verifiable factual claims
    extracted = extract_claims(article)
    logger.info("Extracted %d claims from ingested article", len(extracted))

    # Retrieve evidence from external providers
    retrieval_result = await retrieve_evidence(extracted)
    logger.info(
        "Retrieved %d total evidence items in %.1fms",
        retrieval_result.total_evidence_count,
        retrieval_result.retrieval_duration_ms,
    )

    # Build lookup map of claim_id -> ClaimEvidence
    evidence_by_claim = {ce.claim_id: ce for ce in retrieval_result.claims}

    claims_results: list[ClaimResult] = []
    claim_cred_scores = []
    # Part 10 — per-claim data collectors for report generation
    all_evidence_map: dict[str, list] = {}
    all_source_analyses_map: dict[str, list] = {}
    all_independence_map: dict = {}
    all_comparisons_map: dict = {}
    all_claim_scores_map: dict = {}
    all_ai_reasoning_map: dict = {}
    if extracted:
        for c in extracted:
            claim_ev = evidence_by_claim.get(c.claim_id)
            ev_items = claim_ev.evidence if claim_ev else []

            retrieved_items = [
                RetrievedEvidenceItem(
                    evidence_id=e.evidence_id,
                    title=e.title,
                    url=e.url,
                    publisher=e.publisher,
                    domain=e.domain,
                    snippet=e.snippet,
                    source_type=e.source_type.value,
                    provider=e.provider,
                    published_at=e.published_at,
                    query_used=e.query_used,
                    metadata=e.metadata,
                )
                for e in ev_items
            ]

            # Execute Part 5 Source Analysis on retrieved evidence
            source_analyses = analyze_sources(ev_items)

            # Execute Part 6 Duplicate, Syndication & Independence Detection
            independence_result = analyze_evidence_independence(
                evidence_items=ev_items,
                source_analyses=source_analyses,
                claim_id=c.claim_id,
            )

            # Map independence metadata by evidence_id
            analysis_by_eid = {a.evidence_id: a for a in independence_result.analyses}

            source_analysis_items = [
                SourceAnalysisItem(
                    domain=sa.domain,
                    publisher=sa.publisher or sa.domain,
                    reliability_tier=sa.reliability_label.value.lower(),
                    transparency_score=sa.metadata_quality.score,
                    type=sa.source_category.value.lower(),
                    is_primary_source=sa.primary_reporting.present,
                    is_duplicate=bool(
                        analysis_by_eid.get(sa.evidence_id)
                        and analysis_by_eid[sa.evidence_id].independence_status == IndependenceStatus.LIKELY_DERIVED
                    ),
                    cluster_id=(
                        analysis_by_eid[sa.evidence_id].cluster_id
                        if sa.evidence_id in analysis_by_eid
                        else None
                    ),
                    evidence_id=sa.evidence_id,
                    reliability_score=sa.reliability_score,
                    transparency_level=sa.transparency.value,
                    source_category=sa.source_category.value,
                    source_age=sa.source_age.value,
                    signals=sa.signals,
                    limitations=sa.limitations,
                )
                for sa in source_analyses
            ]

            # Build duplicate cluster summary objects for multi-item clusters
            duplicate_clusters = [
                DuplicateCluster(
                    cluster_id=cl.cluster_id,
                    origin={
                        "representative_evidence_id": cl.representative_evidence_id,
                        "cluster_type": cl.cluster_type.value,
                        "confidence": cl.confidence,
                    },
                    duplicates=[
                        {"evidence_id": eid}
                        for eid in cl.evidence_ids
                        if eid != cl.representative_evidence_id
                    ],
                    cluster_size=len(cl.evidence_ids),
                    counted_as_independent=1,
                )
                for cl in independence_result.clusters
                if len(cl.evidence_ids) > 1
            ]

            # Execute Part 7 Evidence Comparison & Stance Detection
            comparison_result = compare_evidence_for_claim(
                claim=c,
                evidence_items=ev_items,
                clusters=independence_result.clusters,
            )

            # Map raw evidence and source analysis for schema population
            ev_by_id = {e.evidence_id: e for e in ev_items}
            sa_by_eid = {sa.evidence_id: sa for sa in source_analyses}

            supporting_items: list[EvidenceItem] = []
            contradicting_items: list[EvidenceItem] = []
            neutral_items: list[EvidenceItem] = []

            for comp in comparison_result.comparisons:
                ev_orig = ev_by_id.get(comp.evidence_id)
                if not ev_orig:
                    continue
                sa_orig = sa_by_eid.get(comp.evidence_id)
                e_item = EvidenceItem(
                    evidence_id=comp.evidence_id,
                    title=ev_orig.title,
                    url=ev_orig.url,
                    publisher=ev_orig.publisher or ev_orig.domain or "Unknown",
                    published_at=ev_orig.published_at,
                    snippet=ev_orig.snippet or "",
                    stance=EvidenceStance(comp.stance.value),
                    rationale=comp.reasoning,
                    is_primary_source=sa_orig.primary_reporting.present if sa_orig else False,
                    source_reliability=sa_orig.reliability_label.value.lower() if sa_orig else "unknown",
                )
                if comp.stance.value == "SUPPORTING":
                    supporting_items.append(e_item)
                elif comp.stance.value == "CONTRADICTING":
                    contradicting_items.append(e_item)
                else:
                    neutral_items.append(e_item)

            fact_check_items = [
                FactCheckItem(
                    fact_check_id=fc.fact_check_id,
                    claim_text=c.original_text,
                    verdict=fc.verdict_normalized,
                    rating_label=fc.raw_rating,
                    fact_checker=fc.fact_checker,
                    url=fc.url,
                    published_at=fc.published_at,
                    explanation=fc.explanation,
                )
                for fc in comparison_result.fact_checks
            ]

            # Execute Part 8 AI Evidence Reasoning
            ai_reasoning = await reason_about_claim_evidence(
                claim=c,
                evidence_items=ev_items,
                source_analyses=source_analyses,
                independence_result=independence_result,
                comparison_result=comparison_result,
            )

            reasoning_response = AIReasoningResponse(
                summary=ai_reasoning.summary,
                key_findings=[
                    EvidenceFindingItem(
                        text=f.text,
                        evidence_ids=f.evidence_ids,
                        stance=f.stance,
                        importance=f.importance.value if hasattr(f.importance, "value") else str(f.importance),
                        confidence=f.confidence,
                    )
                    for f in ai_reasoning.key_findings
                ],
                supporting_findings=[
                    EvidenceFindingItem(
                        text=f.text,
                        evidence_ids=f.evidence_ids,
                        stance=f.stance,
                        importance=f.importance.value if hasattr(f.importance, "value") else str(f.importance),
                        confidence=f.confidence,
                    )
                    for f in ai_reasoning.supporting_findings
                ],
                contradicting_findings=[
                    EvidenceFindingItem(
                        text=f.text,
                        evidence_ids=f.evidence_ids,
                        stance=f.stance,
                        importance=f.importance.value if hasattr(f.importance, "value") else str(f.importance),
                        confidence=f.confidence,
                    )
                    for f in ai_reasoning.contradicting_findings
                ],
                important_discrepancies=ai_reasoning.important_discrepancies,
                source_observations=ai_reasoning.source_observations,
                independence_observations=ai_reasoning.independence_observations,
                fact_check_observations=ai_reasoning.fact_check_observations,
                verification_gaps=ai_reasoning.verification_gaps,
                uncertainty=ai_reasoning.uncertainty.value if hasattr(ai_reasoning.uncertainty, "value") else str(ai_reasoning.uncertainty),
                reasoning_steps=ai_reasoning.reasoning_steps,
                limitations=ai_reasoning.limitations,
                ai_used=ai_reasoning.ai_used,
                provider=ai_reasoning.provider,
                model=ai_reasoning.model,
                fallback_used=ai_reasoning.fallback_used,
            )

            verification_gap_items = [
                VerificationGap(gap_type="evidence_gap", description=gap_str)
                for gap_str in ai_reasoning.verification_gaps
            ]

            claim_summary = ai_reasoning.summary or comparison_result.summary
            if not claim_summary:
                claim_summary = (
                    f"Claim ({c.claim_type.value}, importance: {c.importance.value}) extracted. "
                    f"Retrieved {len(retrieved_items)} evidence item(s) resolved into "
                    f"{independence_result.independent_source_count} independent source cluster(s)."
                )

            # Execute Part 9 Credibility Scoring Engine
            claim_cred_score = scoring_service.score_claim(
                claim_id=c.claim_id,
                claim_text=c.original_text,
                evidence_items=ev_items,
                source_analyses=source_analyses,
                independence_result=independence_result,
                comparison_result=comparison_result,
            )
            claim_cred_scores.append(claim_cred_score)

            # Collect Part 10 data keyed by claim_id
            all_evidence_map[c.claim_id] = ev_items
            all_source_analyses_map[c.claim_id] = source_analyses
            all_independence_map[c.claim_id] = independence_result
            all_comparisons_map[c.claim_id] = comparison_result
            all_claim_scores_map[c.claim_id] = claim_cred_score
            all_ai_reasoning_map[c.claim_id] = ai_reasoning

            claims_results.append(
                ClaimResult(
                    claim_id=c.claim_id,
                    claim_text=c.original_text,
                    score=claim_cred_score.score,
                    classification=claim_cred_score.classification,
                    summary=claim_summary or claim_cred_score.summary,
                    supporting_evidence=supporting_items,
                    contradicting_evidence=contradicting_items,
                    neutral_evidence=neutral_items,
                    fact_checks=fact_check_items,
                    source_analysis=source_analysis_items,
                    duplicate_clusters=duplicate_clusters,
                    score_breakdown=claim_cred_score.score_breakdown,
                    verification_gaps=verification_gap_items,
                    evidence_reasoning=reasoning_response,
                    independent_source_count=independence_result.independent_source_count,
                    total_evidence_count=len(retrieved_items),
                    retrieved_evidence=retrieved_items,
                )
            )

        # Aggregate document-level score across all evaluated claims
        doc_cred_score = scoring_service.score_document(
            claim_scores=claim_cred_scores,
            claims=extracted,
        )
        overall_score = doc_cred_score.overall_score
        overall_classification = doc_cred_score.overall_classification
        overall_summary = doc_cred_score.summary

        # Part 10 — Generate explainable verification report
        report = report_service.generate_report(
            article=article,
            extracted_claims=extracted,
            all_evidence=all_evidence_map,
            all_source_analyses=all_source_analyses_map,
            all_independence=all_independence_map,
            all_comparisons=all_comparisons_map,
            all_claim_scores=all_claim_scores_map,
            all_ai_reasoning=all_ai_reasoning_map,
            doc_cred_score=doc_cred_score,
            request_type=request.input_type.value,
        )

    else:
        # Fallback if text contained no verifiable claims
        display_claim_text = (
            article.title
            or article.body[:200]
            + ("..." if len(article.body) > 200 else "")
        )
        claims_results.append(
            ClaimResult(
                claim_id=f"claim_{request_id[:8]}",
                claim_text=display_claim_text,
                score=None,
                classification=ClassificationLabel.INSUFFICIENT_EVIDENCE.value,
                summary="No discrete verifiable factual assertions detected in submitted content.",
                supporting_evidence=[],
                contradicting_evidence=[],
                neutral_evidence=[],
                fact_checks=[],
                source_analysis=[],
                duplicate_clusters=[],
                score_breakdown=[],
                verification_gaps=[],
                independent_source_count=0,
                total_evidence_count=0,
                retrieved_evidence=[],
            )
        )
        overall_score = None
        overall_classification = ClassificationLabel.INSUFFICIENT_EVIDENCE.value
        overall_summary = "No discrete verifiable factual assertions detected in submitted content."
        report = None  # No claims → no structured report

    return VerificationResponse(
        request_id=request_id,
        processed_at=now,
        input_type=request.input_type,
        input_summary=input_summary,
        claims=claims_results,
        overall_score=overall_score,
        overall_classification=overall_classification,
        overall_summary=overall_summary,
        limitations=[
            "Credibility score is deterministic and reflects currently indexed and retrieved evidence.",
            "This system cannot access paywalled content.",
            "Evidence retrieval is limited to sources indexed by configured providers.",
            "The credibility score represents evidence strength, not a guaranteed truth determination.",
        ],
        report=report,
    )



@router.post(
    "/verify",
    response_model=VerificationResponse,
    status_code=status.HTTP_200_OK,
    tags=["Verification"],
)
async def verify_claim_or_article(request: VerificationRequest) -> VerificationResponse:
    """Alias for /analyze matching README Section 19."""
    return await analyze_claim_or_article(request)
