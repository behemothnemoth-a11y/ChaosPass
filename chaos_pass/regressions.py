from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

@dataclass(slots=True)
class RegressionCase:
    case_id: str
    title: str
    historical_symptom: str
    current_expectation: str
    regression_test: str
    source_file: str

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.case_id,
            "title": self.title,
            "historical_symptom": self.historical_symptom,
            "current_expectation": self.current_expectation,
            "regression_test": self.regression_test,
            "source_file": self.source_file,
        }

def _target_root(target: Path) -> Path:
    return target if target.is_dir() else target.parent

def regression_files(target: Path) -> list[Path]:
    root = _target_root(target).resolve()
    directory = root / "regressions"
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.glob("*.json") if p.is_file())

def load_regression_cases(target: Path) -> list[RegressionCase]:
    cases: list[RegressionCase] = []
    for path in regression_files(target):
        data = json.loads(path.read_text(encoding="utf-8"))
        raw_cases = data.get("cases", []) if isinstance(data, dict) else []
        if not isinstance(raw_cases, list):
            continue
        for raw in raw_cases:
            if not isinstance(raw, dict):
                continue
            case_id = str(raw.get("id", "")).strip()
            title = str(raw.get("title", "")).strip()
            if not case_id or not title:
                continue
            cases.append(RegressionCase(
                case_id=case_id,
                title=title,
                historical_symptom=str(raw.get("historical_symptom", "")),
                current_expectation=str(raw.get("current_expectation", "")),
                regression_test=str(raw.get("regression_test", "")),
                source_file=str(path),
            ))
    return cases