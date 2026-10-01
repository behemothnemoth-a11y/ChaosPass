from __future__ import annotations

import json
from pathlib import Path

BUILTIN_FALLBACKS = {
    "expert-baseline": [
        "inventory",
        "adapter:expert-domain",
        "adapter:expert-qa",
        "adapter:expert-ux",
        "adapter:expert-accessibility",
        "adapter:expert-performance-reliability",
        "adapter:expert-security-safety",
    ],
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

def profile_search_dirs() -> list[Path]:
    here = Path(__file__).resolve()
    return [Path.cwd() / "profiles", here.parent.parent / "profiles"]

def load_profile(name: str) -> list[str]:
    for directory in profile_search_dirs():
        path = directory / f"{name}.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            scenarios = data.get("scenarios", [])
            if not isinstance(scenarios, list):
                raise ValueError(f"{path}: scenarios must be a list")
            return [str(item) for item in scenarios]
    try:
        return list(BUILTIN_FALLBACKS[name])
    except KeyError as exc:
        known = ", ".join(sorted(BUILTIN_FALLBACKS))
        raise ValueError(f"Unknown profile '{name}'. Known: {known}") from exc

def profile_names() -> list[str]:
    return sorted(BUILTIN_FALLBACKS)
