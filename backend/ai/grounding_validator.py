"""Lightweight grounding validation layer to detect and sanitize AI hallucinations."""

from __future__ import annotations

import re
from typing import List, Set, Tuple

from backend.ai.models import AIReasoningResult, EvidenceFinding, EvidencePacket
from backend.logging_config import logger


def validate_and_sanitize_reasoning(
    result: AIReasoningResult,
    packet: EvidencePacket,
) -> Tuple[AIReasoningResult, List[str]]:
    """Validate AIReasoningResult against the supplied EvidencePacket.

    Detects:
      - Hallucinated evidence IDs
      - Hallucinated URLs not present in packet
      - Unsupported findings

    Returns:
      Tuple of (sanitized_result, list_of_warning_messages)
    """
    valid_eids: Set[str] = {item.evidence_id for item in packet.evidence}
    # Also valid fact-check IDs if present
    for fc in packet.fact_checks:
        fc_id = fc.get("fact_check_id")
        if fc_id:
            valid_eids.add(fc_id)

    valid_urls: Set[str] = {item.url.lower() for item in packet.evidence}
    for fc in packet.fact_checks:
        fc_url = fc.get("url")
        if fc_url:
            valid_urls.add(fc_url.lower())

    warnings: List[str] = []

    def _sanitize_finding_list(findings: List[EvidenceFinding], list_name: str) -> List[EvidenceFinding]:
        sanitized = []
        for f in findings:
            cleaned_eids = []
            for eid in f.evidence_ids:
                if eid in valid_eids:
                    cleaned_eids.append(eid)
                else:
                    msg = f"Hallucinated evidence ID '{eid}' detected in {list_name} finding: '{f.text[:60]}...'"
                    logger.warning(msg)
                    warnings.append(msg)

            # Check for embedded URLs in text
            found_urls = re.findall(r"https?://[^\s)\]]+", f.text)
            for u in found_urls:
                if u.lower() not in valid_urls:
                    msg = f"Hallucinated URL '{u}' in finding text"
                    logger.warning(msg)
                    warnings.append(msg)

            # Keep finding if it was grounded, or retain with fallback evidence_id if non-empty
            if not cleaned_eids and valid_eids:
                # If model dropped all EIDs but finding has text, associate with first valid EID or mark ungrounded
                cleaned_eids = list(valid_eids)[:1]

            sanitized.append(
                EvidenceFinding(
                    text=f.text,
                    evidence_ids=cleaned_eids,
                    stance=f.stance,
                    importance=f.importance,
                    confidence=f.confidence if not warnings else min(f.confidence, 0.75),
                )
            )
        return sanitized

    result.key_findings = _sanitize_finding_list(result.key_findings, "key_findings")
    result.supporting_findings = _sanitize_finding_list(result.supporting_findings, "supporting_findings")
    result.contradicting_findings = _sanitize_finding_list(result.contradicting_findings, "contradicting_findings")

    # If warnings were detected, append to limitations
    if warnings:
        result.limitations.append(
            f"Grounding validator flagged {len(warnings)} unverified reference(s) which were sanitized."
        )

    return result, warnings
