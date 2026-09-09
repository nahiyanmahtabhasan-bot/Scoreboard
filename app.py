"""Local scoreboard server for the Intrakore Project Plan."""

from __future__ import annotations

import io
import json
import os
import time
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from parse_scorecard import parse_scorecard
from sources.fetch import (
    extract_sheet_id,
    fetch_bytes,
    resolve_docx_fetch_url,
    sheet_export_url,
    sheet_view_url,
)
from sources.normalize import normalize_generic, suggest_mapping
from sources.parse_docx import parse_docx
from sources.parse_generic_sheet import list_sheet_names, parse_generic_sheet
from sources.parse_ms_forms import fetch_ms_form_responses, ms_forms_configured

GOOGLE_SHEET_ID = os.environ.get(
    "GOOGLE_SHEET_ID",
    "1Dt5ae3Cekxnd4XNZr1MdqBfx_vJyVFLeN5j-n-ibSjU",
)
GOOGLE_SHEET_URL = os.environ.get(
    "GOOGLE_SHEET_URL",
    f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}/edit",
)
GOOGLE_EXPORT_URL = os.environ.get(
    "GOOGLE_EXPORT_URL",
    f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}/export?format=xlsx",
)

DEFAULT_XLSX = Path.home() / "Downloads" / "Copy of Project Plan.xlsx"
CACHE_TTL_SECONDS = int(os.environ.get("SCOREBOARD_CACHE_SECONDS", "30"))
UPLOAD_MAX_BYTES = 4 * 1024 * 1024

BASE_DIR = Path(__file__).resolve().parent

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static"),
)

# cache key -> (timestamp, data)
_cache: dict[str, tuple[float, dict]] = {}


def _local_xlsx_path() -> Path | None:
    if os.environ.get("VERCEL"):
        return None
    override = os.environ.get("SCOREBOARD_XLSX")
    if override:
        return Path(override)
    if os.environ.get("SCOREBOARD_USE_LOCAL", "").lower() in {"1", "true", "yes"}:
        return DEFAULT_XLSX
    return None


def _cache_get(key: str, *, force_refresh: bool) -> dict | None:
    if force_refresh:
        return None
    entry = _cache.get(key)
    if not entry:
        return None
    ts, data = entry
    if time.time() - ts >= CACHE_TTL_SECONDS:
        return None
    return {**data, "fetched_at": ts, "from_cache": True}


def _cache_set(key: str, data: dict) -> dict:
    now = time.time()
    _cache[key] = (now, data)
    return {**data, "fetched_at": now, "from_cache": False}


def _fetch_sheet_bytes(sheet_id: str | None = None) -> bytes:
    sid = sheet_id or GOOGLE_SHEET_ID
    url = sheet_export_url(sid) if sheet_id else GOOGLE_EXPORT_URL
    if sheet_id is None and url == GOOGLE_EXPORT_URL:
        return fetch_bytes(GOOGLE_EXPORT_URL)
    return fetch_bytes(url)


def _load_scorecard(
    *,
    sheet_id: str | None = None,
    tab: str = "Scorecard",
    force_refresh: bool = False,
) -> dict:
    sid = sheet_id or GOOGLE_SHEET_ID
    cache_key = f"scorecard:{sid}:{tab}"
    cached = _cache_get(cache_key, force_refresh=force_refresh)
    if cached:
        return cached

    local_path = _local_xlsx_path() if not sheet_id else None
    if local_path:
        if not local_path.exists():
            raise FileNotFoundError(f"Spreadsheet not found: {local_path}")
        data = parse_scorecard(local_path, sheet_name=tab)
    else:
        try:
            content = _fetch_sheet_bytes(sheet_id)
        except RuntimeError as exc:
            raise RuntimeError(
                "Could not download Google Sheet. Make sure the sheet is shared as "
                f"'Anyone with the link can view'. ({exc})"
            ) from exc

        data = parse_scorecard(
            io.BytesIO(content),
            source_label="Google Sheets (live)",
            sheet_name=tab,
        )
        data["source_url"] = sheet_view_url(sid)

    return _cache_set(cache_key, data)


def _load_generic_sheet(
    *,
    sheet_id: str,
    tab: str | None,
    mapping: dict | None,
    source_type: str,
    force_refresh: bool = False,
) -> dict:
    cache_key = f"generic_sheet:{sheet_id}:{tab or ''}:{source_type}"
    # Mapping changes should not use stale rendered boards from a different mapping;
    # cache the raw parse then normalize.
    cached = _cache_get(cache_key, force_refresh=force_refresh)
    if cached and "columns" in cached and cached.get("_raw"):
        raw = cached["_raw"]
        result = normalize_generic(raw, mapping, source_type=source_type)
        result["fetched_at"] = cached["fetched_at"]
        result["from_cache"] = True
        return result

    content = _fetch_sheet_bytes(sheet_id)
    raw = parse_generic_sheet(
        io.BytesIO(content),
        tab=tab,
        source_label="Google Sheets (live)",
    )
    raw["source_url"] = sheet_view_url(sheet_id)
    stored = _cache_set(cache_key, {"_raw": raw, "columns": raw.get("columns")})
    result = normalize_generic(raw, mapping, source_type=source_type)
    result["fetched_at"] = stored["fetched_at"]
    result["from_cache"] = False
    return result


def _preview_sheet(sheet_id: str, tab: str | None = None) -> dict:
    content = _fetch_sheet_bytes(sheet_id)
    names = list_sheet_names(io.BytesIO(content))
    parsed = parse_generic_sheet(
        io.BytesIO(content),
        tab=tab,
        source_label="Google Sheets (live)",
    )
    return {
        "type": "google_sheet",
        "sheet_id": sheet_id,
        "sheet_names": names,
        "has_scorecard_tab": "Scorecard" in names,
        "columns": parsed.get("columns") or [],
        "row_count": len(parsed.get("rows") or []),
        "sample_rows": (parsed.get("rows") or [])[:5],
        "suggested_mapping": suggest_mapping(parsed, source_type="google_sheet"),
        "suggested_display_mode": (
            "scorecard" if "Scorecard" in names else "generic"
        ),
    }


def _preview_doc(url: str) -> dict:
    fetch_url = resolve_docx_fetch_url(url)
    content = fetch_bytes(fetch_url)
    parsed = parse_docx(content, source_label="Document (live)")
    return {
        "type": "word_doc",
        "section_count": len(parsed.get("sections") or []),
        "table_count": len(parsed.get("tables") or []),
        "sections": [
            {"heading": s.get("heading"), "paragraph_count": len(s.get("paragraphs") or [])}
            for s in (parsed.get("sections") or [])[:20]
        ],
        "tables": [
            {
                "index": t.get("index"),
                "title": t.get("title"),
                "columns": t.get("columns"),
                "row_count": len(t.get("rows") or []),
            }
            for t in (parsed.get("tables") or [])
        ],
        "suggested_mapping": suggest_mapping(parsed, source_type="word_doc"),
        "suggested_display_mode": "generic",
    }


def _fetch_source_payload(body: dict, *, force_refresh: bool = False) -> dict:
    source_type = (body.get("type") or "").strip()
    connection = body.get("connection") or {}
    display_mode = (body.get("displayMode") or "").strip()
    mapping = body.get("mapping") or {}

    if source_type in {"google_sheet", "google_forms"}:
        url_or_id = connection.get("urlOrId") or connection.get("url") or ""
        sheet_id = extract_sheet_id(url_or_id)
        tab = connection.get("tab") or None
        if display_mode == "scorecard" or (
            not display_mode and mapping.get("preset") == "intrakore_scorecard"
        ):
            data = _load_scorecard(
                sheet_id=sheet_id,
                tab=tab or "Scorecard",
                force_refresh=force_refresh,
            )
            data["mode"] = "scorecard"
            return data
        return _load_generic_sheet(
            sheet_id=sheet_id,
            tab=tab,
            mapping=mapping,
            source_type=source_type,
            force_refresh=force_refresh,
        )

    if source_type == "word_doc":
        url = connection.get("url") or connection.get("urlOrId") or ""
        cache_key = f"docx:{url}"
        cached = _cache_get(cache_key, force_refresh=force_refresh)
        if cached and cached.get("_raw"):
            result = normalize_generic(cached["_raw"], mapping, source_type=source_type)
            result["fetched_at"] = cached["fetched_at"]
            result["from_cache"] = True
            return result
        fetch_url = resolve_docx_fetch_url(url)
        content = fetch_bytes(fetch_url)
        raw = parse_docx(content, source_label="Document (live)")
        raw["source_url"] = url
        stored = _cache_set(cache_key, {"_raw": raw})
        result = normalize_generic(raw, mapping, source_type=source_type)
        result["fetched_at"] = stored["fetched_at"]
        result["from_cache"] = False
        return result

    if source_type == "microsoft_forms":
        form_id = (connection.get("formId") or connection.get("urlOrId") or "").strip()
        cache_key = f"msforms:{form_id}"
        cached = _cache_get(cache_key, force_refresh=force_refresh)
        if cached and cached.get("_raw"):
            result = normalize_generic(cached["_raw"], mapping, source_type=source_type)
            result["fetched_at"] = cached["fetched_at"]
            result["from_cache"] = True
            return result
        raw = fetch_ms_form_responses(form_id)
        stored = _cache_set(cache_key, {"_raw": raw})
        result = normalize_generic(raw, mapping, source_type=source_type)
        result["fetched_at"] = stored["fetched_at"]
        result["from_cache"] = False
        return result

    raise ValueError(f"Unsupported source type: {source_type or '(empty)'}")


@app.get("/api/health")
def health():
    return jsonify(
        {
            "status": "ok",
            "ms_forms_configured": ms_forms_configured(),
        }
    )


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/scoreboard")
def scoreboard_api():
    try:
        force_refresh = request.args.get("refresh", "").lower() in {"1", "true", "yes"}
        sheet_id = request.args.get("sheet_id") or None
        tab = request.args.get("tab") or "Scorecard"
        if sheet_id:
            sheet_id = extract_sheet_id(sheet_id)
        return jsonify(_load_scorecard(sheet_id=sheet_id, tab=tab, force_refresh=force_refresh))
    except FileNotFoundError as exc:
        return jsonify({"error": str(exc)}), 404
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"Failed to read spreadsheet: {exc}"}), 500


@app.get("/api/source/preview")
def source_preview():
    try:
        source_type = (request.args.get("type") or "").strip()
        if source_type in {"google_sheet", "google_forms"}:
            url_or_id = request.args.get("urlOrId") or request.args.get("url") or ""
            sheet_id = extract_sheet_id(url_or_id)
            tab = request.args.get("tab") or None
            preview = _preview_sheet(sheet_id, tab=tab)
            if source_type == "google_forms":
                preview["type"] = "google_forms"
                preview["suggested_display_mode"] = "generic"
                parsed_like = {
                    "kind": "table",
                    "columns": preview["columns"],
                    "rows": preview.get("sample_rows") or [],
                    "has_scorecard_tab": False,
                }
                preview["suggested_mapping"] = suggest_mapping(
                    parsed_like, source_type="google_forms"
                )
            return jsonify(preview)

        if source_type == "word_doc":
            url = request.args.get("url") or request.args.get("urlOrId") or ""
            return jsonify(_preview_doc(url))

        if source_type == "microsoft_forms":
            form_id = (request.args.get("formId") or request.args.get("urlOrId") or "").strip()
            if not ms_forms_configured():
                return jsonify(
                    {
                        "type": "microsoft_forms",
                        "ms_forms_configured": False,
                        "error": (
                            "Microsoft Forms credentials are not configured. "
                            "Set MS_TENANT_ID, MS_CLIENT_ID, and MS_CLIENT_SECRET."
                        ),
                        "suggested_display_mode": "generic",
                        "suggested_mapping": {
                            "boards": [
                                {"id": "form-summary", "type": "form_summary", "title": "Form responses"}
                            ]
                        },
                    }
                )
            raw = fetch_ms_form_responses(form_id)
            return jsonify(
                {
                    "type": "microsoft_forms",
                    "ms_forms_configured": True,
                    "form_id": form_id,
                    "columns": raw.get("columns") or [],
                    "row_count": len(raw.get("rows") or []),
                    "sample_rows": (raw.get("rows") or [])[:5],
                    "response_count": raw.get("response_count", 0),
                    "suggested_mapping": suggest_mapping(raw, source_type="microsoft_forms"),
                    "suggested_display_mode": "generic",
                }
            )

        return jsonify({"error": f"Unsupported type: {source_type}"}), 400
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 400


@app.post("/api/source/fetch")
def source_fetch():
    try:
        body = request.get_json(force=True, silent=True) or {}
        force_refresh = bool(body.get("refresh")) or request.args.get("refresh", "").lower() in {
            "1",
            "true",
            "yes",
        }
        data = _fetch_source_payload(body, force_refresh=force_refresh)
        return jsonify(data)
    except FileNotFoundError as exc:
        return jsonify({"error": str(exc)}), 404
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 500


@app.post("/api/source/upload")
def source_upload():
    try:
        upload = request.files.get("file")
        if not upload or not upload.filename:
            return jsonify({"error": "No file uploaded"}), 400
        if not upload.filename.lower().endswith(".docx"):
            return jsonify({"error": "Only .docx files are supported"}), 400
        content = upload.read(UPLOAD_MAX_BYTES + 1)
        if len(content) > UPLOAD_MAX_BYTES:
            return jsonify({"error": "File too large (max 4MB)"}), 400

        mapping_raw = request.form.get("mapping")
        mapping = None
        if mapping_raw:
            mapping = json.loads(mapping_raw)

        raw = parse_docx(content, source_label=upload.filename)
        preview_only = request.form.get("preview", "").lower() in {"1", "true", "yes"}
        if preview_only:
            return jsonify(
                {
                    "type": "word_doc",
                    "section_count": len(raw.get("sections") or []),
                    "table_count": len(raw.get("tables") or []),
                    "sections": [
                        {
                            "heading": s.get("heading"),
                            "paragraph_count": len(s.get("paragraphs") or []),
                        }
                        for s in (raw.get("sections") or [])[:20]
                    ],
                    "tables": [
                        {
                            "index": t.get("index"),
                            "title": t.get("title"),
                            "columns": t.get("columns"),
                            "row_count": len(t.get("rows") or []),
                        }
                        for t in (raw.get("tables") or [])
                    ],
                    "suggested_mapping": suggest_mapping(raw, source_type="word_doc"),
                    "suggested_display_mode": "generic",
                }
            )

        result = normalize_generic(raw, mapping, source_type="word_doc")
        result["fetched_at"] = time.time()
        result["from_cache"] = False
        return jsonify(result)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    local_path = _local_xlsx_path()
    source = local_path if local_path else GOOGLE_SHEET_URL
    print(f"Scoreboard: http://127.0.0.1:{port}")
    print(f"Reading: {source}")
    print(f"Cache TTL: {CACHE_TTL_SECONDS}s")
    print(f"MS Forms configured: {ms_forms_configured()}")
    app.run(host="127.0.0.1", port=port, debug=True)
