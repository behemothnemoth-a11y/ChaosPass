from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .models import SnapshotEntry

class SafetyError(RuntimeError):
    pass

@dataclass(slots=True)
class Sandbox:
    temp: tempfile.TemporaryDirectory[str]
    path: Path

    def cleanup(self) -> None:
        self.temp.cleanup()

def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def snapshot_path(target: Path) -> dict[str, SnapshotEntry]:
    target = target.resolve()
    if not target.exists():
        raise SafetyError(f"Target does not exist: {target}")

    entries: dict[str, SnapshotEntry] = {}
    paths = [target] if target.is_file() or target.is_symlink() else target.rglob("*")
    for path in paths:
        if path.is_dir() and not path.is_symlink():
            continue
        rel = path.name if target.is_file() else path.relative_to(target).as_posix()
        if path.is_symlink():
            link = os.readlink(path)
            entries[rel] = SnapshotEntry(rel, len(link.encode()), _sha256_bytes(link.encode()), "symlink")
        elif path.is_file():
            entries[rel] = SnapshotEntry(rel, path.stat().st_size, _sha256_file(path), "file")
    return entries

def snapshot_size(snapshot: dict[str, SnapshotEntry]) -> int:
    return sum(entry.size for entry in snapshot.values())

def ensure_output_outside_target(target: Path, output: Path) -> None:
    target = target.resolve()
    output = output.resolve()
    if target.is_file():
        if output == target.parent:
            raise SafetyError("Report output may not be the target file's own directory.")
        return
    try:
        output.relative_to(target)
    except ValueError:
        return
    raise SafetyError("Report output must be outside the target tree to preserve zero-trace integrity.")

def clone_target(target: Path, max_bytes: int) -> Sandbox:
    target = target.resolve()
    baseline = snapshot_path(target)
    total = snapshot_size(baseline)
    if total > max_bytes:
        raise SafetyError(
            f"Target is {total:,} bytes; clone cap is {max_bytes:,}. "
            "Increase --max-clone-bytes only when sufficient disposable space exists."
        )

    temp = tempfile.TemporaryDirectory(prefix="chaos-pass-")
    root = Path(temp.name)
    clone = root / target.name

    if target.is_symlink():
        raise SafetyError("Top-level symlink targets require an explicit adapter.")
    if target.is_dir():
        shutil.copytree(target, clone, symlinks=True)
    else:
        clone.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, clone)
    return Sandbox(temp=temp, path=clone)

def diff_snapshots(
    before: dict[str, SnapshotEntry],
    after: dict[str, SnapshotEntry],
) -> list[str]:
    differences: list[str] = []
    all_paths = sorted(set(before) | set(after))
    for rel in all_paths:
        left = before.get(rel)
        right = after.get(rel)
        if left is None:
            differences.append(f"ADDED {rel}")
        elif right is None:
            differences.append(f"REMOVED {rel}")
        elif (left.size, left.sha256, left.kind) != (right.size, right.sha256, right.kind):
            differences.append(f"CHANGED {rel}")
    return differences
