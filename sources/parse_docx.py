"""Parse Word / Google Doc exports into sections and tables."""

from __future__ import annotations

import io
from typing import Any, BinaryIO

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph


def _para_text(paragraph: Paragraph) -> str:
    return (paragraph.text or "").strip()


def _heading_level(paragraph: Paragraph) -> int | None:
    style_name = (paragraph.style.name if paragraph.style else "") or ""
    if style_name.startswith("Heading"):
        parts = style_name.split()
        if len(parts) >= 2 and parts[1].isdigit():
            return int(parts[1])
        return 1
    return None


def _table_to_dict(table: Table, index: int) -> dict[str, Any]:
    matrix: list[list[str]] = []
    for row in table.rows:
        matrix.append([(cell.text or "").strip() for cell in row.cells])
    if not matrix:
        return {
            "index": index,
            "title": f"Table {index + 1}",
            "columns": [],
            "rows": [],
        }
    header = matrix[0]
    columns = [h or f"Column {i + 1}" for i, h in enumerate(header)]
    # Deduplicate
    seen: dict[str, int] = {}
    unique_cols: list[str] = []
    for name in columns:
        count = seen.get(name, 0)
        seen[name] = count + 1
        unique_cols.append(name if count == 0 else f"{name} ({count + 1})")

    rows: list[dict[str, Any]] = []
    for raw in matrix[1:]:
        if not any(raw):
            continue
        rows.append({unique_cols[i]: (raw[i] if i < len(raw) else "") for i in range(len(unique_cols))})
    return {
        "index": index,
        "title": f"Table {index + 1}",
        "columns": unique_cols,
        "rows": rows,
    }


def parse_docx(
    source: bytes | BinaryIO,
    *,
    source_label: str | None = None,
) -> dict[str, Any]:
    if isinstance(source, bytes):
        document = Document(io.BytesIO(source))
    else:
        document = Document(source)

    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    tables: list[dict[str, Any]] = []
    table_index = 0

    # Walk body elements in order
    body = document.element.body
    for child in body.iterchildren():
        tag = child.tag.split("}")[-1]
        if tag == "p":
            paragraph = Paragraph(child, document)
            text = _para_text(paragraph)
            level = _heading_level(paragraph)
            if level is not None:
                current = {"heading": text or "Untitled", "level": level, "paragraphs": []}
                sections.append(current)
            elif text:
                if current is None:
                    current = {"heading": "Introduction", "level": 1, "paragraphs": []}
                    sections.append(current)
                current["paragraphs"].append(text)
        elif tag == "tbl":
            table = Table(child, document)
            tables.append(_table_to_dict(table, table_index))
            table_index += 1

    return {
        "kind": "document",
        "source_file": source_label or "Document",
        "sections": sections,
        "tables": tables,
    }
