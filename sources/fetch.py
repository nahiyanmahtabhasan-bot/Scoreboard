"""Allowlisted URL downloads for Google Sheets/Docs and related hosts."""

from __future__ import annotations

import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ALLOWED_HOSTS = frozenset(
    {
        "docs.google.com",
        "drive.google.com",
        "www.googleapis.com",
        "spreadsheets.google.com",
        "graph.microsoft.com",
        "login.microsoftonline.com",
    }
)

USER_AGENT = "intrakore-scoreboard/2.0"

SHEET_ID_RE = re.compile(r"/spreadsheets/d/([a-zA-Z0-9-_]+)")
DOC_ID_RE = re.compile(r"/document/d/([a-zA-Z0-9-_]+)")
BARE_ID_RE = re.compile(r"^[a-zA-Z0-9-_]{20,}$")


def assert_allowed_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Only http(s) URLs are allowed")
    host = (parsed.hostname or "").lower()
    if host not in ALLOWED_HOSTS:
        raise ValueError(f"Host not allowed: {host or '(none)'}")


def fetch_bytes(url: str, *, timeout: int = 60) -> bytes:
    assert_allowed_url(url)
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.read()
    except HTTPError as exc:
        raise RuntimeError(f"Download failed ({exc.code} {exc.reason})") from exc
    except URLError as exc:
        raise RuntimeError(f"Could not reach URL: {exc.reason}") from exc


def extract_sheet_id(url_or_id: str) -> str:
    text = (url_or_id or "").strip()
    if not text:
        raise ValueError("Sheet URL or ID is required")
    match = SHEET_ID_RE.search(text)
    if match:
        return match.group(1)
    if BARE_ID_RE.match(text):
        return text
    raise ValueError("Could not parse Google Sheet ID from the provided value")


def extract_doc_id(url_or_id: str) -> str | None:
    text = (url_or_id or "").strip()
    if not text:
        return None
    match = DOC_ID_RE.search(text)
    if match:
        return match.group(1)
    if BARE_ID_RE.match(text) and "spreadsheet" not in text.lower():
        return text
    return None


def sheet_export_url(sheet_id: str) -> str:
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"


def sheet_view_url(sheet_id: str) -> str:
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"


def doc_export_url(doc_id: str) -> str:
    return f"https://docs.google.com/document/d/{doc_id}/export?format=docx"


def doc_view_url(doc_id: str) -> str:
    return f"https://docs.google.com/document/d/{doc_id}/edit"


def resolve_docx_fetch_url(url: str) -> str:
    """Return a downloadable URL for a Google Doc or direct .docx link."""
    text = (url or "").strip()
    doc_id = extract_doc_id(text)
    if doc_id and ("docs.google.com" in text or BARE_ID_RE.match(text)):
        return doc_export_url(doc_id)
    if text.lower().endswith(".docx") or "export?format=docx" in text.lower():
        assert_allowed_url(text)
        return text
    # Google Doc edit URL without matching earlier (edge cases)
    if "docs.google.com/document" in text:
        doc_id = extract_doc_id(text)
        if doc_id:
            return doc_export_url(doc_id)
    raise ValueError(
        "Provide a Google Doc link, a bare Doc ID, or a public .docx URL on an allowed host"
    )
