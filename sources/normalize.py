"""Apply client mapping configs to parsed source payloads."""

from __future__ import annotations

from typing import Any


def _default_boards_for_table(parsed: dict[str, Any], *, form_mode: bool = False) -> list[dict[str, Any]]:
    columns = list(parsed.get("columns") or [])
    boards: list[dict[str, Any]] = []
    if form_mode:
        boards.append(
            {
                "id": "form-summary",
                "type": "form_summary",
                "title": "Form responses",
            }
        )
    elif columns:
        # Prefer a progress-like column for cards when present
        title_col = columns[0]
        progress_col = None
        for name in columns:
            lower = name.lower()
            if any(token in lower for token in ("%", "percent", "progress", "complete", "status")):
                progress_col = name
                break
        boards.append(
            {
                "id": "stats",
                "type": "stats",
                "title": "Summary",
                "columns": columns[:4],
            }
        )
        boards.append(
            {
                "id": "cards",
                "type": "card_grid",
                "title": "Cards",
                "titleField": title_col,
                "subtitleField": columns[1] if len(columns) > 1 else None,
                "progressField": progress_col,
            }
        )
    boards.append(
        {
            "id": "table",
            "type": "table",
            "title": parsed.get("source_sheet") or "Data",
            "columns": columns,
        }
    )
    return boards


def _default_boards_for_document(parsed: dict[str, Any]) -> list[dict[str, Any]]:
    boards: list[dict[str, Any]] = [
        {
            "id": "doc-text",
            "type": "text_sections",
            "title": "Document",
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


def suggest_mapping(
    parsed: dict[str, Any],
    *,
    source_type: str,
    force_generic: bool = False,
) -> dict[str, Any]:
    kind = parsed.get("kind")
    if kind == "document":
        return {"boards": _default_boards_for_document(parsed)}
    if kind == "form" or source_type in {"google_forms", "microsoft_forms"}:
        return {"boards": _default_boards_for_table(parsed, form_mode=True)}
    if (
        not force_generic
        and parsed.get("has_scorecard_tab")
        and source_type == "google_sheet"
    ):
        return {"preset": "intrakore_scorecard"}
    return {"boards": _default_boards_for_table(parsed)}


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


def _build_stats_board(board: dict[str, Any], rows: list[dict[str, Any]], columns: list[str]) -> dict[str, Any]:
    cols = board.get("columns") or columns[:4]
    stats = []
    for col in cols:
        values = [r.get(col) for r in rows if r.get(col) is not None and r.get(col) != ""]
        numeric = []
        for v in values:
            try:
                numeric.append(float(str(v).rstrip("%")))
            except (TypeError, ValueError):
                pass
        if numeric:
            stats.append(
                {
                    "label": col,
                    "value": round(sum(numeric) / len(numeric), 2)
                    if "avg" in (board.get("aggregate") or "avg")
                    else round(sum(numeric), 2),
                    "detail": f"{len(numeric)} values",
                }
            )
        else:
            stats.append({"label": col, "value": len(values), "detail": "non-empty"})
    stats.insert(0, {"label": "Rows", "value": len(rows), "detail": "records"})
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
    cards = []
    for row in rows[:100]:
        title = row.get(title_field) if title_field else next(iter(row.values()), "")
        progress = _as_percent(row.get(progress_field)) if progress_field else None
        cards.append(
            {
                "title": "" if title is None else str(title),
                "subtitle": "" if subtitle_field is None else str(row.get(subtitle_field) or ""),
                "progress": progress,
                "status": "completed"
                if progress is not None and progress >= 1
                else ("ongoing" if progress and progress > 0 else "not-started"),
            }
        )
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
    return {
        "id": board.get("id") or "table",
        "type": "table",
        "title": board.get("title") or "Data",
        "columns": cols,
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
        boards_cfg = suggest_mapping(
            parsed, source_type=source_type, force_generic=True
        ).get("boards") or []

    kind = parsed.get("kind")
    rendered: list[dict[str, Any]] = []

    if kind == "document":
        sections = parsed.get("sections") or []
        tables = parsed.get("tables") or []
        for board in boards_cfg:
            btype = board.get("type")
            if btype == "text_sections":
                rendered.append(
                    {
                        "id": board.get("id") or "doc-text",
                        "type": "text_sections",
                        "title": board.get("title") or "Document",
                        "sections": sections,
                    }
                )
            elif btype in {"tables", "table"}:
                idx = int(board.get("tableIndex") or 0)
                table = next((t for t in tables if t.get("index") == idx), tables[idx] if idx < len(tables) else None)
                if table:
                    rendered.append(
                        {
                            "id": board.get("id") or f"doc-table-{idx}",
                            "type": "table",
                            "title": board.get("title") or table.get("title") or f"Table {idx + 1}",
                            "columns": table.get("columns") or [],
                            "rows": table.get("rows") or [],
                        }
                    )
    else:
        columns = list(parsed.get("columns") or [])
        rows = list(parsed.get("rows") or [])
        for board in boards_cfg:
            btype = board.get("type")
            if btype == "stats":
                rendered.append(_build_stats_board(board, rows, columns))
            elif btype == "card_grid":
                rendered.append(_build_card_grid(board, rows))
            elif btype == "form_summary":
                rendered.append(
                    {
                        "id": board.get("id") or "form-summary",
                        "type": "form_summary",
                        "title": board.get("title") or "Form responses",
                        "response_count": parsed.get("response_count", len(rows)),
                        "columns": columns,
                        "rows": rows[:50],
                    }
                )
            elif btype in {"table", "tables"}:
                rendered.append(_build_table_board(board, rows, columns))

    return {
        "mode": "generic",
        "source_file": parsed.get("source_file"),
        "source_sheet": parsed.get("source_sheet"),
        "source_url": parsed.get("source_url"),
        "kind": kind,
        "columns": parsed.get("columns"),
        "sheet_names": parsed.get("sheet_names"),
        "has_scorecard_tab": parsed.get("has_scorecard_tab"),
        "boards": rendered,
        "raw_preview": {
            "columns": parsed.get("columns"),
            "row_count": len(parsed.get("rows") or []),
            "section_count": len(parsed.get("sections") or []),
            "table_count": len(parsed.get("tables") or []),
            "response_count": parsed.get("response_count"),
        },
    }
