"""Tests for Part 2 - Ingestion layer."""

import pytest
import httpx
from backend.ingestion.errors import (
    ArticleExtractionFailed,
    BlockedURL,
    EmptyContent,
    FetchFailed,
    FetchTimeout,
    HTTPError,
    InvalidURL,
    SSRFViolation,
    UnsupportedContentType,
)
from backend.ingestion.models import NormalizedArticle, NormalizedText
from backend.ingestion.text_processor import normalize_text_content, process_text_input
from backend.ingestion.url_extractor import (
    extract_article_body,
    extract_article_from_url,
    extract_metadata,
    fetch_article_html,
    validate_url,
    verify_ip_security,
)
from bs4 import BeautifulSoup


# =====================================================================
# 1. Text Ingestion Tests
# =====================================================================

def test_text_normalization_normal():
    """Test standard plain text processing."""
    raw = "The government announced a 10 rupee reduction in petrol prices."
    res = normalize_text_content(raw)
    assert isinstance(res, NormalizedText)
    assert res.normalized_text == raw
    assert res.word_count == 10
    assert res.character_count == len(raw)


def test_text_normalization_whitespace_and_newlines():
    """Test handling of tabs, excessive spaces, and multiple newlines."""
    raw = "  Headline   with    extra    spaces. \t\n\n\n\nParagraph   two   with   spaces.\t\n\n "
    res = normalize_text_content(raw)
    assert "Headline with extra spaces." in res.normalized_text
    assert "Paragraph two with spaces." in res.normalized_text
    assert "\n\n\n" not in res.normalized_text
    assert not res.normalized_text.startswith(" ")
    assert not res.normalized_text.endswith(" ")


def test_text_normalization_unicode_and_invisible():
    """Test Unicode NFKC composition and invisible character removal."""
    # Includes zero-width space (\u200B) and fullwidth characters
    raw = "Breaking\u200B News\uFEFF: Ｗｏｒｌｄ　Ｂａｎｋ updates projection."
    res = normalize_text_content(raw)
    assert "\u200B" not in res.normalized_text
    assert "\uFEFF" not in res.normalized_text
    assert "World Bank updates projection." in res.normalized_text


def test_text_normalization_empty():
    """Test empty string and whitespace-only string raises EmptyContent."""
    with pytest.raises(EmptyContent):
        normalize_text_content("")

    with pytest.raises(EmptyContent):
        normalize_text_content("   \t  \n  \u200B  ")


def test_process_text_input_model():
    """Test process_text_input creates NormalizedArticle with appropriate fields."""
    raw = "Finance Minister unveiled new economic stimulus package for MSMEs."
    article = process_text_input(raw)
    assert isinstance(article, NormalizedArticle)
    assert article.source_type == "text"
    assert article.title is None
    assert article.publisher is None
    assert article.author is None
    assert article.url is None
    assert article.body == raw
    assert article.extraction_method == "direct_text"
    assert article.metadata["word_count"] == 9


# =====================================================================
# 2. URL Validation & SSRF Tests
# =====================================================================

def test_validate_url_valid_https_and_http():
    """Test valid http and https URLs."""
    url, domain = validate_url("https://www.reuters.com/world/india/article-123")
    assert url == "https://www.reuters.com/world/india/article-123"
    assert domain == "www.reuters.com"

    url, domain = validate_url("http://example.org/news")
    assert url == "http://example.org/news"
    assert domain == "example.org"


def test_validate_url_missing_or_unsupported_scheme():
    """Test missing or unsupported URL schemes raise InvalidURL."""
    with pytest.raises(InvalidURL):
        validate_url("www.reuters.com/news")

    with pytest.raises(InvalidURL):
        validate_url("ftp://files.example.com/data")

    with pytest.raises(InvalidURL):
        validate_url("javascript:alert(1)")

    with pytest.raises(InvalidURL):
        validate_url("")


def test_validate_url_malformed():
    """Test malformed URL without host raises InvalidURL."""
    with pytest.raises(InvalidURL):
        validate_url("https://")


@pytest.mark.parametrize("blocked_url", [
    "http://localhost:8080/admin",
    "http://127.0.0.1/status",
    "http://127.0.0.2:3000/",
    "http://metadata.google.internal/computeMetadata/v1/",
    "http://169.254.169.254/latest/meta-data/",
    "http://internal.service.local/api",
])
def test_ssrf_blocked_urls(blocked_url):
    """Test SSRF-sensitive and internal addresses raise SSRFViolation."""
    with pytest.raises(SSRFViolation):
        validate_url(blocked_url)


@pytest.mark.parametrize("private_ip", [
    "127.0.0.1",
    "10.0.0.1",
    "172.16.0.1",
    "172.31.255.255",
    "192.168.1.1",
    "169.254.169.254",
    "::1",
    "fc00::1",
])
def test_verify_ip_security_private_ranges(private_ip):
    """Test verify_ip_security blocks RFC1918, loopback, and link-local ranges."""
    with pytest.raises(SSRFViolation):
        verify_ip_security(private_ip)


def test_verify_ip_security_public():
    """Test public IP addresses pass security check without exception."""
    # Google DNS / Cloudflare DNS
    verify_ip_security("8.8.8.8")
    verify_ip_security("1.1.1.1")
    verify_ip_security("142.250.190.46")


# =====================================================================
# 3. HTML Metadata & Body Extraction Tests (Fixtures)
# =====================================================================

SAMPLE_NEWS_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <title>Reserve Bank Announces 25bps Rate Cut - Business Daily</title>
    <link rel="canonical" href="https://businessdaily.com/economy/rbi-rate-cut-2026">
    <meta name="author" content="Anita Sharma">
    <meta property="og:site_name" content="Business Daily">
    <meta property="og:title" content="Reserve Bank Announces 25bps Rate Cut">
    <meta property="og:description" content="Central bank eases monetary policy amid declining inflation numbers.">
    <meta property="article:published_time" content="2026-09-22T06:30:00Z">
</head>
<body>
    <header><nav><a href="/">Home</a><a href="/economy">Economy</a></nav></header>
    <div class="sidebar ads"><span>Ad banner</span></div>
    <article>
        <h1>Reserve Bank Announces 25bps Rate Cut</h1>
        <p class="intro">In a surprise move, the Monetary Policy Committee today voted unanimously to reduce the benchmark repo rate by 25 basis points.</p>
        <p>Governor Shaktikanta Das stated during the press conference that softening consumer price inflation provided adequate room for policy easing.</p>
        <p>Commercial lenders are expected to transmit the policy rate reduction to borrowers, resulting in lower equated monthly installments for retail home and vehicle loans.</p>
    </article>
    <div class="comments-section"><p>Reader comment here</p></div>
    <footer><p>&copy; 2026 Business Daily Inc.</p></footer>
</body>
</html>
"""

SAMPLE_JSON_LD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": "Government Unveils Clean Energy Transmission Project",
        "description": "Multi-billion dollar initiative to connect 50GW of renewable power generation.",
        "datePublished": "2026-09-21T14:15:00Z",
        "author": {"@type": "Person", "name": "Vikram Patel"},
        "publisher": {"@type": "Organization", "name": "Global Energy Review"},
        "articleBody": "A flagship green energy corridor connecting offshore wind plants to northern industrial centers was announced today. The project spans three coastal states and is budgeted at 12 billion dollars over four years."
    }
    </script>
</head>
<body>
    <div class="story-body">
        <p>A flagship green energy corridor connecting offshore wind plants to northern industrial centers was announced today.</p>
        <p>The project spans three coastal states and is budgeted at 12 billion dollars over four years.</p>
        <p>Cabinet clearance was granted following environmental impact assessments conducted over the past eighteen months.</p>
    </div>
</body>
</html>
"""


def test_extract_metadata_opengraph_and_html():
    """Test extraction of title, publisher, author, date, and canonical URL from standard HTML."""
    soup = BeautifulSoup(SAMPLE_NEWS_HTML, "html.parser")
    meta = extract_metadata(soup, "https://businessdaily.com/economy/rbi-rate-cut", "https://businessdaily.com/economy/rbi-rate-cut-2026")

    assert meta["title"] == "Reserve Bank Announces 25bps Rate Cut"
    assert meta["publisher"] == "Business Daily"
    assert meta["author"] == "Anita Sharma"
    assert meta["published_at"] == "2026-09-22T06:30:00Z"
    assert meta["canonical_url"] == "https://businessdaily.com/economy/rbi-rate-cut-2026"
    assert meta["domain"] == "businessdaily.com"
    assert "Central bank eases monetary policy" in meta["description"]


def test_extract_metadata_json_ld():
    """Test extraction of structured metadata from JSON-LD schema."""
    soup = BeautifulSoup(SAMPLE_JSON_LD_HTML, "html.parser")
    meta = extract_metadata(soup, "https://energyreview.com/clean-energy-grid", "https://energyreview.com/clean-energy-grid")

    assert meta["title"] == "Government Unveils Clean Energy Transmission Project"
    assert meta["publisher"] == "Global Energy Review"
    assert meta["author"] == "Vikram Patel"
    assert meta["published_at"] == "2026-09-21T14:15:00Z"
    assert "green energy corridor" in meta["json_ld"]["articleBody"]


def test_extract_article_body_semantic_tags():
    """Test extraction of main article body while stripping ads, nav, comments, and footers."""
    soup = BeautifulSoup(SAMPLE_NEWS_HTML, "html.parser")
    body, method = extract_article_body(soup)

    assert method == "semantic_article_tag"
    assert "In a surprise move, the Monetary Policy Committee" in body
    assert "lower equated monthly installments" in body
    assert "Ad banner" not in body
    assert "Reader comment here" not in body
    assert "Home" not in body


def test_extract_article_body_empty_raises_error():
    """Test HTML without substantial body raises ArticleExtractionFailed."""
    empty_html = "<html><head><title>Test</title></head><body><p>Too short</p></body></html>"
    soup = BeautifulSoup(empty_html, "html.parser")
    with pytest.raises(ArticleExtractionFailed):
        extract_article_body(soup)


# =====================================================================
# 4. Mocked HTTP Fetching Tests
# =====================================================================

def test_fetch_article_html_success():
    """Test mock HTTP 200 response fetching."""
    def mock_handler(request: httpx.Request):
        return httpx.Response(
            status_code=200,
            headers={"Content-Type": "text/html; charset=utf-8"},
            content=SAMPLE_NEWS_HTML.encode("utf-8"),
            request=request,
        )

    transport = httpx.MockTransport(mock_handler)
    with httpx.Client(transport=transport) as client:
        html, final_url = fetch_article_html("https://businessdaily.com/economy/rbi-rate-cut", client=client)
        assert "<title>Reserve Bank" in html
        assert "businessdaily.com" in final_url


def test_fetch_article_html_redirect_validation():
    """Test HTTP redirect handling and tracking."""
    def mock_handler(request: httpx.Request):
        if str(request.url) == "https://businessdaily.com/short":
            return httpx.Response(
                status_code=301,
                headers={"Location": "https://businessdaily.com/economy/rbi-rate-cut-2026"},
                request=request,
            )
        return httpx.Response(
            status_code=200,
            headers={"Content-Type": "text/html; charset=utf-8"},
            content=SAMPLE_NEWS_HTML.encode("utf-8"),
            request=request,
        )

    transport = httpx.MockTransport(mock_handler)
    with httpx.Client(transport=transport) as client:
        html, final_url = fetch_article_html("https://businessdaily.com/short", client=client)
        assert final_url == "https://businessdaily.com/economy/rbi-rate-cut-2026"
        assert "<title>Reserve Bank" in html


def test_fetch_article_html_redirect_to_ssrf_blocked():
    """Test redirect targeting localhost/SSRF is strictly intercepted and blocked."""
    def mock_handler(request: httpx.Request):
        if "evil-redirect" in str(request.url):
            return httpx.Response(
                status_code=302,
                headers={"Location": "http://169.254.169.254/latest/meta-data/"},
                request=request,
            )
        return httpx.Response(status_code=200, content=b"OK", request=request)

    transport = httpx.MockTransport(mock_handler)
    with httpx.Client(transport=transport) as client:
        with pytest.raises(SSRFViolation):
            fetch_article_html("https://news.example.com/evil-redirect", client=client)


@pytest.mark.parametrize("status_code", [404, 403, 429, 500])
def test_fetch_article_http_errors(status_code):
    """Test remote HTTP error status codes raise HTTPError."""
    def mock_handler(request: httpx.Request):
        return httpx.Response(status_code=status_code, content=b"Error", request=request)

    transport = httpx.MockTransport(mock_handler)
    with httpx.Client(transport=transport) as client:
        with pytest.raises(HTTPError) as exc_info:
            fetch_article_html("https://news.example.com/item", client=client)
        assert exc_info.value.remote_status_code == status_code


def test_fetch_article_timeout():
    """Test network timeout raises FetchTimeout."""
    def mock_handler(request: httpx.Request):
        raise httpx.ReadTimeout("Connection timed out", request=request)

    transport = httpx.MockTransport(mock_handler)
    with httpx.Client(transport=transport) as client:
        with pytest.raises(FetchTimeout):
            fetch_article_html("https://news.example.com/slow", client=client)


def test_fetch_article_unsupported_content_type():
    """Test non-HTML responses (e.g. image, PDF) raise UnsupportedContentType."""
    def mock_handler(request: httpx.Request):
        return httpx.Response(
            status_code=200,
            headers={"Content-Type": "application/pdf"},
            content=b"%PDF-1.4...",
            request=request,
        )

    transport = httpx.MockTransport(mock_handler)
    with httpx.Client(transport=transport) as client:
        with pytest.raises(UnsupportedContentType):
            fetch_article_html("https://news.example.com/document.pdf", client=client)


def test_fetch_article_oversized_response():
    """Test responses exceeding MAX_RESPONSE_BYTES are rejected."""
    oversized_bytes = b"A" * (6 * 1024 * 1024)  # 6 MB

    def mock_handler(request: httpx.Request):
        return httpx.Response(
            status_code=200,
            headers={"Content-Type": "text/html", "Content-Length": str(len(oversized_bytes))},
            content=oversized_bytes,
            request=request,
        )

    transport = httpx.MockTransport(mock_handler)
    with httpx.Client(transport=transport) as client:
        with pytest.raises(FetchFailed) as exc_info:
            fetch_article_html("https://news.example.com/massive", client=client)
        assert "exceeds" in str(exc_info.value).lower()


def test_end_to_end_extract_article_from_url():
    """Test full extract_article_from_url pipeline with mock client."""
    def mock_handler(request: httpx.Request):
        return httpx.Response(
            status_code=200,
            headers={"Content-Type": "text/html; charset=utf-8"},
            content=SAMPLE_NEWS_HTML.encode("utf-8"),
            request=request,
        )

    transport = httpx.MockTransport(mock_handler)
    with httpx.Client(transport=transport) as client:
        article = extract_article_from_url("https://businessdaily.com/economy/rbi-rate-cut", client=client)
        assert article.source_type == "url"
        assert article.title == "Reserve Bank Announces 25bps Rate Cut"
        assert article.publisher == "Business Daily"
        assert article.author == "Anita Sharma"
        assert article.domain == "businessdaily.com"
        assert len(article.body) > 100
        assert article.metadata["word_count"] > 20
