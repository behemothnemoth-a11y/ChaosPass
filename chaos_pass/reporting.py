from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from .models import RunReport

def write_json(report: RunReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

def _finding_block(index: int, finding) -> list[str]:
    lines = [
        f"### {index}. [{finding.status}] {finding.scenario}",
        "",
        f"- **Profile:** {finding.profile}",
        f"- **Severity:** {finding.severity}",
        f"- **Summary:** {finding.summary}",
    ]
    if finding.reproduction:
        lines += ["- **Reproduction:**"] + [f"  {i+1}. {step}" for i, step in enumerate(finding.reproduction)]
    if finding.evidence:
        lines += ["- **Evidence:**"] + [f"  - {item}" for item in finding.evidence]
    if finding.suspected_cause:
        lines.append(f"- **Suspected cause:** {finding.suspected_cause}")
    if finding.recommended_action:
        lines.append(f"- **Recommended action:** {finding.recommended_action}")
    lines.append("")
    return lines

def write_markdown(report: RunReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    counts = Counter(f.status for f in report.findings)
    lines = [
        "# Chaos Pass Report",
        "",
        f"- **Run:** {report.run_id}",
        f"- **Target:** {report.target}",
        f"- **Profile:** {report.profile}",
        f"- **Started (UTC):** {report.started_utc}",
        f"- **Finished (UTC):** {report.finished_utc}",
        f"- **Sandbox:** {report.sandbox_strategy}",
        f"- **Baseline:** {report.baseline_files} files / {report.baseline_bytes:,} bytes",
        f"- **Original integrity:** {'PASS' if report.integrity_passed else 'FAIL'}",
        "",
        "## Outcome summary",
        "",
    ]
    for status in ["CATASTROPHIC","BREAK","BEND","WEIRD","BLOCKED","SURVIVED"]:
        lines.append(f"- **{status}:** {counts.get(status, 0)}")
    lines += ["", "## Integrity verification", ""]
    if report.integrity_passed:
        lines.append("Original target matches the pre-run baseline. No test residue was detected.")
    else:
        lines.append("**ZERO-TRACE FAILURE.** Differences were detected in the original target:")
        lines += [f"- {item}" for item in report.integrity_diff]
    lines += ["", "## Findings", ""]
    for i, finding in enumerate(report.findings, 1):
        lines.extend(_finding_block(i, finding))
    if report.notes:
        lines += ["## Run notes", ""] + [f"- {note}" for note in report.notes] + [""]
    path.write_text("\n".join(lines), encoding="utf-8")
