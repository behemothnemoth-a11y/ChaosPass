from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BUILTIN_FALLBACKS = {
    "expert-baseline": ["inventory", "adapter:expert-domain", "adapter:expert-qa", "adapter:expert-ux", "adapter:expert-accessibility", "adapter:expert-performance-reliability", "adapter:expert-security-safety"],
    "power-user": ["inventory", "duplicate_wave", "large_blob"],
    "chaos-goblin": ["rapid_churn", "duplicate_wave", "rename_churn"],
    "boundary-hunter": ["deep_nesting", "unicode_names", "large_blob"],
    "wrong-way-user": ["unicode_names", "rename_churn", "adapter:wrong_way"],
    "ui-gremlin": ["adapter:ui"],
    "performance-murderer": ["duplicate_wave", "large_blob", "soak_loop"],
    "persistence-demon": ["adapter:persistence"],
    "state-breaker": ["adapter:state"],
    "charlie": ["charlie_workflow", "adapter:charlie"],
    "random-chaos": ["random_chain"],
    "wildcard": ["wildcard_chain"],
    "soak-monster": ["soak_loop"],
    "regression-archaeologist": ["adapter:regression"],
    "full-chaos-pass": ["final_boss"],
}

REQUIRED_PROFILE_FIELDS = {
    "schema_version", "id", "display_name", "category",
    "mission", "mindset", "attack_surface_priority", "opening_moves",
    "escalation_ladder", "signature_tactics", "combination_rules",
    "handoff_triggers", "stop_conditions", "required_evidence", "scenarios",
}

def profile_search_dirs() -> list[Path]:
    here = Path(__file__).resolve()
    return [Path.cwd() / "profiles", here.parent.parent / "profiles"]

def _validate_profile(data: dict[str, Any], source: str) -> dict[str, Any]:
    missing = sorted(REQUIRED_PROFILE_FIELDS - set(data))
    if missing:
        raise ValueError(f"{source}: missing profile fields: {', '.join(missing)}")
    list_fields = [
        "attack_surface_priority", "opening_moves", "escalation_ladder",
        "signature_tactics", "combination_rules", "handoff_triggers",
        "stop_conditions", "required_evidence", "scenarios",
    ]
    for key in list_fields:
        if not isinstance(data[key], list) or not data[key]:
            raise ValueError(f"{source}: {key} must be a non-empty list")
    return data

def load_profile_definition(name: str) -> dict[str, Any]:
    for directory in profile_search_dirs():
        path = directory / f"{name}.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError(f"{path}: profile root must be an object")
            return _validate_profile(data, str(path))
    try:
        scenarios = BUILTIN_FALLBACKS[name]
    except KeyError as exc:
        known = ", ".join(sorted(BUILTIN_FALLBACKS))
        raise ValueError(f"Unknown profile '{name}'. Known: {known}") from exc
    return {
        "schema_version": "fallback",
        "id": name,
        "display_name": name.replace("-", " ").title(),
        "category": "fallback",
        "mission": "Execute the packaged scenario set.",
        "mindset": "Follow the repository playbook when available.",
        "attack_surface_priority": ["adapter-defined"],
        "opening_moves": ["Load the target-specific adapter."],
        "escalation_ladder": [{"level": 0, "name": "Fallback", "actions": ["Run built-in scenarios."]}],
        "signature_tactics": [{"name": "Fallback scenarios", "purpose": "Maintain runner availability.", "actions": list(scenarios), "watch_for": ["findings"]}],
        "combination_rules": ["Follow the Zero-Trace Contract."],
        "handoff_triggers": ["A finding requires another profile."],
        "stop_conditions": ["Isolation cannot be guaranteed."],
        "required_evidence": ["reproduction", "integrity result"],
        "scenarios": list(scenarios),
    }

def load_profile(name: str) -> list[str]:
    return [str(item) for item in load_profile_definition(name)["scenarios"]]

def profile_names() -> list[str]:
    return sorted(BUILTIN_FALLBACKS)