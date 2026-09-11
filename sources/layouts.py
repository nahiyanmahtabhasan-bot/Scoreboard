"""Rule-based layout templates and column-role inference (no LLM)."""

from __future__ import annotations

from typing import Any

# Public template catalog for the Sources UI
LAYOUT_TEMPLATES: list[dict[str, str]] = [
    {
        "id": "bug_index",
        "label": "Bug / issue index",
        "description": "Severity · bug/no-bug · status table with summary and finding cards",
    },
    {
        "id": "status_tracker",
        "label": "Status tracker",
        "description": "Stats, progress cards, and a full table",
    },
    {
        "id": "summary_cards",
        "label": "Summary + cards",
        "description": "Overview stats with a card grid and table",
    },
    {
        "id": "team_roster",
        "label": "Team roster",
        "description": "People cards (name + role/team) and table",
    },
    {
        "id": "form_responses",
        "label": "Form responses",
        "description": "Response summary plus a responses table",
    },
    {
        "id": "simple_table",
        "label": "Simple table",
        "description": "Table only — best for wide or mixed sheets",
    },
    {
        "id": "document",
        "label": "Document",
        "description": "Text sections and embedded tables",
    },
]

_TITLE_TOKENS = (
    "finding",
    "issue",
    "snag",
    "defect",
    "title",
    "name",
    "item",
    "task",
    "project",
    "deliverable",
    "subject",
    "label",
    "module",
)
_SUBTITLE_TOKENS = (
    "subtitle",
    "description",
    "desc",
    "detail",
    "summary",
    "notes",
    "phase",
    "category",
    "type",
    "area",
    "module",
)
_OWNER_TOKENS = (
    "owner",
    "assignee",
    "assigned",
    "lead",
    "person",
    "member",
    "team",
    "role",
    "responsible",
)
_STATUS_TOKENS = (
    "status",
    "state",
    "stage",
)
_PROGRESS_TOKENS = (
    "%",
    "percent",
    "progress",
    "complete",
    "completion",
    "done",
    "pct",
)
_DATE_TOKENS = (
    "date",
    "deadline",
    "due",
    "updated",
    "created",
    "timestamp",
    "when",
)
_ID_TOKENS = (
    "id",
    "key",
    "code",
    "ref",
    "number",
    "#",
)
_SEVERITY_TOKENS = (
    "severity",
    "priority",
    "urgency",
    "impact",
)
_VERDICT_TOKENS = (
    "bug/ no bug",
    "bug / no bug",
    "bug/no bug",
    "bug or no",
    "no bug",
    "verdict",
    "classification",
    "is bug",
)


def _lower(name: str) -> str:
    return (name or "").strip().lower()


def _score_tokens(name: str, tokens: tuple[str, ...]) -> int:
    lower = _lower(name)
    score = 0
    for token in tokens:
        if token == "%" and "%" in lower:
            score += 3
        elif token in lower:
            score += 2 if len(token) > 2 else 1
    return score


def _looks_numeric_progress(values: list[Any]) -> bool:
    """True when values look like % complete — not row numbers / IDs."""
    usable = [v for v in values if v not in (None, "")]
    if not usable:
        return False
    pct_hits = 0
    ratio_hits = 0
    for value in usable:
        text = str(value).strip()
        if text.endswith("%"):
            pct_hits += 1
            continue
        try:
            num = float(text.rstrip("%"))
        except (TypeError, ValueError):
            continue
        if 0 <= num <= 1.5:
            ratio_hits += 1
    # Require % markers or clear 0–1 ratios — plain integers 1..n are not progress
    return pct_hits >= max(1, len(usable) // 3) or ratio_hits >= max(2, len(usable) // 2)


def _looks_status_text(values: list[Any]) -> bool:
    status_words = {
        "done",
        "complete",
        "completed",
        "in progress",
        "ongoing",
        "not started",
        "pending",
        "blocked",
        "open",
        "closed",
        "active",
        "actioned",
        "fixed",
        "wontfix",
        "won't fix",
        "deferred",
        "tbc",
    }
    hits = 0
    for value in values:
        if value is None or value == "":
            continue
        if _lower(str(value)) in status_words:
            hits += 1
    return hits >= 1


def _looks_severity_text(values: list[Any]) -> bool:
    words = {"critical", "high", "medium", "low", "blocker", "minor", "major", "trivial"}
    hits = sum(1 for v in values if v not in (None, "") and _lower(str(v)) in words)
    return hits >= 1


def _looks_verdict_text(values: list[Any]) -> bool:
    words = {"bug", "no bug", "not a bug", "tbc", "n/a", "duplicate", "by design"}
    hits = sum(1 for v in values if v not in (None, "") and _lower(str(v)) in words)
    return hits >= 1


def is_bug_sheet(columns: list[str], sample_rows: list[dict[str, Any]] | None = None) -> bool:
    """Heuristic: Severity + (Bug/No Bug | Finding | STATUS) looks like a bug index."""
    lowers = [_lower(c) for c in columns]
    has_severity = any("severity" in c or "priority" in c for c in lowers)
    has_verdict = any(
        ("bug" in c and "no" in c) or "verdict" in c or c in {"bug", "classification"}
        for c in lowers
    )
    has_finding = any(
        any(t in c for t in ("finding", "issue", "snag", "defect")) for c in lowers
    )
    has_status = any("status" in c for c in lowers)
    sheet_hint = any("bug" in c or "snag" in c for c in lowers)
    if has_severity and (has_verdict or has_finding):
        return True
    if has_severity and has_status and (sheet_hint or has_finding):
        return True
    # Sample-based fallback
    if has_severity and sample_rows:
        for col in columns:
            if "severity" in _lower(col) and _looks_severity_text(
                [r.get(col) for r in sample_rows[:12]]
            ):
                return has_status or has_verdict or has_finding
    return False


def infer_column_roles(
    columns: list[str],
    sample_rows: list[dict[str, Any]] | None = None,
) -> dict[str, str | None]:
    """Map semantic roles to column names (or None)."""
    sample_rows = sample_rows or []
    roles: dict[str, str | None] = {
        "title": None,
        "subtitle": None,
        "owner": None,
        "status": None,
        "progress": None,
        "date": None,
        "id": None,
        "severity": None,
        "verdict": None,
    }
    if not columns:
        return roles

    bug_like = is_bug_sheet(columns, sample_rows)
    best: dict[str, tuple[int, str]] = {}

    for col in columns:
        samples = [row.get(col) for row in sample_rows[:12]]
        lower = _lower(col)
        progress_score = _score_tokens(col, _PROGRESS_TOKENS)
        # Never treat pure ID / row-index columns as progress
        id_score = _score_tokens(col, _ID_TOKENS)
        if lower in {"#", "no", "no.", "s.no", "sno"} or (id_score and not progress_score):
            sample_boost = 0
        elif progress_score > 0 and _looks_numeric_progress(samples):
            sample_boost = 3
        elif _looks_numeric_progress(samples) and any(
            str(v).strip().endswith("%") for v in samples if v not in (None, "")
        ):
            sample_boost = 2
        else:
            sample_boost = 0

        title_score = _score_tokens(col, _TITLE_TOKENS)
        # On bug sheets, prefer Finding over Modules
        if bug_like:
            if any(t in lower for t in ("finding", "issue", "snag", "defect")):
                title_score += 4
            if "module" in lower and "finding" not in lower:
                title_score = max(0, title_score - 3)

        candidates = {
            "title": title_score,
            "subtitle": _score_tokens(col, _SUBTITLE_TOKENS),
            "owner": _score_tokens(col, _OWNER_TOKENS),
            "status": _score_tokens(col, _STATUS_TOKENS)
            + (2 if _looks_status_text(samples) else 0),
            "progress": progress_score + sample_boost,
            "date": _score_tokens(col, _DATE_TOKENS),
            "id": id_score + (3 if lower in {"id", "#"} or lower.endswith(" id") else 0),
            "severity": _score_tokens(col, _SEVERITY_TOKENS)
            + (3 if _looks_severity_text(samples) else 0),
            "verdict": _score_tokens(col, _VERDICT_TOKENS)
            + (3 if _looks_verdict_text(samples) else 0),
        }
        # Exact-ish verdict header "Bug/ No Bug"
        if "bug" in lower and "no" in lower:
            candidates["verdict"] = max(candidates["verdict"], 6)

        for role, score in candidates.items():
            if score <= 0:
                continue
            prev = best.get(role)
            if prev is None or score > prev[0]:
                best[role] = (score, col)

    for role, (_score, col) in best.items():
        roles[role] = col

    # Prefer a real ticket ID (e.g. SNG-01) over "#" when both exist
    if roles.get("id"):
        id_lower = _lower(roles["id"])
        if id_lower in {"#", "no", "no."}:
            for col in columns:
                if col == roles["id"]:
                    continue
                if _score_tokens(col, ("id",)) and _lower(col) not in {"#"}:
                    roles["id"] = col
                    break

    # Fallbacks so cards always have a title
    used = {v for v in roles.values() if v}
    if not roles["title"]:
        for col in columns:
            if roles.get("id") == col:
                continue
            if col not in used or col == roles.get("id"):
                roles["title"] = col
                break
        if not roles["title"]:
            roles["title"] = columns[0]

    if not roles["subtitle"]:
        for col in columns:
            if col != roles["title"] and col not in {
                roles.get("progress"),
                roles.get("id"),
            }:
                if col == roles.get("owner") or col == roles.get("status"):
                    roles["subtitle"] = col
                    break
        if not roles["subtitle"]:
            for col in columns:
                if col != roles["title"] and col not in {
                    roles.get("id"),
                    roles.get("severity"),
                    roles.get("verdict"),
                    roles.get("status"),
                }:
                    roles["subtitle"] = col
                    break

    # If progress and status point at the same column, keep progress for % sheets
    if roles["progress"] and roles["progress"] == roles["status"]:
        for col in columns:
            if col != roles["progress"] and _score_tokens(col, _STATUS_TOKENS):
                roles["status"] = col
                break
        else:
            roles["status"] = None

    # Bug sheets: progress is usually wrong — clear unless header clearly says progress
    if bug_like and roles.get("progress"):
        if _score_tokens(roles["progress"], _PROGRESS_TOKENS) <= 0:
            roles["progress"] = None

    return roles


def _stats_columns(columns: list[str], roles: dict[str, str | None], limit: int = 4) -> list[str]:
    preferred = [
        roles.get("severity"),
        roles.get("verdict"),
        roles.get("progress"),
        roles.get("status"),
        roles.get("owner"),
        roles.get("date"),
    ]
    ordered: list[str] = []
    for col in preferred:
        if col and col in columns and col not in ordered:
            ordered.append(col)
    for col in columns:
        if col not in ordered:
            ordered.append(col)
    return ordered[:limit]


def _bug_table_columns(columns: list[str], roles: dict[str, str | None]) -> list[str]:
    """Keep the dense bug-index columns readable — skip long repro text by default."""
    preferred = [
        roles.get("id"),
        roles.get("severity"),
        roles.get("title"),
        roles.get("subtitle"),
        roles.get("owner"),
        roles.get("verdict"),
        roles.get("status"),
    ]
    # Named fallbacks common on Intrakore BugIndex
    for name in (
        "ID",
        "Severity",
        "Modules",
        "Area",
        "Finding",
        "Responsible",
        "Bug/ No Bug",
        "STATUS",
        "#",
    ):
        if name in columns and name not in preferred:
            preferred.append(name)

    ordered: list[str] = []
    for col in preferred:
        if col and col in columns and col not in ordered:
            ordered.append(col)

    # If we somehow got nothing useful, fall back to first few columns
    if len(ordered) < 3:
        for col in columns:
            if col not in ordered:
                ordered.append(col)
            if len(ordered) >= 8:
                break
    return ordered


def _bug_meta_fields(roles: dict[str, str | None]) -> list[str]:
    fields: list[str] = []
    for key in ("severity", "verdict", "status", "id"):
        col = roles.get(key)
        if col and col not in fields:
            fields.append(col)
    return fields


def build_boards_for_template(
    template_id: str,
    *,
    columns: list[str],
    roles: dict[str, str | None] | None = None,
    parsed: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Emit board mapping configs for a named layout template."""
    parsed = parsed or {}
    roles = roles or infer_column_roles(columns, parsed.get("rows") or parsed.get("sample_rows"))
    title_field = roles.get("title") or (columns[0] if columns else None)
    subtitle_field = roles.get("subtitle") or roles.get("owner") or roles.get("status")
    progress_field = roles.get("progress") or roles.get("status")
    sheet_title = parsed.get("source_sheet") or "Data"

    if template_id == "document":
        return _document_boards(parsed)

    if template_id == "form_responses":
        boards: list[dict[str, Any]] = [
            {
                "id": "form-summary",
                "type": "form_summary",
                "title": "Form responses",
            }
        ]
        if columns:
            boards.append(
                {
                    "id": "table",
                    "type": "table",
                    "title": "Responses",
                    "columns": columns,
                }
            )
        return boards

    if template_id == "simple_table":
        return [
            {
                "id": "table",
                "type": "table",
                "title": sheet_title,
                "columns": columns,
            }
        ]

    if template_id == "bug_index":
        if not columns:
            return []
        meta = _bug_meta_fields(roles)
        table_cols = _bug_table_columns(columns, roles)
        stats_cols = _stats_columns(columns, roles, limit=3)
        # Table first so activation lands on the sensible primary view
        return [
            {
                "id": "table",
                "type": "table",
                "title": sheet_title,
                "columns": table_cols,
                "emphasisColumns": [
                    c
                    for c in (
                        roles.get("severity"),
                        roles.get("verdict"),
                        roles.get("status"),
                    )
                    if c
                ],
            },
            {
                "id": "stats",
                "type": "stats",
                "title": "Breakdown",
                "columns": stats_cols,
                "aggregate": "count",
            },
            {
                "id": "cards",
                "type": "card_grid",
                "title": "Findings",
                "titleField": title_field,
                "subtitleField": subtitle_field,
                "progressField": None,
                "metaFields": meta,
                "sortCompletedFirst": False,
            },
        ]

    if template_id == "team_roster":
        boards = []
        if columns:
            boards.append(
                {
                    "id": "cards",
                    "type": "card_grid",
                    "title": "Team",
                    "titleField": title_field,
                    "subtitleField": roles.get("owner")
                    or roles.get("subtitle")
                    or (columns[1] if len(columns) > 1 else None),
                    "progressField": None,
                }
            )
            boards.append(
                {
                    "id": "table",
                    "type": "table",
                    "title": sheet_title,
                    "columns": columns,
                }
            )
        return boards

    if template_id == "status_tracker":
        boards = []
        if columns:
            boards.append(
                {
                    "id": "stats",
                    "type": "stats",
                    "title": "Summary",
                    "columns": _stats_columns(columns, roles),
                }
            )
            boards.append(
                {
                    "id": "cards",
                    "type": "card_grid",
                    "title": "Progress",
                    "titleField": title_field,
                    "subtitleField": subtitle_field,
                    "progressField": progress_field,
                    "sortCompletedFirst": True,
                }
            )
            boards.append(
                {
                    "id": "table",
                    "type": "table",
                    "title": sheet_title,
                    "columns": columns,
                }
            )
        return boards

    # summary_cards (default) and unknown → improved default
    boards = []
    if columns:
        boards.append(
            {
                "id": "stats",
                "type": "stats",
                "title": "Summary",
                "columns": _stats_columns(columns, roles),
            }
        )
        boards.append(
            {
                "id": "cards",
                "type": "card_grid",
                "title": "Cards",
                "titleField": title_field,
                "subtitleField": subtitle_field,
                "progressField": progress_field,
                "sortCompletedFirst": bool(progress_field),
            }
        )
        boards.append(
            {
                "id": "table",
                "type": "table",
                "title": sheet_title,
                "columns": columns,
            }
        )
    elif parsed.get("kind") == "document":
        return _document_boards(parsed)
    return boards


def _document_boards(parsed: dict[str, Any]) -> list[dict[str, Any]]:
    doc_title = parsed.get("document_title") or parsed.get("source_file") or "Document"
    boards: list[dict[str, Any]] = [
        {
            "id": "doc-text",
            "type": "text_sections",
            "title": doc_title,
        }
    ]
    for table in parsed.get("tables") or []:
        boards.append(
            {
                "id": f"doc-table-{table.get('index', 0)}",
                "type": "tables",
                "title": table.get("title") or "Table",
                "tableIndex": table.get("index", 0),
            }
        )
    return boards


def pick_template(
    parsed: dict[str, Any],
    *,
    source_type: str,
    roles: dict[str, str | None] | None = None,
) -> str:
    """Choose a layout template id from parsed source context."""
    kind = parsed.get("kind")
    if kind == "document" or source_type == "word_doc":
        return "document"
    if kind == "form" or source_type in {"google_forms", "microsoft_forms"}:
        return "form_responses"

    columns = list(parsed.get("columns") or [])
    sample = list(parsed.get("rows") or parsed.get("sample_rows") or [])[:12]
    roles = roles or infer_column_roles(columns, sample)

    if not columns:
        return "simple_table"

    sheet_name = _lower(str(parsed.get("source_sheet") or ""))
    if is_bug_sheet(columns, sample) or any(
        t in sheet_name for t in ("bug", "snag", "defect", "issue")
    ):
        return "bug_index"

    owner_ish = roles.get("owner")
    progress_ish = roles.get("progress")
    status_ish = roles.get("status")
    title_ish = roles.get("title")

    # Team roster: name + role/team, little/no progress
    if owner_ish and title_ish and not progress_ish:
        owner_lower = _lower(owner_ish)
        if any(t in owner_lower for t in ("team", "role", "member", "person", "assignee")):
            return "team_roster"
        if any(_score_tokens(c, ("email", "phone", "department")) for c in columns):
            return "team_roster"

    # Progress trackers need a real progress signal — status alone ≠ module progress
    if progress_ish:
        return "status_tracker"

    if status_ish and roles.get("severity"):
        return "bug_index"

    if len(columns) <= 2:
        return "simple_table"

    return "summary_cards"


def suggest_layout(
    parsed: dict[str, Any],
    *,
    source_type: str,
    force_generic: bool = False,
) -> dict[str, Any]:
    """
    Full suggestion payload for preview / normalize defaults.

    Returns either:
      { preset: "intrakore_scorecard" }
    or:
      { template, column_roles, boards, templates }
    """
    kind = parsed.get("kind")
    # Only suggest the Intrakore scorecard preset when the *selected* sheet tab
    # is Scorecard — not merely because the workbook also contains one.
    sheet_name = (parsed.get("source_sheet") or "").strip()
    if (
        not force_generic
        and source_type == "google_sheet"
        and sheet_name == "Scorecard"
    ):
        return {"preset": "intrakore_scorecard"}

    if kind == "document" or source_type == "word_doc":
        boards = build_boards_for_template("document", columns=[], parsed=parsed)
        return {
            "template": "document",
            "column_roles": {},
            "boards": boards,
            "templates": LAYOUT_TEMPLATES,
        }

    columns = list(parsed.get("columns") or [])
    sample = list(parsed.get("rows") or [])[:12]
    roles = infer_column_roles(columns, sample)
    template = pick_template(parsed, source_type=source_type, roles=roles)
    boards = build_boards_for_template(
        template, columns=columns, roles=roles, parsed=parsed
    )
    return {
        "template": template,
        "column_roles": roles,
        "boards": boards,
        "templates": LAYOUT_TEMPLATES,
    }
