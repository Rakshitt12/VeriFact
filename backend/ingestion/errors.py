"""Ingestion error hierarchy for robust, safe error handling."""


class IngestionError(Exception):
    """Base class for all ingestion errors."""

    def __init__(self, message: str, error_code: str = "INGESTION_ERROR", status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code


class InvalidURL(IngestionError):
    """Raised when a URL is malformed or lacks an accepted HTTP/HTTPS scheme."""

    def __init__(self, message: str = "Invalid URL format or unsupported scheme."):
        super().__init__(message=message, error_code="INVALID_URL", status_code=400)


class SSRFViolation(IngestionError):
    """Raised when a URL targets localhost, private networks, or metadata endpoints."""

    def __init__(self, message: str = "Target URL resolves to a restricted or private address."):
        super().__init__(message=message, error_code="SSRF_VIOLATION", status_code=403)


class BlockedURL(IngestionError):
    """Raised when a target host or URL pattern is administratively blocked."""

    def __init__(self, message: str = "Target URL is blocked by security policy."):
        super().__init__(message=message, error_code="BLOCKED_URL", status_code=403)


class FetchTimeout(IngestionError):
    """Raised when fetching an article URL times out."""

    def __init__(self, message: str = "Timed out while fetching article from remote server."):
        super().__init__(message=message, error_code="FETCH_TIMEOUT", status_code=504)


class FetchFailed(IngestionError):
    """Raised when an HTTP or network connection error occurs."""

    def __init__(self, message: str = "Failed to establish connection to the remote article host."):
        super().__init__(message=message, error_code="FETCH_FAILED", status_code=502)


class HTTPError(IngestionError):
    """Raised when a remote server returns an HTTP 4xx or 5xx status code."""

    def __init__(self, status_code: int, message: str | None = None):
        msg = message or f"Remote server responded with HTTP status {status_code}."
        super().__init__(message=msg, error_code=f"HTTP_{status_code}", status_code=502)
        self.remote_status_code = status_code


class UnsupportedContentType(IngestionError):
    """Raised when the fetched resource is not HTML (e.g. image, PDF, audio)."""

    def __init__(self, message: str = "The requested URL did not return an HTML document."):
        super().__init__(message=message, error_code="UNSUPPORTED_CONTENT_TYPE", status_code=415)


class EmptyContent(IngestionError):
    """Raised when the input text or fetched article contains no readable text."""

    def __init__(self, message: str = "Provided or extracted content is empty or contains only whitespace."):
        super().__init__(message=message, error_code="EMPTY_CONTENT", status_code=422)


class ArticleExtractionFailed(IngestionError):
    """Raised when an HTML document could not yield meaningful article content."""

    def __init__(self, message: str = "Unable to extract meaningful article content or body from page."):
        super().__init__(message=message, error_code="ARTICLE_EXTRACTION_FAILED", status_code=422)
