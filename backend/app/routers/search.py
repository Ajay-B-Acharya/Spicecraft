import logging
import re
from html import unescape
from urllib.parse import parse_qs, quote_plus, urlparse
from urllib.request import Request, urlopen

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies import get_current_firebase_uid

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])

DUCKDUCKGO_HTML_URL = "https://html.duckduckgo.com/html/"
MAX_RESULTS = 10
SEARCH_SUFFIX = (
    " electronics datasheet application note tutorial LTspice research paper"
)
RESULT_PATTERN = re.compile(
    r'<a[^>]*class="result__a"[^>]*href="(?P<href>[^"]+)"[^>]*>(?P<title>.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
TAG_PATTERN = re.compile(r"<[^>]+>")


def _clean_html(value: str) -> str:
    return TAG_PATTERN.sub("", unescape(value)).strip()


def _extract_target_url(href: str) -> str:
    parsed = urlparse(href)
    if parsed.path == "/l/":
        uddg = parse_qs(parsed.query).get("uddg", [None])[0]
        if uddg:
            return unescape(uddg)
    return unescape(href)


def _source_name_from_url(url: str) -> str:
    hostname = urlparse(url).netloc.lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]
    return hostname or "Unknown Source"


def _image_url_for_source(url: str) -> str | None:
    hostname = urlparse(url).netloc.lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]
    if not hostname:
        return None
    return f"https://icons.duckduckgo.com/ip3/{hostname}.ico"


def _search_duckduckgo(query: str) -> list[dict[str, str | None]]:
    search_query = f"{query.strip()}{SEARCH_SUFFIX}"
    request = Request(
        f"{DUCKDUCKGO_HTML_URL}?q={quote_plus(search_query)}",
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        },
    )

    with urlopen(request, timeout=10) as response:
        html = response.read().decode("utf-8", errors="ignore")

    results: list[dict[str, str | None]] = []
    seen_urls: set[str] = set()

    for match in RESULT_PATTERN.finditer(html):
        source_url = _extract_target_url(match.group("href"))
        if not source_url.startswith(("http://", "https://")):
            continue
        if source_url in seen_urls:
            continue

        seen_urls.add(source_url)
        results.append(
            {
                "title": _clean_html(match.group("title")),
                "source_name": _source_name_from_url(source_url),
                "source_url": source_url,
                "image_url": _image_url_for_source(source_url),
            }
        )

        if len(results) >= MAX_RESULTS:
            break

    return results


@router.get("")
def search_circuits(
    q: str = Query(..., min_length=2, max_length=200),
    firebase_uid: str = Depends(get_current_firebase_uid),
) -> list[dict[str, str | None]]:
    logger.info("GET /search — user=%s query=%r", firebase_uid, q)

    try:
        return _search_duckduckgo(q)
    except Exception as exc:
        logger.exception("Circuit search failed for query=%r", q)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Search provider request failed",
        ) from exc
