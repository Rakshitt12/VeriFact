"""Provider-agnostic LLM client abstraction for structured reasoning generation."""

from __future__ import annotations

import abc
import json
import re
from typing import Any, Dict, Optional, Type, TypeVar
import httpx
from pydantic import BaseModel

from backend.config.settings import settings
from backend.logging_config import logger

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """Base exception for LLM operations."""
    def __init__(self, message: str, provider: str = "unknown") -> None:
        super().__init__(f"[{provider}] {message}")
        self.message = message
        self.provider = provider


class LLMUnavailableError(LLMError):
    """Raised when LLM provider is disabled, unconfigured, or key missing."""
    pass


class LLMTimeoutError(LLMError):
    """Raised when LLM request times out."""
    pass


class LLMParsingError(LLMError):
    """Raised when LLM output cannot be parsed into the expected Pydantic model."""
    pass


def _extract_json_block(text: str) -> str:
    """Extract json from markdown code fences if present."""
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        return match.group(1).strip()
    return text.strip()


class LLMClient(abc.ABC):
    """Abstract interface for provider-agnostic structured LLM interactions."""

    @property
    @abc.abstractmethod
    def provider_name(self) -> str:
        """Name of the provider (e.g. gemini, openai, mock)."""
        pass

    @abc.abstractmethod
    async def generate_structured(
        self,
        system_instruction: str,
        user_prompt: str,
        response_model: Type[T],
    ) -> T:
        """Send prompt to LLM and parse the response into response_model."""
        pass


class GeminiLLMClient(LLMClient):
    """Google Gemini API client using standard HTTP JSON endpoints."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self.api_key = api_key or settings.GOOGLE_API_KEY
        self.model = model or settings.LLM_MODEL
        self.timeout = timeout or settings.LLM_TIMEOUT_SECONDS
        self._client = client

    @property
    def provider_name(self) -> str:
        return "gemini"

    async def generate_structured(
        self,
        system_instruction: str,
        user_prompt: str,
        response_model: Type[T],
    ) -> T:
        if not self.api_key:
            raise LLMUnavailableError("GOOGLE_API_KEY is not configured", self.provider_name)

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "system_instruction": {"parts": [{"text": system_instruction}]},
            "contents": [{"parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "temperature": settings.LLM_TEMPERATURE,
                "maxOutputTokens": settings.LLM_MAX_OUTPUT_TOKENS,
                "responseMimeType": "application/json",
            },
        }

        try:
            if self._client:
                resp = await self._client.post(url, json=payload, timeout=self.timeout)
            else:
                async with httpx.AsyncClient() as client:
                    resp = await client.post(url, json=payload, timeout=self.timeout)

            if resp.status_code in (401, 403):
                raise LLMUnavailableError(f"Authentication failed (HTTP {resp.status_code})", self.provider_name)
            if resp.status_code != 200:
                raise LLMError(f"API returned HTTP {resp.status_code}: {resp.text[:200]}", self.provider_name)

            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise LLMError("No candidates returned from Gemini", self.provider_name)

            content_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            raw_json = _extract_json_block(content_text)
            parsed_dict = json.loads(raw_json)
            return response_model.model_validate(parsed_dict)

        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(f"Request timed out after {self.timeout}s: {exc}", self.provider_name) from exc
        except (json.JSONDecodeError, ValueError) as exc:
            raise LLMParsingError(f"Failed to parse model response into JSON: {exc}", self.provider_name) from exc
        except Exception as exc:
            if isinstance(exc, LLMError):
                raise
            raise LLMError(f"Unexpected error: {exc}", self.provider_name) from exc


class OpenAILLMClient(LLMClient):
    """OpenAI API client supporting JSON object mode."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        timeout: Optional[int] = None,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = model
        self.timeout = timeout or settings.LLM_TIMEOUT_SECONDS
        self._client = client

    @property
    def provider_name(self) -> str:
        return "openai"

    async def generate_structured(
        self,
        system_instruction: str,
        user_prompt: str,
        response_model: Type[T],
    ) -> T:
        if not self.api_key:
            raise LLMUnavailableError("OPENAI_API_KEY is not configured", self.provider_name)

        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": settings.LLM_TEMPERATURE,
            "max_tokens": settings.LLM_MAX_OUTPUT_TOKENS,
        }

        try:
            if self._client:
                resp = await self._client.post(url, headers=headers, json=payload, timeout=self.timeout)
            else:
                async with httpx.AsyncClient() as client:
                    resp = await client.post(url, headers=headers, json=payload, timeout=self.timeout)

            if resp.status_code in (401, 403):
                raise LLMUnavailableError(f"Authentication failed (HTTP {resp.status_code})", self.provider_name)
            if resp.status_code != 200:
                raise LLMError(f"API returned HTTP {resp.status_code}: {resp.text[:200]}", self.provider_name)

            data = resp.json()
            content_text = data["choices"][0]["message"]["content"]
            raw_json = _extract_json_block(content_text)
            parsed_dict = json.loads(raw_json)
            return response_model.model_validate(parsed_dict)

        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(f"Request timed out: {exc}", self.provider_name) from exc
        except Exception as exc:
            if isinstance(exc, LLMError):
                raise
            raise LLMError(f"OpenAI call failed: {exc}", self.provider_name) from exc


class MockLLMClient(LLMClient):
    """Deterministic mock client for testing without external networks."""

    def __init__(
        self,
        response_instance: Optional[BaseModel | Dict[str, Any]] = None,
        response_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.response_instance = response_instance or response_data

    @property
    def provider_name(self) -> str:
        return "mock"

    async def generate_structured(
        self,
        system_instruction: str,
        user_prompt: str,
        response_model: Type[T],
    ) -> T:
        if self.response_instance is not None:
            if isinstance(self.response_instance, response_model):
                return self.response_instance
            if isinstance(self.response_instance, BaseModel):
                return response_model.model_validate(self.response_instance.model_dump())
            if isinstance(self.response_instance, dict):
                return response_model.model_validate(self.response_instance)

        default_dict = {
            "summary": "Mock grounded reasoning summary based on evidence.",
            "key_findings": [],
            "supporting_findings": [],
            "contradicting_findings": [],
            "important_discrepancies": [],
            "source_observations": ["Mock source observation."],
            "independence_observations": ["Mock independence observation."],
            "fact_check_observations": [],
            "verification_gaps": [],
            "uncertainty": "MEDIUM",
            "reasoning_steps": ["Mock step 1"],
            "limitations": [],
            "ai_used": True,
            "provider": "mock",
            "model": "mock-model",
            "fallback_used": False,
        }
        return response_model.model_validate(default_dict)


def get_llm_client(provider: Optional[str] = None) -> LLMClient:
    """Factory creating an LLMClient instance based on configuration."""
    selected = (provider or settings.LLM_PROVIDER).lower()
    if selected == "gemini":
        return GeminiLLMClient()
    if selected in ("openai", "gpt"):
        return OpenAILLMClient()
    if selected == "mock":
        return MockLLMClient()
    logger.warning("Unknown LLM_PROVIDER '%s'. Defaulting to Gemini", selected)
    return GeminiLLMClient()
