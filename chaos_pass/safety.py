from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from .models import SnapshotEntry

class SafetyError(RuntimeError):
    pass

@dataclass(slots=True)
class Sandbox:
    temp: tempfile.TemporaryDirectory[str]
    path: Path

    def cleanup(self) -> None:
        self.temp.cleanup()

def _absolute_without_resolving(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path.expanduser())))

def _is_junction(path: Path) -> bool:
    checker = getattr(path, "is_junction", None)
    if checker is None:
        return False
    try:
        return bool(checker())
    except OSError:
        return False

def _is_linklike(path: Path) -> bool:
    try:
        return path.is_symlink() or _is_junction(path)
    except OSError:
        return True

def _iter_tree_without_following_links(root: Path) -> Iterator[Path]:
    if _is_linklike(root) or root.is_file():
        yield root
        return
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            entries = list(os.scandir(current))
        except OSError:
            yield current
            continue
        for entry in entries:
            path = Path(entry.path)
            if _is_linklike(path):
                yield path
                continue
            try:
                if entry.is_dir(follow_symlinks=False):
                    stack.append(path)
                else:
                    yield path
            except OSError:
                yield path

def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _link_target_text(path: Path) -> str:
    try:
        if path.is_symlink():
            return os.readlink(path)
    except OSError:
        pass
    try:
        return str(path.resolve(strict=False))
    except OSError:
        return "<unresolved>"

def snapshot_path(target: Path) -> dict[str, SnapshotEntry]:
    target = _absolute_without_resolving(target)
    if not target.exists() and not _is_linklike(target):
        raise SafetyError(f"Target does not exist: {target}")

    entries: dict[str, SnapshotEntry] = {}
    paths = _iter_tree_without_following_links(target)
    for path in paths:
        rel = path.name if target.is_file() or _is_linklike(target) else path.relative_to(target).as_posix()
        if _is_linklike(path):
            link = _link_target_text(path)
            kind = "junction" if _is_junction(path) else "symlink"
            entries[rel] = SnapshotEntry(rel, len(link.encode()), _sha256_bytes(link.encode()), kind)
        elif path.is_file():
            entries[rel] = SnapshotEntry(rel, path.stat().st_size, _sha256_file(path), "file")
        elif path.exists():
            marker = f"unreadable:{path}"
            entries[rel] = SnapshotEntry(rel, 0, _sha256_bytes(marker.encode()), "unreadable")
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

def escaping_links(root: Path) -> list[str]:
    root = _absolute_without_resolving(root)
    if _is_linklike(root):
        return [f"{root} -> {_link_target_text(root)}"]
    root_resolved = root.resolve()
    escaped: list[str] = []
    for path in _iter_tree_without_following_links(root):
        if not _is_linklike(path):
            continue
        try:
            resolved = path.resolve(strict=False)
        except OSError:
            escaped.append(str(path))
            continue
        if resolved != root_resolved and root_resolved not in resolved.parents:
            escaped.append(f"{path} -> {resolved}")
    return escaped

# Backward-compatible name used by early DROP 0003 drafts.
escaping_symlinks = escaping_links

def clone_target(target: Path, max_bytes: int) -> Sandbox:
    target = _absolute_without_resolving(target)
    if _is_linklike(target):
        raise SafetyError("Top-level symlink/junction targets require an explicit isolation adapter.")

    source_escapes = escaping_links(target)
    if source_escapes:
        preview = "; ".join(source_escapes[:5])
        raise SafetyError(
            "Target contains symlinks/junctions that leave the target tree. "
            f"Refusing to clone for destructive testing. Examples: {preview}"
        )

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
    try:
        if target.is_dir():
            shutil.copytree(target, clone, symlinks=True)
        else:
            clone.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, clone)

        escaped = escaping_links(clone)
        if escaped:
            preview = "; ".join(escaped[:5])
            raise SafetyError(
                "Disposable clone contains symlinks/junctions that escape the sandbox. "
                f"Refusing destructive testing. Examples: {preview}"
            )
        return Sandbox(temp=temp, path=clone)
    except Exception:
        temp.cleanup()
        raise

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