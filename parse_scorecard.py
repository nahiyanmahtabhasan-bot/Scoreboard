"""Parse the Scorecard sheet from the Project Plan Excel file."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, BinaryIO

import pandas as pd

TEAM_MEMBERS = ["Dhaval", "Syed", "Ahamed", "Yaseen", "Vaizhnavi", "Sneha"]

PHASES = [
    "Process Flow",
    "Functionality",
    "DocType Creation",
    "Validation (@ field level)",
    "Configuration",
    "Testing",
    "Push to GIT",
    "Demo",
    "Feedback -> fixes -> testing ->git hub",
    "Production",
]

PHASE_SHORT_LABELS = {
    "Process Flow": "Process Flow",
    "Functionality": "Functionality",
    "DocType Creation": "DocType Creation",
    "Validation (@ field level)": "Validation",
    "Configuration": "Configuration",
    "Testing": "Testing",
    "Push to GIT": "Push to GIT",
    "Demo": "Demo",
    "Feedback -> fixes -> testing ->git hub": "Feedback Cycle",
    "Production": "Production",
}


def _num(value: Any) -> float | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _str(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    text = str(value).strip()
    return text or None


def _parse_module_row(df: pd.DataFrame, idx: int) -> dict[str, Any]:
    priority = _num(df.iloc[idx, 1])
    return {
        "priority": int(priority) if priority is not None else None,
        "module": _str(df.iloc[idx, 2]),
        "overall": _num(df.iloc[idx, 3]),
        "phases": {phase: _num(df.iloc[idx, 4 + i]) for i, phase in enumerate(PHASES)},
        "pct_completed": _num(df.iloc[idx, 14]),
        "total_items": _num(df.iloc[idx, 15]),
        "completed_items": _num(df.iloc[idx, 16]),
    }


def _is_ongoing_module(module: dict[str, Any]) -> bool:
    """Include modules that are in progress or not yet started; exclude fully complete."""
    pct = module.get("pct_completed")
    if pct is not None and pct >= 1.0:
        return False
    return module.get("priority") in (1, 2) and bool(module.get("module"))


def _find_section_header(df: pd.DataFrame, start: int = 0) -> int | None:
    for idx in range(start, len(df)):
        if _str(df.iloc[idx, 1]) == "Priority" and _str(df.iloc[idx, 2]) == "Modules":
            return idx
    return None


def _module_progress_section(df: pd.DataFrame) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    header_row = _find_section_header(df)
    if header_row is None:
        raise ValueError("Module progress section not found on Scorecard sheet")

    modules: list[dict[str, Any]] = []
    summary: dict[str, Any] | None = None

    for idx in range(header_row + 1, len(df)):
        module_name = _str(df.iloc[idx, 2])
        if module_name == "Total Core":
            summary = {
                "overall": _num(df.iloc[idx, 3]),
                "pct_completed": _num(df.iloc[idx, 14]),
                "total_items": _num(df.iloc[idx, 15]),
                "completed_items": _num(df.iloc[idx, 16]),
            }
            break
        if not module_name:
            continue

        row = _parse_module_row(df, idx)
        if row["priority"] not in (1, 2):
            continue
        modules.append(row)

    return modules, summary


def _team_module_rows(df: pd.DataFrame, start: int, end: int, value_key: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx in range(start, end + 1):
        module = _str(df.iloc[idx, 2])
        if not module or module == "Total Core":
            continue
        priority = _num(df.iloc[idx, 1])
        team_values = {member: _num(df.iloc[idx, 4 + i]) for i, member in enumerate(TEAM_MEMBERS)}
        rows.append(
            {
                "priority": int(priority) if priority is not None else None,
                "module": module,
                "overall": _num(df.iloc[idx, 3]),
                value_key: team_values,
            }
        )
    return rows


def _phase_team_rows(df: pd.DataFrame, start: int, end: int, value_key: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx in range(start, end + 1):
        phase = _str(df.iloc[idx, 2])
        if not phase or phase == "Modules":
            continue
        team_values = {member: _num(df.iloc[idx, 4 + i]) for i, member in enumerate(TEAM_MEMBERS)}
        rows.append(
            {
                "phase": phase,
                "overall": _num(df.iloc[idx, 3]),
                value_key: team_values,
            }
        )
    return rows


def _find_team_sections(df: pd.DataFrame) -> tuple[int, int, int, int]:
    headers = [
        idx
        for idx in range(len(df))
        if _str(df.iloc[idx, 1]) == "Priority" and _str(df.iloc[idx, 2]) == "Modules"
    ]
    if len(headers) < 2:
        return 32, 54, 58, 80

    workload_header = headers[1]
    progress_header = headers[2] if len(headers) > 2 else workload_header + 26

    def section_end(header: int) -> int:
        for idx in range(header + 1, len(df)):
            if _str(df.iloc[idx, 2]) == "Total Core":
                return idx - 1
        return header + 22

    return (
        workload_header + 1,
        section_end(workload_header),
        progress_header + 1,
        section_end(progress_header),
    )


def parse_scorecard(source: str | Path | BinaryIO, *, source_label: str | None = None) -> dict[str, Any]:
    df = pd.read_excel(source, sheet_name="Scorecard", header=None)

    if source_label:
        label = source_label
    elif isinstance(source, (str, Path)):
        label = str(Path(source).resolve())
    else:
        label = "Live spreadsheet"

    all_modules, summary = _module_progress_section(df)
    ongoing_modules = [module for module in all_modules if _is_ongoing_module(module)]
    ongoing_names = {module["module"] for module in ongoing_modules}

    workload_start, workload_end, progress_start, progress_end = _find_team_sections(df)
    team_workload = [
        row
        for row in _team_module_rows(df, workload_start, workload_end, "hours")
        if row["module"] in ongoing_names
    ]
    team_progress = [
        row
        for row in _team_module_rows(df, progress_start, progress_end, "progress")
        if row["module"] in ongoing_names
    ]

    return {
        "source_file": label,
        "source_sheet": "Scorecard",
        "summary": summary or {},
        "modules": ongoing_modules,
        "team_workload": team_workload,
        "team_progress": team_progress,
        "phase_totals": _phase_team_rows(df, 85, 94, "totals"),
        "phase_progress": _phase_team_rows(df, 97, 106, "progress"),
        "team_members": TEAM_MEMBERS,
        "phases": PHASES,
        "phase_labels": PHASE_SHORT_LABELS,
    }
