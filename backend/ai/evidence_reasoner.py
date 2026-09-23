"""Orchestrates bounded evidence packet construction, AI reasoning, and graceful fallback."""

from __future__ import annotations

import asyncio
from typing import List, Optional

from backend.ai.fallback_reasoner import generate_fallback_reasoning
from backend.ai.grounding_validator import validate_and_sanitize_reasoning
from backend.ai.llm_client import LLMClient, LLMError, get_llm_client
from backend.ai.models import AIReasoningResult, EvidencePacket
from backend.ai.packet_builder import build_evidence_packet
from backend.ai.prompts import build_reasoning_prompt
from backend.claim.models import Claim
from backend.config.settings import settings
from backend.logging_config import logger
from backend.retrieval.models import Evidence
from backend.sources.models import SourceAnalysis
from backend.verification.models import (
    ClaimEvidenceComparisonResult,
    ClaimIndependenceResult,
)


class EvidenceReasoner:
    """Orchestrator for grounded AI evidence synthesis and deterministic fallback."""

    def __init__(self, llm_client: Optional[LLMClient] = None) -> None:
        self.llm_client = llm_client

    async def reason(
        self,
        claim: Claim,
        evidence_items: List[Evidence],
        source_analyses: Optional[List[SourceAnalysis]] = None,
        independence_result: Optional[ClaimIndependenceResult] = None,
        comparison_result: Optional[ClaimEvidenceComparisonResult] = None,
    ) -> AIReasoningResult:
        """Construct bounded evidence packet, perform AI reasoning or trigger deterministic fallback."""
        # 1. Build bounded evidence packet
        packet = build_evidence_packet(
            claim=claim,
            evidence_items=evidence_items,
            source_analyses=source_analyses,
            independence_result=independence_result,
            comparison_result=comparison_result,
        )

        # 2. Check if LLM is enabled and configured
        if not settings.LLM_ENABLED and self.llm_client is None:
            logger.info("LLM_ENABLED is False. Executing deterministic fallback reasoning for claim %s", claim.claim_id)
            return generate_fallback_reasoning(packet)

        client = self.llm_client or get_llm_client()

        # 3. Attempt LLM Reasoning
        try:
            logger.info("Dispatching evidence packet (%d items) to %s for claim %s", len(packet.evidence), client.provider_name, claim.claim_id)
            system_prompt, user_prompt = build_reasoning_prompt(packet)
            
            raw_result = await client.generate_structured(
                system_instruction=system_prompt,
                user_prompt=user_prompt,
                response_model=AIReasoningResult,
            )

            # 4. Set provenance metadata
            claim_text = getattr(claim, "original_text", getattr(claim, "claim_text", ""))
            raw_result.claim_id = claim.claim_id
            raw_result.claim_text = claim_text
            raw_result.ai_used = True
            raw_result.fallback_used = False
            raw_result.provider = client.provider_name
            raw_result.model = settings.LLM_MODEL

            # 5. Validate grounding and sanitize hallucinations
            validated_result, warnings = validate_and_sanitize_reasoning(raw_result, packet)
            validated_result.claim_id = claim.claim_id
            validated_result.claim_text = claim_text
            if warnings:
                logger.info("Sanitized %d ungrounded references in AI output for claim %s", len(warnings), claim.claim_id)

            return validated_result

        except LLMError as exc:
            logger.warning("LLM reasoning failed [%s: %s]. Engaging deterministic fallback reasoner.", exc.provider, exc.message)
            return generate_fallback_reasoning(packet)
        except Exception as exc:
            logger.error("Unexpected error during AI reasoning: %s. Engaging deterministic fallback reasoner.", exc, exc_info=True)
            return generate_fallback_reasoning(packet)

    def reason_sync(
        self,
        claim: Claim,
        evidence_items: List[Evidence],
        source_analyses: Optional[List[SourceAnalysis]] = None,
        independence_result: Optional[ClaimIndependenceResult] = None,
        comparison_result: Optional[ClaimEvidenceComparisonResult] = None,
    ) -> AIReasoningResult:
        """Synchronous wrapper for reason()."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # In active loop, run via new loop or executor
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    return executor.submit(
                        asyncio.run,
                        self.reason(
                            claim,
                            evidence_items,
                            source_analyses,
                            independence_result,
                            comparison_result,
                        ),
                    ).result()
            return loop.run_until_complete(
                self.reason(
                    claim,
                    evidence_items,
                    source_analyses,
                    independence_result,
                    comparison_result,
                )
            )
        except Exception:
            # Fallback direct execution
            packet = build_evidence_packet(
                claim=claim,
                evidence_items=evidence_items,
                source_analyses=source_analyses,
                independence_result=independence_result,
                comparison_result=comparison_result,
            )
            return generate_fallback_reasoning(packet)
