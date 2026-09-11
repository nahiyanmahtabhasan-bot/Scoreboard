"""Apply client mapping configs to parsed source payloads."""

from __future__ import annotations

from collections import Counter
from typing import Any

from sources.layouts import (
    LAYOUT_TEMPLATES,
    build_boards_for_template,
    suggest_layout,
)


def suggest_mapping(
    parsed: dict[str, Any],
    *,
    source_type: str,
    force_generic: bool = False,
) -> dict[str, Any]:
    return suggest_layout(
        parsed, source_type=source_type, force_generic=force_generic
    )


def _as_percent(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        text = str(value).strip().rstrip("%")
        try:
            num = float(text)
        except (TypeError, ValueError):
            return None
    if abs(num) <= 1.5:
        return max(0.0, min(1.0, num))
    return max(0.0, min(1.0, num / 100.0))


def _status_rank(status: str, progress: float | None) -> int:
    if status == "completed" or (progress is not None and progress >= 1):
        return 0
    if status == "ongoing" or (progress is not None and progress > 0):
        return 1
    return 2


def _tone_for(label: str, value: str) -> str:
    """CSS tone hint for severity / verdict / status chips."""
    text = (value or "").strip().lower()
    field = (label or "").strip().lower()
    if "severity" in field or "priority" in field:
        if text in {"critical", "blocker"}:
            return "critical"
        if text in {"high", "major"}:
            return "high"
        if text in {"medium", "moderate"}:
            return "medium"
        if text in {"low", "minor", "trivial"}:
            return "low"
    if "bug" in field or "verdict" in field or "classification" in field:
        if text in {"bug", "yes"}:
            return "bug"
        if text in {"no bug", "not a bug", "no"}:
            return "nobug"
        if text in {"tbc", "duplicate", "by design", "n/a"}:
            return "tbc"
    if "status" in field or "state" in field:
        if text in {"open", "new", "pending", "reopened"}:
            return "open"
        if text in {"actioned", "fixed", "closed", "done", "resolved", "complete", "completed"}:
            return "done"
        if text in {"in progress", "ongoing", "active"}:
            return "wip"
    return "neutral"


def _build_stats_board(board: dict[str, Any], rows: list[dict[str, Any]], columns: list[str]) -> dict[str, Any]:
    cols = list(board.get("columns") or columns[:4])
    aggregate = (board.get("aggregate") or "avg").lower()
    prefer_counts = aggregate == "count"
    stats: list[dict[str, Any]] = [
        {"label": "Rows", "value": len(rows), "detail": "records"}
    ]
    budget = 6 - 1  # remaining tiles after Rows

    # Spread categorical tiles across columns so Severity doesn't crowd out STATUS
    per_col = max(2, budget // max(1, len(cols))) if prefer_counts else budget

    for col_idx, col in enumerate(cols):
        if budget <= 0:
            break
        values = [r.get(col) for r in rows if r.get(col) is not None and r.get(col) != ""]
        numeric: list[float] = []
        for v in values:
            try:
                numeric.append(float(str(v).rstrip("%")))
            except (TypeError, ValueError):
                pass

        use_numeric = (
            numeric
            and not prefer_counts
            and len(numeric) >= max(1, int(len(values) * 0.6))
        )
        if use_numeric:
            stats.append(
                {
                    "label": col,
                    "value": round(sum(numeric) / len(numeric), 2)
                    if "avg" in aggregate
                    else round(sum(numeric), 2),
                    "detail": f"{len(numeric)} values",
                }
            )
            budget -= 1
            continue

        counts = Counter(str(v).strip() for v in values if str(v).strip())
        if not counts:
            stats.append({"label": col, "value": 0, "detail": "empty"})
            budget -= 1
            continue

        # Last column may take whatever budget remains
        take = budget if col_idx == len(cols) - 1 else min(per_col, budget)
        for label, count in counts.most_common(take):
            stats.append(
                {
                    "label": label,
                    "value": count,
                    "detail": col,
                    "tone": _tone_for(col, label),
                }
            )
            budget -= 1
            if budget <= 0:
                break

    return {
        "id": board.get("id") or "stats",
        "type": "stats",
        "title": board.get("title") or "Summary",
        "stats": stats[:6],
    }


def _build_card_grid(board: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    title_field = board.get("titleField")
    subtitle_field = board.get("subtitleField")
    progress_field = board.get("progressField")
    meta_fields = [f for f in (board.get("metaFields") or []) if f]
    sort_completed_first = board.get("sortCompletedFirst")
    if sort_completed_first is None:
        sort_completed_first = bool(progress_field)

    cards = []
    for row in rows[:100]:
        title = row.get(title_field) if title_field else next(iter(row.values()), "")
        progress = _as_percent(row.get(progress_field)) if progress_field else None
        status = (
            "completed"
            if progress is not None and progress >= 1
            else ("ongoing" if progress and progress > 0 else "not-started")
        )
        # Text status column when progress isn't numeric
        if progress is None and progress_field:
            raw = str(row.get(progress_field) or "").strip().lower()
            if raw in {"done", "complete", "completed", "closed", "actioned", "fixed", "resolved"}:
                status = "completed"
                progress = 1.0
            elif raw in {"in progress", "ongoing", "active", "pending", "open"}:
                status = "ongoing"
                progress = progress if progress is not None else 0.5

        meta = []
        for field in meta_fields:
            raw_val = row.get(field)
            if raw_val is None or raw_val == "":
                continue
            text = str(raw_val).strip()
            meta.append(
                {
                    "label": field,
                    "value": text,
                    "tone": _tone_for(field, text),
                }
            )

        cards.append(
            {
                "title": "" if title is None else str(title),
                "subtitle": "" if subtitle_field is None else str(row.get(subtitle_field) or ""),
                "progress": progress,
                "status": status,
                "meta": meta,
            }
        )

    if sort_completed_first:
        cards.sort(key=lambda c: (_status_rank(c.get("status") or "", c.get("progress")), c.get("title") or ""))

    return {
        "id": board.get("id") or "cards",
        "type": "card_grid",
        "title": board.get("title") or "Cards",
        "cards": cards,
    }


def _build_table_board(board: dict[str, Any], rows: list[dict[str, Any]], columns: list[str]) -> dict[str, Any]:
    cols = board.get("columns") or columns
    # Cap extremely wide sheets for UI performance
    if len(cols) > 40:
        cols = cols[:40]
    limited_rows = rows[:200]
    emphasis = [c for c in (board.get("emphasisColumns") or []) if c in cols]
    return {
        "id": board.get("id") or "table",
        "type": "table",
        "title": board.get("title") or "Data",
        "columns": cols,
        "emphasisColumns": emphasis,
        "rows": [{c: r.get(c) for c in cols} for r in limited_rows],
    }


def normalize_generic(
    parsed: dict[str, Any],
    mapping: dict[str, Any] | None,
    *,
    source_type: str,
) -> dict[str, Any]:
    mapping = mapping or {}
    boards_cfg = mapping.get("boards")
    if not boards_cfg:
        suggested = suggest_mapping(
            parsed, source_type=source_type, force_generic=True
        )
        boards_cfg = suggested.get("boards") or []
        if not mapping.get("template") and suggested.get("template"):
            mapping = {**mapping, "template": suggested["template"]}

    # Allow template id without boards — rebuild from roles/columns
    if not boards_cfg and mapping.get("template"):
        columns = list(parsed.get("columns") or [])
        boards_cfg = build_boards_for_template(
            mapping["template"],
            columns=columns,
            roles=mapping.get("column_roles"),
            parsed=parsed,
        )

    kind = parsed.get("kind")
    rendered: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    columns = list(parsed.get("columns") or [])
    rows = list(parsed.get("rows") or [])
    sections = parsed.get("sections") or []
    tables = parsed.get("tables") or []

    def _unique_id(preferred: str, fallback: str) -> str:
        base = (preferred or fallback or "board").strip() or "board"
        candidate = base
        n = 2
        while candidate in used_ids:
            candidate = f"{base}-{n}"
            n += 1
        used_ids.add(candidate)
        return candidate

    def _append_doc_table(board: dict[str, Any]) -> bool:
        idx = int(board.get("tableIndex") or 0)
        table = next(
            (t for t in tables if t.get("index") == idx),
            tables[idx] if idx < len(tables) else None,
        )
        if not table:
            return False
        rendered.append(
            {
                "id": _unique_id(board.get("id") or "", f"doc-table-{idx}"),
                "type": "table",
                "title": board.get("title") or table.get("title") or f"Table {idx + 1}",
                "columns": table.get("columns") or [],
                "rows": table.get("rows") or [],
            }
        )
        return True

    def _append_sheet_table(board: dict[str, Any]) -> None:
        built = _build_table_board(board, rows, columns)
        sheet_title = parsed.get("source_sheet")
        if sheet_title and board.get("id") in {None, "", "table"}:
            built["title"] = sheet_title
        built["id"] = _unique_id(built.get("id") or "", "table")
        rendered.append(built)

    for board in boards_cfg:
        btype = (board.get("type") or "").strip() or "table"

        if btype == "text_sections":
            rendered.append(
                {
                    "id": _unique_id(board.get("id") or "", "doc-text"),
                    "type": "text_sections",
                    "title": board.get("title")
                    or parsed.get("document_title")
                    or parsed.get("source_file")
                    or "Document",
                    "sections": sections,
                }
            )
            continue

        if btype == "stats":
            built = _build_stats_board(board, rows, columns)
            built["id"] = _unique_id(built.get("id") or "", "stats")
            rendered.append(built)
            continue

        if btype == "card_grid":
            built = _build_card_grid(board, rows)
            built["id"] = _unique_id(built.get("id") or "", "cards")
            rendered.append(built)
            continue

        if btype == "form_summary":
            rendered.append(
                {
                    "id": _unique_id(board.get("id") or "", "form-summary"),
                    "type": "form_summary",
                    "title": board.get("title") or "Form responses",
                    "response_count": parsed.get("response_count", len(rows)),
                    "columns": columns,
                    "rows": rows[:50],
                }
            )
            continue

        if btype in {"table", "tables"}:
            if kind == "document" and tables:
                if not _append_doc_table(board):
                    # Still show a tab so configured boards are never silently dropped
                    rendered.append(
                        {
                            "id": _unique_id(board.get("id") or "", "table"),
                            "type": "table",
                            "title": board.get("title") or "Table",
                            "columns": [],
                            "rows": [],
                        }
                    )
            else:
                _append_sheet_table(board)
            continue

        # Unknown type: keep the board visible as a table fallback
        if kind == "document" and tables and _append_doc_table(board):
            continue
        if columns or rows:
            _append_sheet_table({**board, "type": "table"})
        else:
            rendered.append(
                {
                    "id": _unique_id(board.get("id") or "", "board"),
                    "type": "table",
                    "title": board.get("title") or btype or "Board",
                    "columns": [],
                    "rows": [],
                }
            )

    section_count = len(sections) if kind == "document" else None

    return {
        "mode": "generic",
        "source_file": parsed.get("source_file"),
        "source_sheet": parsed.get("source_sheet"),
        "source_url": parsed.get("source_url"),
        "document_title": parsed.get("document_title"),
        "kind": kind,
        "columns": parsed.get("columns"),
        "sheet_names": parsed.get("sheet_names"),
        "has_scorecard_tab": parsed.get("has_scorecard_tab"),
        "template": mapping.get("template"),
        "boards": rendered,
        "raw_preview": {
            "columns": parsed.get("columns"),
            "row_count": len(rows),
            "section_count": section_count,
            "table_count": len(tables),
            "response_count": parsed.get("response_count"),
        },
    }


# Re-export for callers / tests
__all__ = [
    "LAYOUT_TEMPLATES",
    "normalize_generic",
    "suggest_mapping",
]
