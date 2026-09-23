"""AI Evidence Reasoning package exports."""

from backend.ai.evidence_reasoner import EvidenceReasoner
from backend.ai.fallback_reasoner import generate_fallback_reasoning
from backend.ai.grounding_validator import validate_and_sanitize_reasoning
from backend.ai.llm_client import (
    GeminiLLMClient,
    LLMClient,
    LLMError,
    LLMParsingError,
    LLMTimeoutError,
    LLMUnavailableError,
    MockLLMClient,
    OpenAILLMClient,
    get_llm_client,
)
from backend.ai.models import (
    AIReasoningResult,
    EvidenceFinding,
    EvidencePacket,
    EvidencePacketItem,
    FindingImportance,
    UncertaintyLevel,
)
from backend.ai.packet_builder import build_evidence_packet
from backend.ai.service import (
    AIReasoningService,
    reason_about_claim_evidence,
    reason_about_claim_evidence_sync,
)

__all__ = [
    "FindingImportance",
    "UncertaintyLevel",
    "EvidenceFinding",
    "AIReasoningResult",
    "EvidencePacketItem",
    "EvidencePacket",
    "build_evidence_packet",
    "validate_and_sanitize_reasoning",
    "generate_fallback_reasoning",
    "LLMClient",
    "GeminiLLMClient",
    "OpenAILLMClient",
    "MockLLMClient",
    "get_llm_client",
    "LLMError",
    "LLMUnavailableError",
    "LLMTimeoutError",
    "LLMParsingError",
    "EvidenceReasoner",
    "AIReasoningService",
    "reason_about_claim_evidence",
    "reason_about_claim_evidence_sync",
]
