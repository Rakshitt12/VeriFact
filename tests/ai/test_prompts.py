"""Unit tests for AI prompt construction and constraints."""

from backend.ai.packet_builder import build_evidence_packet
from backend.ai.prompts import SYSTEM_INSTRUCTION, build_reasoning_prompt
from backend.claim.models import Claim, ClaimImportance, ClaimType
from backend.retrieval.models import Evidence, SourceType


def test_system_prompt_critical_constraints():
    assert "EVIDENCE FIRST, AI REASONING SECOND" in SYSTEM_INSTRUCTION
    assert "NEVER invent facts" in SYSTEM_INSTRUCTION
    assert "DO NOT produce a final credibility score" in SYSTEM_INSTRUCTION
    assert "JSON" in SYSTEM_INSTRUCTION


def test_user_reasoning_prompt_structure():
    claim = Claim(
        claim_id="c_test",
        original_text="Solar capacity doubled in 2023.",
        normalized_text="Solar capacity doubled in 2023.",
        claim_text="Solar capacity doubled in 2023.",
        source_sentence="Solar capacity doubled in 2023.",
        claim_type=ClaimType.STATISTIC,
        importance=ClaimImportance.HIGH,
        confidence=0.88,
    )
    ev = Evidence(
        evidence_id="ev_01",
        claim_id="c_test",
        title="Solar Report 2023",
        url="https://iea.org/solar",
        publisher="IEA",
        domain="iea.org",
        snippet="Global solar installations expanded significantly.",
        source_type=SourceType.ACADEMIC,
        provider="tavily",
        query_used="solar capacity 2023",
    )

    packet = build_evidence_packet(claim=claim, evidence_items=[ev])

    sys_prompt, user_prompt = build_reasoning_prompt(packet)
    assert sys_prompt == SYSTEM_INSTRUCTION
    assert "EVIDENCE PACKET FOR ANALYSIS" in user_prompt
    assert "Solar capacity doubled in 2023." in user_prompt
    assert "ev_01" in user_prompt
    assert "iea.org" in user_prompt
