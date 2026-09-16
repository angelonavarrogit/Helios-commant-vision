"""HELIOS EYE — Safe HTML-to-text extraction for email bodies.

Email bodies are frequently HTML and always UNTRUSTED. This parser derives a
plain-text representation **without ever executing anything**:

- It uses Python's stdlib ``html.parser`` (an event-based tokenizer). Nothing is
  rendered, no scripts run, no network is touched.
- ``<script>`` and ``<style>`` contents are dropped entirely (they are noise and
  a common hiding place for junk).
- Block-level tags become line breaks so the text keeps some structure.

The output is *raw derived text*; the normalizer applies sanitization and
truncation afterwards. Keeping parsing and sanitization separate keeps each
piece small and testable.
"""

from __future__ import annotations

from html.parser import HTMLParser

# Tags whose text content we discard completely.
_SKIP_CONTENT_TAGS = frozenset({"script", "style", "head", "title"})

# Tags that should introduce a line break when opened/closed.
_BLOCK_TAGS = frozenset(
    {"p", "br", "div", "li", "tr", "table", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote"}
)


class _TextExtractor(HTMLParser):
    """Collects visible text from an HTML document, skipping script/style."""

    def __init__(self) -> None:
        # convert_charrefs=True lets the parser resolve entities like &amp; for us.
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []
        self._skip_depth = 0  # >0 while inside a skipped element

    def handle_starttag(self, tag: str, attrs: object) -> None:
        if tag in _SKIP_CONTENT_TAGS:
            self._skip_depth += 1
        elif tag in _BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_CONTENT_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
        elif tag in _BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        # Ignore text inside script/style/etc.
        if self._skip_depth == 0:
            self._chunks.append(data)

    def get_text(self) -> str:
        return "".join(self._chunks)


def html_to_text(html: str) -> str:
    """Convert an HTML string to plain text without executing anything.

    Returns best-effort derived text. On any parser error it degrades to the raw
    input rather than raising, because a malformed email must not break the
    pipeline (it is just untrusted data).
    """
    try:
        extractor = _TextExtractor()
        extractor.feed(html)
        extractor.close()
        return extractor.get_text()
    except Exception:  # noqa: BLE001 - never let a bad body break ingestion
        return html


def derive_body_text(*, body_text: str | None, body_html: str | None) -> str:
    """Pick the best available plain text for an email.

    Prefers a provider-supplied plain-text body; otherwise derives text from the
    HTML body; otherwise returns an empty string.
    """
    if body_text:
        return body_text
    if body_html:
        return html_to_text(body_html)
    return ""
