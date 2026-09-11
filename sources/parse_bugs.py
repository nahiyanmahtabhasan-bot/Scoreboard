"""Parse BugIndex sheet into bug rows + status/severity summaries."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, BinaryIO

from sources.parse_generic_sheet import parse_generic_sheet

SEVERITY_ORDER = ("Critical", "High", "Medium", "Low")
STATUS_ORDER = ("UNOPENED", "OPEN", "ACTIONED", "CLOSED")

DETAIL_FIELDS = (
    "ID",
    "Severity",
    "STATUS",
    "Modules",
    "Area",
    "Responsible",
    "Finding",
    "Steps to reproduce",
    "Actual result",
    "Expected result",
    "Why it matters",
    "CORRECTION / EXPLANATION",
    "Bug/ No Bug",
    "Evidence",
)

LIST_FIELDS = (
    "ID",
    "Severity",
    "STATUS",
    "Modules",
    "Area",
    "Responsible",
    "Finding",
    "Bug/ No Bug",
)


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalize_status(raw: Any) -> str:
    """Blank STATUS means the finding has not been touched yet (Unopened)."""
    text = _text(raw).upper()
    if not text:
        return "UNOPENED"
    if text in {"UNOPENED", "UNTOUCHED", "NOT OPENED", "NOT STARTED", "BLANK"}:
        return "UNOPENED"
    if text in {"CLOSED", "CLOSE", "DONE", "RESOLVED", "FIXED", "COMPLETE", "COMPLETED"}:
        return "CLOSED"
    if text in {"ACTIONED", "ACTIONED.", "IN PROGRESS", "WIP"}:
        return "ACTIONED"
    if text in {"OPEN", "NEW", "PENDING", "REOPENED"}:
        return "OPEN"
    if "ACTION" in text:
        return "ACTIONED"
    if "UNOPEN" in text or "UNTOUCH" in text:
        return "UNOPENED"
    if "OPEN" in text:
        return "OPEN"
    if "CLOSE" in text or "RESOLV" in text or "DONE" in text:
        return "CLOSED"
    return text


def normalize_severity(raw: Any) -> str:
    text = _text(raw)
    if not text:
        return "Unknown"
    lower = text.lower()
    for name in SEVERITY_ORDER:
        if lower == name.lower():
            return name
    return text


def _status_tone(status: str) -> str:
    if status == "UNOPENED":
        return "tbc"
    if status == "OPEN":
        return "open"
    if status == "ACTIONED":
        return "wip"
    if status == "CLOSED":
        return "done"
    return "neutral"


def _severity_tone(severity: str) -> str:
    lower = severity.lower()
    if lower == "critical":
        return "critical"
    if lower == "high":
        return "high"
    if lower == "medium":
        return "medium"
    if lower == "low":
        return "low"
    return "neutral"


def _build_pivot(bugs: list[dict[str, Any]]) -> dict[str, Any]:
    """Severity → module → status counts (same shape as the sheet pivot)."""
    matrix: dict[str, dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
    severity_totals: dict[str, Counter] = defaultdict(Counter)
    status_totals: Counter = Counter()

    for bug in bugs:
        severity = bug["severity"]
        module = bug["module"] or "(none)"
        status = bug["status"]
        matrix[severity][module][status] += 1
        severity_totals[severity][status] += 1
        status_totals[status] += 1

    groups = []
    for severity in (*SEVERITY_ORDER, *(s for s in matrix if s not in SEVERITY_ORDER)):
        if severity not in matrix:
            continue
        modules = []
        for module in sorted(matrix[severity].keys(), key=lambda m: (m == "(none)", m.lower())):
            counts = {s: int(matrix[severity][module].get(s, 0)) for s in STATUS_ORDER}
            counts["total"] = sum(counts.values())
            modules.append({"module": module, "counts": counts})
        tot = {s: int(severity_totals[severity].get(s, 0)) for s in STATUS_ORDER}
        tot["total"] = sum(tot.values())
        groups.append({"severity": severity, "modules": modules, "totals": tot})

    grand = {s: int(status_totals.get(s, 0)) for s in STATUS_ORDER}
    grand["total"] = sum(grand.values())
    return {"groups": groups, "grand_total": grand, "statuses": list(STATUS_ORDER)}


def parse_bugs(
    source: str | BinaryIO,
    *,
    tab: str = "BugIndex",
    source_label: str | None = None,
) -> dict[str, Any]:
    raw = parse_generic_sheet(
        source,
        tab=tab,
        max_rows=2000,
        source_label=source_label or "Bug Index",
    )
    bugs: list[dict[str, Any]] = []
    for row in raw.get("rows") or []:
        bug_id = _text(row.get("ID"))
        if not bug_id:
            continue
        status = normalize_status(row.get("STATUS"))
        severity = normalize_severity(row.get("Severity"))
        module = _text(row.get("Modules"))
        finding = _text(row.get("Finding"))
        bugs.append(
            {
                "id": bug_id,
                "severity": severity,
                "status": status,
                "module": module,
                "area": _text(row.get("Area")),
                "responsible": _text(row.get("Responsible")).replace("\n", " / "),
                "finding": finding,
                "verdict": _text(row.get("Bug/ No Bug")),
                "severity_tone": _severity_tone(severity),
                "status_tone": _status_tone(status),
                "list": {field: _text(row.get(field)) for field in LIST_FIELDS},
                "details": {field: _text(row.get(field)) for field in DETAIL_FIELDS},
            }
        )

    # Unopened / Open / Critical first, then Actioned, then Closed
    sev_rank = {name: i for i, name in enumerate(SEVERITY_ORDER)}
    status_rank = {"UNOPENED": 0, "OPEN": 1, "ACTIONED": 2, "CLOSED": 3}

    def sort_key(bug: dict[str, Any]) -> tuple:
        return (
            status_rank.get(bug["status"], 9),
            sev_rank.get(bug["severity"], 9),
            bug["id"],
        )

    bugs.sort(key=sort_key)

    by_status = Counter(b["status"] for b in bugs)
    by_severity = Counter(b["severity"] for b in bugs)
    by_module = Counter(b["module"] or "(none)" for b in bugs)
    by_verdict = Counter(b["verdict"] or "(blank)" for b in bugs)

    summary = {
        "total": len(bugs),
        "by_status": {s: int(by_status.get(s, 0)) for s in STATUS_ORDER},
        "by_severity": {
            s: int(by_severity.get(s, 0))
            for s in (*SEVERITY_ORDER, *(k for k in by_severity if k not in SEVERITY_ORDER))
        },
        "by_module": dict(sorted(by_module.items(), key=lambda kv: (-kv[1], kv[0].lower()))),
        "by_verdict": dict(by_verdict),
        "open_critical": sum(
            1 for b in bugs if b["status"] == "OPEN" and b["severity"] == "Critical"
        ),
    }

    return {
        "kind": "bugs",
        "mode": "bugs",
        "source_file": raw.get("source_file") or source_label or "Bug Index",
        "source_sheet": raw.get("source_sheet") or tab,
        "sheet_names": raw.get("sheet_names") or [],
        "bugs": bugs,
        "summary": summary,
        "pivot": _build_pivot(bugs),
        "filters": {
            "statuses": list(STATUS_ORDER),
            "severities": [
                s
                for s in (*SEVERITY_ORDER, *(k for k in by_severity if k not in SEVERITY_ORDER))
                if by_severity.get(s)
            ],
            "modules": [m for m, _ in sorted(by_module.items(), key=lambda kv: kv[0].lower())],
        },
    }
