"""Local scoreboard server for the Intrakore Project Plan."""

from __future__ import annotations

import io
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from parse_scorecard import parse_scorecard

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

BASE_DIR = Path(__file__).resolve().parent

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static"),
)
_cache: tuple[float, dict] | None = None


def _local_xlsx_path() -> Path | None:
    if os.environ.get("VERCEL"):
        return None
    override = os.environ.get("SCOREBOARD_XLSX")
    if override:
        return Path(override)
    if os.environ.get("SCOREBOARD_USE_LOCAL", "").lower() in {"1", "true", "yes"}:
        return DEFAULT_XLSX
    return None


def _fetch_google_sheet() -> bytes:
    request = urllib.request.Request(
        GOOGLE_EXPORT_URL,
        headers={"User-Agent": "intrakore-scoreboard/1.0"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def _load_data(*, force_refresh: bool = False) -> dict:
    global _cache

    now = time.time()
    if not force_refresh and _cache and now - _cache[0] < CACHE_TTL_SECONDS:
        return _cache[1]

    local_path = _local_xlsx_path()
    if local_path:
        if not local_path.exists():
            raise FileNotFoundError(f"Spreadsheet not found: {local_path}")
        data = parse_scorecard(local_path)
    else:
        try:
            content = _fetch_google_sheet()
        except urllib.error.HTTPError as exc:
            raise RuntimeError(
                "Could not download Google Sheet. Make sure the sheet is shared as "
                f"'Anyone with the link can view'. ({exc.code} {exc.reason})"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Could not reach Google Sheets: {exc.reason}") from exc

        data = parse_scorecard(
            io.BytesIO(content),
            source_label="Google Sheets (live)",
        )
        data["source_url"] = GOOGLE_SHEET_URL

    _cache = (now, data)
    return data


@app.get("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/scoreboard")
def scoreboard_api():
    try:
        force_refresh = request.args.get("refresh", "").lower() in {"1", "true", "yes"}
        return jsonify(_load_data(force_refresh=force_refresh))
    except FileNotFoundError as exc:
        return jsonify({"error": str(exc)}), 404
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"Failed to read spreadsheet: {exc}"}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    local_path = _local_xlsx_path()
    source = local_path if local_path else GOOGLE_SHEET_URL
    print(f"Scoreboard: http://127.0.0.1:{port}")
    print(f"Reading: {source}")
    print(f"Cache TTL: {CACHE_TTL_SECONDS}s")
    app.run(host="127.0.0.1", port=port, debug=True)
