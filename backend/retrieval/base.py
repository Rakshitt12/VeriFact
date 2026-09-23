"""Abstract base class for all evidence retrieval providers.

Every concrete provider must subclass EvidenceProvider and implement
the `search` coroutine.  The service layer calls providers uniformly
and handles failures through the common exception hierarchy.
"""

from __future__ import annotations

import abc
import time
from typing import List

from backend.retrieval.models import Evidence, ProviderStatus, ProviderStatusCode
from backend.logging_config import logger


class ProviderError(Exception):
    """Raised by a provider to signal a retrieval failure (non-crash)."""

    def __init__(self, message: str, provider: str) -> None:
        super().__init__(message)
        self.provider = provider


class ProviderUnavailable(ProviderError):
    """Raised when a provider is not configured (e.g. missing API key)."""


class ProviderTimeout(ProviderError):
    """Raised when a provider call exceeds the configured timeout."""


class EvidenceProvider(abc.ABC):
    """Common interface for all evidence retrieval providers.

    Subclasses must implement:
        - provider_name (property)
        - search(query, limit) -> list[Evidence]
    """

    @property
    @abc.abstractmethod
    def provider_name(self) -> str:
        """Short identifier for this provider (e.g. 'gdelt', 'tavily')."""

    @abc.abstractmethod
    async def search(self, query: str, limit: int = 10) -> List[Evidence]:
        """Search for evidence relevant to *query*.

        Args:
            query: The search query string.
            limit: Maximum number of results to return.

        Returns:
            A list of normalised Evidence objects.

        Raises:
            ProviderUnavailable: If the provider cannot be contacted (no key, disabled).
            ProviderTimeout:     If the request times out.
            ProviderError:       For any other retrieval failure.
        """

    async def safe_search(
        self,
        query: str,
        limit: int = 10,
    ) -> tuple[List[Evidence], ProviderStatus]:
        """Wrap `search` with timing and structured error handling.

        Always returns a (results, status) tuple — never raises.
        """
        t0 = time.perf_counter()
        try:
            results = await self.search(query, limit)
            duration_ms = (time.perf_counter() - t0) * 1000
            status = ProviderStatus(
                provider=self.provider_name,
                status=ProviderStatusCode.SUCCESS,
                results_count=len(results),
                duration_ms=round(duration_ms, 1),
            )
            logger.debug(
                "Provider %s returned %d result(s) in %.0fms for query: %.80s",
                self.provider_name,
                len(results),
                duration_ms,
                query,
            )
            return results, status

        except ProviderUnavailable as exc:
            duration_ms = (time.perf_counter() - t0) * 1000
            logger.info("Provider %s unavailable: %s", self.provider_name, exc)
            return [], ProviderStatus(
                provider=self.provider_name,
                status=ProviderStatusCode.UNAVAILABLE,
                results_count=0,
                error=str(exc),
                duration_ms=round(duration_ms, 1),
            )

        except ProviderTimeout as exc:
            duration_ms = (time.perf_counter() - t0) * 1000
            logger.warning("Provider %s timed out: %s", self.provider_name, exc)
            return [], ProviderStatus(
                provider=self.provider_name,
                status=ProviderStatusCode.TIMEOUT,
                results_count=0,
                error=str(exc),
                duration_ms=round(duration_ms, 1),
            )

        except ProviderError as exc:
            duration_ms = (time.perf_counter() - t0) * 1000
            logger.error("Provider %s error: %s", self.provider_name, exc)
            return [], ProviderStatus(
                provider=self.provider_name,
                status=ProviderStatusCode.ERROR,
                results_count=0,
                error=str(exc),
                duration_ms=round(duration_ms, 1),
            )

        except Exception as exc:  # noqa: BLE001
            duration_ms = (time.perf_counter() - t0) * 1000
            logger.exception("Unexpected error in provider %s: %s", self.provider_name, exc)
            return [], ProviderStatus(
                provider=self.provider_name,
                status=ProviderStatusCode.ERROR,
                results_count=0,
                error="Unexpected error during retrieval",
                duration_ms=round(duration_ms, 1),
            )
