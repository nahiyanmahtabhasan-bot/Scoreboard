"""Fetch Microsoft Forms responses via Microsoft Graph."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from sources.fetch import USER_AGENT, assert_allowed_url


def ms_forms_configured() -> bool:
    return bool(
        os.environ.get("MS_TENANT_ID")
        and os.environ.get("MS_CLIENT_ID")
        and os.environ.get("MS_CLIENT_SECRET")
    )


def _post_form(url: str, data: dict[str, str]) -> dict[str, Any]:
    assert_allowed_url(url)
    encoded = urllib.parse.urlencode(data).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=encoded,
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def _get_json(url: str, token: str) -> dict[str, Any]:
    assert_allowed_url(url)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def _access_token() -> str:
    tenant = os.environ["MS_TENANT_ID"]
    client_id = os.environ["MS_CLIENT_ID"]
    client_secret = os.environ["MS_CLIENT_SECRET"]
    scope = os.environ.get("MS_FORMS_SCOPE", "https://graph.microsoft.com/.default")
    token_url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
    payload = _post_form(
        token_url,
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": scope,
            "grant_type": "client_credentials",
        },
    )
    token = payload.get("access_token")
    if not token:
        raise RuntimeError("Microsoft Graph did not return an access token")
    return token


def _answers_to_row(answers: list[dict[str, Any]] | None) -> dict[str, Any]:
    row: dict[str, Any] = {}
    for answer in answers or []:
        question = (
            answer.get("questionId")
            or answer.get("questionTitle")
            or answer.get("id")
            or "Answer"
        )
        # Prefer readable title when present
        title = answer.get("questionTitle") or str(question)
        value = answer.get("answer")
        if value is None:
            value = answer.get("value")
        if isinstance(value, (list, dict)):
            value = json.dumps(value, ensure_ascii=False)
        row[str(title)] = value
    return row


def fetch_ms_form_responses(form_id: str, *, source_label: str | None = None) -> dict[str, Any]:
    if not ms_forms_configured():
        raise RuntimeError(
            "Microsoft Forms is not configured. Set MS_TENANT_ID, MS_CLIENT_ID, "
            "and MS_CLIENT_SECRET on the server."
        )
    form_id = (form_id or "").strip()
    if not form_id:
        raise ValueError("Microsoft Form ID is required")

    try:
        token = _access_token()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Microsoft auth failed ({exc.code})") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach Microsoft login: {exc.reason}") from exc

    # Forms responses live under the beta forms API for many tenants.
    # Try common Graph endpoints in order.
    candidates = [
        f"https://graph.microsoft.com/v1.0/forms/{form_id}/responses",
        f"https://graph.microsoft.com/beta/forms/{form_id}/responses",
        f"https://graph.microsoft.com/beta/me/forms/{form_id}/responses",
    ]

    last_error: Exception | None = None
    payload: dict[str, Any] | None = None
    for url in candidates:
        try:
            payload = _get_json(url, token)
            break
        except urllib.error.HTTPError as exc:
            last_error = RuntimeError(f"Graph forms fetch failed ({exc.code}) at {url}")
        except Exception as exc:  # noqa: BLE001
            last_error = exc

    if payload is None:
        raise RuntimeError(
            str(last_error)
            or "Could not fetch Microsoft Form responses. "
            "Ensure the app has Forms.Read.All (application) and admin consent."
        )

    items = payload.get("value") or []
    rows: list[dict[str, Any]] = []
    columns_order: list[str] = []
    seen_cols: set[str] = set()

    for item in items:
        base: dict[str, Any] = {}
        if item.get("id"):
            base["Response ID"] = item["id"]
        if item.get("submitDate") or item.get("submittedDateTime"):
            base["Submitted"] = item.get("submitDate") or item.get("submittedDateTime")
        if item.get("responder"):
            base["Responder"] = item.get("responder")

        answers = item.get("answers") or item.get("responses") or []
        answer_row = _answers_to_row(answers if isinstance(answers, list) else [])
        row = {**base, **answer_row}
        for key in row:
            if key not in seen_cols:
                seen_cols.add(key)
                columns_order.append(key)
        rows.append(row)

    return {
        "kind": "form",
        "source_file": source_label or f"Microsoft Form {form_id}",
        "form_id": form_id,
        "response_count": len(rows),
        "columns": columns_order,
        "rows": rows,
    }
