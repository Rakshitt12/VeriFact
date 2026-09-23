"""Evidence retrieval provider implementations."""

from backend.retrieval.providers.factcheck_api import GoogleFactCheckProvider
from backend.retrieval.providers.gdelt import GDELTProvider
from backend.retrieval.providers.official_search import OfficialSearchProvider
from backend.retrieval.providers.web_search import WebSearchProvider

__all__ = [
    "GDELTProvider",
    "GoogleFactCheckProvider",
    "WebSearchProvider",
    "OfficialSearchProvider",
]
