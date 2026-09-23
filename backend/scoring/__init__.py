"""Credibility Scoring Engine package."""

from backend.scoring.component_calculator import ComponentCalculator
from backend.scoring.credibility_score import (
    CredibilityScoreCalculator,
    classify_credibility_score,
)
from backend.scoring.models import (
    ClaimCredibilityScore,
    DocumentCredibilityScore,
    ScoreComponent,
    ScoreFactor,
    ScorePenalty,
)
from backend.scoring.penalties import PenaltyCalculator
from backend.scoring.score_explanation import ScoreExplainer
from backend.scoring.service import CredibilityScoringService

__all__ = [
    "ComponentCalculator",
    "PenaltyCalculator",
    "ScoreExplainer",
    "CredibilityScoreCalculator",
    "CredibilityScoringService",
    "classify_credibility_score",
    "ClaimCredibilityScore",
    "DocumentCredibilityScore",
    "ScoreComponent",
    "ScorePenalty",
    "ScoreFactor",
]
