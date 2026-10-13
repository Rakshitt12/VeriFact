"""Secure URL validation, SSRF protection, HTTP fetching, and HTML article extraction.

Protects against SSRF, internal redirects, oversized payloads, and unverified HTML.
Extracts title, publisher, author, date, body, canonical URL, and metadata using semantic HTML,
OpenGraph, Twitter Cards, and JSON-LD structured data.
"""

import ipaddress
import json
import re
import socket
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup, Comment

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
from backend.ingestion.models import NormalizedArticle
from backend.logging_config import logger

# Configuration constants
MAX_RESPONSE_BYTES = 5 * 1024 * 1024  # 5 MB maximum response size
DEFAULT_TIMEOUT_SECONDS = 15.0
MAX_REDIRECTS = 5

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

REQUEST_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "cross-site",
    "Sec-Fetch-User": "?1",
    "Referer": "https://www.google.com/",
}

# Blocked hostnames or domains
BLOCKED_HOSTNAMES: Set[str] = {
    "localhost",
    "localhost.localdomain",
    "metadata.google.internal",
    "169.254.169.254",  # AWS/GCP/Azure link-local metadata
    "instance-data",
    "metadata",
}

# Tags to completely remove from article body candidate trees
JUNK_TAGS = [
    "script",
    "style",
    "noscript",
    "iframe",
    "nav",
    "footer",
    "header",
    "aside",
    "form",
    "button",
    "svg",
    "canvas",
    "audio",
    "video",
    "menu",
]

# Class or ID keywords typical of non-article chrome/ads
JUNK_CLASS_ID_KEYWORDS = [
    "comment",
    "advert",
    "sponsored",
    "cookie",
    "newsletter",
    "subscribe",
    "sidebar",
    "related-posts",
    "social-share",
    "share-buttons",
    "disclaimer",
    "breadcrumb",
    "modal",
    "popup",
    "banner",
]


# =====================================================================
# 1. URL Validation & SSRF Prevention
# =====================================================================

def validate_url(url: str) -> Tuple[str, str]:
    """Validate URL syntax, scheme, and domain.

    Returns:
        (sanitized_url, domain)

    Raises:
        InvalidURL: If URL is empty, malformed, or has an unsupported scheme.
        BlockedURL: If hostname matches blocked internal targets.
    """
    if not url or not url.strip():
        raise InvalidURL("URL cannot be empty.")

    cleaned_url = url.strip()
    try:
        parsed = urlparse(cleaned_url)
    except Exception as exc:
        raise InvalidURL(f"Malformed URL: {exc}")

    # Enforce HTTP / HTTPS scheme only
    if parsed.scheme.lower() not in ("http", "https"):
        raise InvalidURL(f"Unsupported scheme '{parsed.scheme}'. Only HTTP and HTTPS are permitted.")

    hostname = parsed.hostname
    if not hostname:
        raise InvalidURL("URL missing valid host name or domain.")

    hostname_lower = hostname.lower()

    # Immediate check if hostname is an IP address
    try:
        ip = ipaddress.ip_address(hostname_lower)
        verify_ip_security(str(ip))
    except ValueError:
        pass

    if hostname_lower in BLOCKED_HOSTNAMES:
        raise SSRFViolation(f"Target host '{hostname}' is a restricted address.")

    if hostname_lower.endswith(".local") or hostname_lower.endswith(".internal"):
        raise SSRFViolation(f"Local or internal domain '{hostname}' is not permitted.")

    return cleaned_url, hostname_lower



def verify_ip_security(ip_str: str) -> None:
    """Verify that an IP address is public and does not point to private/loopback/cloud networks."""
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        raise SSRFViolation(f"Invalid IP address resolved: '{ip_str}'")

    if (
        ip.is_loopback  # 127.0.0.0/8, ::1
        or ip.is_private  # 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, fc00::/7
        or ip.is_link_local  # 169.254.0.0/16, fe80::/10
        or ip.is_multicast  # 224.0.0.0/4
        or ip.is_reserved  # 240.0.0.0/4
        or ip.is_unspecified  # 0.0.0.0, ::
    ):
        raise SSRFViolation(f"Resolved IP address '{ip}' is in a reserved or private network range.")


def resolve_and_verify_host(hostname: str) -> str:
    """Resolve hostname to IP address and verify it is not a private or loopback IP.

    Returns:
        The verified IP address.
    """
    # If hostname is already a raw IP
    try:
        ipaddress.ip_address(hostname)
        verify_ip_security(hostname)
        return hostname
    except ValueError:
        pass

    try:
        # Resolve via DNS
        addr_info = socket.getaddrinfo(hostname, None, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM)
        if not addr_info:
            raise FetchFailed(f"DNS resolution returned no records for host '{hostname}'.")

        # Check all resolved IPs
        verified_ip = None
        for item in addr_info:
            ip = item[4][0]
            verify_ip_security(ip)
            if not verified_ip:
                verified_ip = ip

        return verified_ip
    except socket.gaierror as exc:
        raise FetchFailed(f"DNS lookup failed for host '{hostname}': {exc}")
    except SSRFViolation:
        raise
    except Exception as exc:
        raise FetchFailed(f"Failed to resolve host '{hostname}': {exc}")


# =====================================================================
# 2. Secure HTTP Fetching
# =====================================================================

def fetch_article_html(
    url: str,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    client: Optional[httpx.Client] = None,
) -> Tuple[str, str]:
    """Fetch article HTML with strict redirect tracking, size limits, and SSRF verification.

    Returns:
        (html_content, final_url)
    """
    current_url, host = validate_url(url)
    if client is None:
        resolve_and_verify_host(host)

    redirects_followed = 0

    # Custom redirect loop to re-verify every redirect hop against SSRF
    owns_client = client is None
    http_client = client or httpx.Client(
        headers=REQUEST_HEADERS,
        timeout=httpx.Timeout(timeout),
        follow_redirects=False,
    )

    try:
        while True:
            try:
                response = http_client.get(current_url)
            except httpx.TimeoutException:
                raise FetchTimeout(f"Timed out fetching '{current_url}'.")
            except httpx.RequestError as exc:
                raise FetchFailed(f"Connection failed for '{current_url}': {exc}")

            # Check for redirect (301, 302, 303, 307, 308)
            if response.is_redirect:
                redirect_target = response.headers.get("Location")
                if not redirect_target:
                    raise HTTPError(response.status_code, "Redirect response missing Location header.")

                redirects_followed += 1
                if redirects_followed > MAX_REDIRECTS:
                    raise FetchFailed(f"Exceeded maximum redirect limit of {MAX_REDIRECTS}.")

                # Resolve relative redirects
                next_url = urljoin(current_url, redirect_target)
                next_url, next_host = validate_url(next_url)
                # Verify security of the new target
                if client is None:
                    resolve_and_verify_host(next_host)
                current_url = next_url
                continue


            # Check HTTP Status
            if response.status_code >= 400:
                raise HTTPError(response.status_code)

            # Check content length
            content_length = response.headers.get("content-length")
            if content_length and int(content_length) > MAX_RESPONSE_BYTES:
                raise FetchFailed(f"Remote document size exceeds maximum allowed size ({MAX_RESPONSE_BYTES} bytes).")

            # Check Content-Type
            content_type = response.headers.get("content-type", "").lower()
            if content_type and ("text/html" not in content_type and "application/xhtml" not in content_type):
                raise UnsupportedContentType(
                    f"Unsupported content type '{content_type}'. Expected HTML document."
                )

            # Check actual downloaded byte size
            content_bytes = response.content
            if len(content_bytes) > MAX_RESPONSE_BYTES:
                raise FetchFailed(f"Downloaded content exceeds {MAX_RESPONSE_BYTES} bytes.")

            if not content_bytes or not content_bytes.strip():
                raise EmptyContent(f"The webpage at '{current_url}' returned an empty response.")

            # Decode text
            text = response.text
            return text, str(response.url)
    finally:
        if owns_client:
            http_client.close()


# =====================================================================
# 3. HTML Article Extraction
# =====================================================================

def _extract_json_ld(soup: BeautifulSoup) -> Dict[str, Any]:
    """Extract metadata from JSON-LD scripts."""
    results: Dict[str, Any] = {}
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            content = script.string
            if not content:
                continue
            data = json.loads(content)
            # JSON-LD can be a dict, a list, or have @graph
            items = []
            if isinstance(data, list):
                items.extend(data)
            elif isinstance(data, dict):
                if "@graph" in data and isinstance(data["@graph"], list):
                    items.extend(data["@graph"])
                else:
                    items.append(data)

            for item in items:
                if not isinstance(item, dict):
                    continue
                type_val = item.get("@type", "")
                types = [type_val] if isinstance(type_val, str) else type_val
                if any("article" in str(t).lower() or "news" in str(t).lower() for t in types):
                    if "headline" in item and not results.get("headline"):
                        results["headline"] = item["headline"]
                    if "author" in item and not results.get("author"):
                        author_val = item["author"]
                        if isinstance(author_val, list) and author_val:
                            results["author"] = author_val[0].get("name") if isinstance(author_val[0], dict) else str(author_val[0])
                        elif isinstance(author_val, dict):
                            results["author"] = author_val.get("name")
                        elif isinstance(author_val, str):
                            results["author"] = author_val
                    if "publisher" in item and not results.get("publisher"):
                        pub_val = item["publisher"]
                        if isinstance(pub_val, dict):
                            results["publisher"] = pub_val.get("name")
                        elif isinstance(pub_val, str):
                            results["publisher"] = pub_val
                    if "datePublished" in item and not results.get("datePublished"):
                        results["datePublished"] = item["datePublished"]
                    if "description" in item and not results.get("description"):
                        results["description"] = item["description"]
                    if "articleBody" in item and not results.get("articleBody"):
                        results["articleBody"] = item["articleBody"]
        except Exception:
            continue
    return results


def _extract_meta_content(soup: BeautifulSoup, properties: List[str]) -> Optional[str]:
    """Find content for meta tags matching name or property attributes."""
    for prop in properties:
        tag = soup.find("meta", attrs={"property": prop}) or soup.find("meta", attrs={"name": prop})
        if tag and tag.get("content"):
            content = tag["content"].strip()
            if content:
                return content
    return None


def extract_metadata(soup: BeautifulSoup, original_url: str, final_url: str) -> Dict[str, Any]:
    """Extract metadata: title, publisher, author, date, domain, canonical_url, description."""
    parsed = urlparse(final_url or original_url)
    domain = parsed.hostname.lower() if parsed.hostname else None
    if domain and domain.startswith("www."):
        domain = domain[4:]

    # 1. JSON-LD structured data (highest fidelity)
    json_ld = _extract_json_ld(soup)

    # 2. Canonical URL
    canonical_tag = soup.find("link", rel=lambda r: r and "canonical" in r.lower())
    canonical_url = canonical_tag.get("href") if canonical_tag else None
    if canonical_url:
        canonical_url = urljoin(final_url, canonical_url)

    # 3. Title extraction
    title = (
        json_ld.get("headline")
        or _extract_meta_content(soup, ["og:title", "twitter:title"])
        or (soup.find("h1").get_text(strip=True) if soup.find("h1") else None)
        or (soup.title.get_text(strip=True) if soup.title else None)
    )
    # Clean trailing title decorations (e.g. "Headline - Reuters")
    if title and " - " in title and domain:
        parts = title.split(" - ")
        if len(parts) > 1 and domain.split(".")[0].lower() in parts[-1].lower():
            title = " - ".join(parts[:-1]).strip()

    # 4. Publisher extraction
    publisher = (
        json_ld.get("publisher")
        or _extract_meta_content(soup, ["og:site_name", "publisher", "twitter:site"])
    )
    if not publisher and domain:
        # Fallback to domain name root capitalized
        publisher = domain.split(".")[0].capitalize()

    # 5. Author extraction
    author = (
        json_ld.get("author")
        or _extract_meta_content(soup, ["author", "article:author", "twitter:creator", "byl"])
    )

    # 6. Published Date
    published_at = (
        json_ld.get("datePublished")
        or _extract_meta_content(
            soup,
            [
                "article:published_time",
                "datePublished",
                "publishdate",
                "pubdate",
                "timestamp",
                "dc.date",
            ],
        )
    )

    # 7. Description
    description = (
        json_ld.get("description")
        or _extract_meta_content(soup, ["og:description", "description", "twitter:description"])
    )

    return {
        "title": title,
        "publisher": publisher,
        "author": author,
        "published_at": published_at,
        "domain": domain,
        "canonical_url": canonical_url,
        "description": description,
        "json_ld": json_ld,
    }


def extract_article_body(soup: BeautifulSoup, json_ld_body: Optional[str] = None) -> Tuple[str, str]:
    """Extract the main textual body of an article.

    Attempts:
    1. Cleaned <article> container paragraphs
    2. Primary container with class/id containing 'article', 'story', 'post', 'entry-content'
    3. JSON-LD articleBody if present and sufficient
    4. Aggregated top paragraph blocks from <body>

    Returns:
        (extracted_text, method_name)
    """
    # Clone soup to safely clean DOM
    dom = BeautifulSoup(str(soup), "html.parser")

    # Remove comments
    for comment in dom.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()


    # Remove non-content junk tags
    for tag_name in JUNK_TAGS:
        for tag in dom.find_all(tag_name):
            tag.decompose()

    # Remove elements matching junk class/id heuristics
    for elem in dom.find_all(attrs={"class": True}):
        class_str = " ".join(elem.get("class", [])).lower()
        if any(junk in class_str for junk in JUNK_CLASS_ID_KEYWORDS):
            elem.decompose()

    for elem in dom.find_all(attrs={"id": True}):
        id_str = elem.get("id", "").lower()
        if any(junk in id_str for junk in JUNK_CLASS_ID_KEYWORDS):
            elem.decompose()

    # Strategy 1: <article> tag
    article_tag = dom.find("article")
    if article_tag:
        paras = [p.get_text(strip=True) for p in article_tag.find_all(["p", "h2", "h3"]) if len(p.get_text(strip=True)) > 20]
        if paras and sum(len(p) for p in paras) > 100:
            return "\n\n".join(paras), "semantic_article_tag"

    # Strategy 2: Common article containers
    container_selectors = [
        "div[class*='article-body']",
        "div[class*='story-body']",
        "div[class*='post-content']",
        "div[class*='entry-content']",
        "section[class*='article']",
        "div[id*='article-body']",
        "main",
    ]
    for sel in container_selectors:
        container = dom.select_one(sel)
        if container:
            paras = [p.get_text(strip=True) for p in container.find_all(["p", "h2", "h3"]) if len(p.get_text(strip=True)) > 20]
            if paras and sum(len(p) for p in paras) > 100:
                return "\n\n".join(paras), f"container_selector({sel})"

    # Strategy 3: JSON-LD articleBody
    if json_ld_body and len(json_ld_body.strip()) > 100:
        return json_ld_body.strip(), "json_ld_article_body"

    # Strategy 4: Fallback to all substantial paragraphs across the document body
    all_paras = [p.get_text(strip=True) for p in dom.find_all("p") if len(p.get_text(strip=True)) > 30]
    if all_paras and sum(len(p) for p in all_paras) > 100:
        return "\n\n".join(all_paras), "body_paragraph_aggregation"

    raise ArticleExtractionFailed("Could not extract readable article text from HTML document.")


def _clean_reader_markdown(md_text: str) -> str:
    """Strip unnecessary markdown formatting, images, and noise lines from reader output."""
    # Remove image markdown [![...](...)](...)
    text = re.sub(r"\[!\[.*?\]\(.*?\)\]\(.*?\)", "", md_text)
    # Remove standalone images ![...](...)
    text = re.sub(r"!\[.*?\]\(.*?\)", "", md_text)
    # Remove markdown link formatting [text](url) -> text
    text = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", text)
    # Collapse multiple blank lines
    lines = [line.strip() for line in text.splitlines()]
    clean_lines = []
    for line in lines:
        if line:
            clean_lines.append(line)
        elif clean_lines and clean_lines[-1] != "":
            clean_lines.append("")
    return "\n\n".join(clean_lines)


def extract_article_via_reader(
    url: str,
    domain: str,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> Optional[NormalizedArticle]:
    """Fallback article extraction using the public Jina Reader proxy.

    Used when direct HTTP GET is blocked by CDN/WAF anti-bot measures (HTTP 403/401/429/503)
    or returns an unparseable response on datacenter/cloud IPs.
    """
    reader_url = f"https://r.jina.ai/{url}"
    headers = {
        "Accept": "application/json",
        "X-Target-Selector": "article",
        "X-Timeout": str(int(timeout)),
    }
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(reader_url, headers=headers)
            if resp.status_code != 200:
                headers.pop("X-Target-Selector", None)
                resp = client.get(reader_url, headers=headers)
                if resp.status_code != 200:
                    return None

            data = resp.json().get("data", {})
            title = data.get("title")
            desc = data.get("description")
            content = data.get("content", "")

            # If article selector returned insufficient text, retry without selector
            if len(content.strip()) < 150:
                headers.pop("X-Target-Selector", None)
                resp = client.get(reader_url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    title = data.get("title") or title
                    desc = data.get("description") or desc
                    content = data.get("content", "")

            clean_body = _clean_reader_markdown(content)
            if len(clean_body) < 100:
                return None

            clean_domain = domain.lower().removeprefix("www.") if domain else ""
            if clean_domain in ("ndtv.com", "bbc.com", "cnn.com"):
                publisher = clean_domain.split(".")[0].upper()
            elif clean_domain:
                publisher = clean_domain.split(".")[0].capitalize()
            else:
                publisher = "Unknown"

            return NormalizedArticle(
                source_type="url",
                original_input=url,
                url=url,
                canonical_url=data.get("url") or url,
                title=title or "Untitled Article",
                body=clean_body,
                publisher=publisher,
                author=None,
                published_at=None,
                domain=domain,
                description=desc,
                extraction_method="reader_proxy_fallback",
                metadata={
                    "character_count": len(clean_body),
                    "word_count": len(clean_body.split()),
                    "proxy": "jina_reader",
                },
            )
    except Exception as exc:
        logger.warning("Reader proxy fallback failed for '%s': %s", url, exc)
        return None


def extract_article_from_url(
    url: str,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    client: Optional[httpx.Client] = None,
) -> NormalizedArticle:
    """End-to-end extraction from a validated URL with automatic reader fallback."""
    cleaned_url, domain = validate_url(url)
    logger.info("Starting article extraction for URL: %s", cleaned_url)

    try:
        html, final_url = fetch_article_html(cleaned_url, timeout=timeout, client=client)
        soup = BeautifulSoup(html, "html.parser")
        meta = extract_metadata(soup, original_url=cleaned_url, final_url=final_url)
        body, method = extract_article_body(soup, json_ld_body=meta.get("json_ld", {}).get("articleBody"))

        logger.info(
            "Successfully extracted article directly: title='%s', body_len=%d, method=%s",
            meta["title"],
            len(body),
            method,
        )

        return NormalizedArticle(
            source_type="url",
            original_input=url,
            url=final_url or cleaned_url,
            canonical_url=meta["canonical_url"],
            title=meta["title"],
            body=body,
            publisher=meta["publisher"],
            author=meta["author"],
            published_at=meta["published_at"],
            domain=meta["domain"] or domain,
            description=meta["description"],
            extraction_method=method,
            metadata={
                "raw_json_ld": meta["json_ld"],
                "character_count": len(body),
                "word_count": len(body.split()),
            },
        )
    except (HTTPError, FetchFailed, FetchTimeout, ArticleExtractionFailed, EmptyContent) as direct_exc:
        logger.warning(
            "Direct article fetch failed (%s: %s). Attempting reader proxy fallback for %s...",
            type(direct_exc).__name__,
            direct_exc,
            cleaned_url,
        )
        fallback_article = extract_article_via_reader(cleaned_url, domain=domain, timeout=timeout)
        if fallback_article:
            logger.info(
                "Reader proxy fallback succeeded for %s: title='%s', body_len=%d",
                cleaned_url,
                fallback_article.title,
                len(fallback_article.body),
            )
            return fallback_article
        # If fallback also failed, re-raise original exception
        raise direct_exc
