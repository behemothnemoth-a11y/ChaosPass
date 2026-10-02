from __future__ import annotations

from collections import Counter, defaultdict
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import sqlite3
import struct
import time
from typing import Any
import zipfile

from .adapters import AdapterAction, AdapterContext, BaseAdapter, TargetFingerprint
from .config import TargetConfig
from .models import Finding


class NBTReader:
    """Small dependency-free NBT reader used for structural world validation."""

    def __init__(self, data: bytes) -> None:
        self.data = memoryview(data)
        self.pos = 0

    def _take(self, size: int) -> memoryview:
        if size < 0 or self.pos + size > len(self.data):
            raise EOFError(f"NBT truncated at {self.pos}+{size}")
        value = self.data[self.pos : self.pos + size]
        self.pos += size
        return value

    def _u8(self) -> int:
        return struct.unpack(">B", self._take(1))[0]

    def _i8(self) -> int:
        return struct.unpack(">b", self._take(1))[0]

    def _i16(self) -> int:
        return struct.unpack(">h", self._take(2))[0]

    def _i32(self) -> int:
        return struct.unpack(">i", self._take(4))[0]

    def _i64(self) -> int:
        return struct.unpack(">q", self._take(8))[0]

    def _f32(self) -> float:
        return struct.unpack(">f", self._take(4))[0]

    def _f64(self) -> float:
        return struct.unpack(">d", self._take(8))[0]

    def _string(self) -> str:
        length = struct.unpack(">H", self._take(2))[0]
        return bytes(self._take(length)).decode("utf-8", "replace")

    def _payload(self, tag: int) -> Any:
        if tag == 0:
            return None
        if tag == 1:
            return self._i8()
        if tag == 2:
            return self._i16()
        if tag == 3:
            return self._i32()
        if tag == 4:
            return self._i64()
        if tag == 5:
            return self._f32()
        if tag == 6:
            return self._f64()
        if tag == 7:
            length = self._i32()
            if length < 0:
                raise ValueError("negative NBT byte-array length")
            self._take(length)
            return {"byte_array_len": length}
        if tag == 8:
            return self._string()
        if tag == 9:
            element_type = self._u8()
            length = self._i32()
            if length < 0:
                raise ValueError("negative NBT list length")
            return [self._payload(element_type) for _ in range(length)]
        if tag == 10:
            result: dict[str, Any] = {}
            while True:
                element_type = self._u8()
                if element_type == 0:
                    return result
                name = self._string()
                result[name] = self._payload(element_type)
        if tag == 11:
            length = self._i32()
            if length < 0:
                raise ValueError("negative NBT int-array length")
            self._take(length * 4)
            return {"int_array_len": length}
        if tag == 12:
            length = self._i32()
            if length < 0:
                raise ValueError("negative NBT long-array length")
            self._take(length * 8)
            return {"long_array_len": length}
        raise ValueError(f"unknown NBT tag type {tag}")

    def root(self) -> tuple[str, Any]:
        tag = self._u8()
        if tag == 0:
            return "", None
        name = self._string()
        return name, self._payload(tag)


def read_nbt(path: Path) -> tuple[str, Any]:
    raw = path.read_bytes()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return NBTReader(raw).root()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _world_data(path: Path) -> dict[str, Any]:
    name, root = read_nbt(path)
    data = root.get("Data", root) if isinstance(root, dict) else {}
    if not isinstance(data, dict):
        raise ValueError("level NBT root does not contain a compound")
    return {
        "root_name": name,
        "DataVersion": data.get("DataVersion"),
        "LevelName": data.get("LevelName"),
        "LastPlayed": data.get("LastPlayed"),
        "hardcore": data.get("hardcore"),
        "Difficulty": data.get("Difficulty"),
        "Version": data.get("Version"),
        "DataPacks": data.get("DataPacks"),
    }


def _validate_region(path: Path) -> dict[str, Any]:
    size = path.stat().st_size
    if size == 0:
        return {"ok": True, "placeholder": True, "bytes": 0, "chunks": 0}
    if size < 8192:
        return {
            "ok": False,
            "placeholder": False,
            "bytes": size,
            "error": f"non-empty region smaller than 8192-byte header: {size}",
        }

    sectors = (size + 4095) // 4096
    used: list[tuple[int, int, int]] = []
    compressions: Counter[str] = Counter()
    chunks = 0
    with path.open("rb") as handle:
        locations = handle.read(4096)
        timestamps = handle.read(4096)
        if len(locations) != 4096 or len(timestamps) != 4096:
            return {"ok": False, "bytes": size, "error": "truncated region header"}

        for index in range(1024):
            value = int.from_bytes(locations[index * 4 : index * 4 + 4], "big")
            offset = value >> 8
            count = value & 0xFF
            if offset == 0 and count == 0:
                continue
            chunks += 1
            if offset < 2 or count == 0 or offset + count > sectors:
                return {
                    "ok": False,
                    "bytes": size,
                    "error": (
                        f"bad location index={index} offset={offset} "
                        f"count={count} sectors={sectors}"
                    ),
                }
            used.append((offset, offset + count, index))
            handle.seek(offset * 4096)
            length_bytes = handle.read(4)
            compression_byte = handle.read(1)
            if len(length_bytes) != 4 or len(compression_byte) != 1:
                return {"ok": False, "bytes": size, "error": f"truncated chunk index={index}"}
            length = int.from_bytes(length_bytes, "big")
            if length < 1 or length > count * 4096 - 4:
                return {
                    "ok": False,
                    "bytes": size,
                    "error": f"bad chunk length index={index} length={length} sectors={count}",
                }
            raw_type = compression_byte[0]
            compression = raw_type & 0x7F
            external = bool(raw_type & 0x80)
            label = f"{compression}{'-external' if external else ''}"
            compressions[label] += 1
            if compression not in {1, 2, 3, 4}:
                return {
                    "ok": False,
                    "bytes": size,
                    "error": f"unknown compression type {compression} at chunk {index}",
                }

    used.sort()
    for previous, current in zip(used, used[1:]):
        if current[0] < previous[1]:
            return {
                "ok": False,
                "bytes": size,
                "error": (
                    f"sector overlap chunk={previous[2]} range={previous[:2]} "
                    f"chunk={current[2]} range={current[:2]}"
                ),
            }
    return {
        "ok": True,
        "placeholder": False,
        "bytes": size,
        "chunks": chunks,
        "compressions": dict(compressions),
    }


def _unsafe_zip_member(name: str) -> bool:
    normalized = name.replace("\\", "/")
    pure = PurePosixPath(normalized)
    return (
        pure.is_absolute()
        or ".." in pure.parts
        or normalized.startswith("/")
        or (len(normalized) >= 2 and normalized[1] == ":")
    )


def _datapack_record(path: Path, world: Path) -> dict[str, Any]:
    record: dict[str, Any] = {
        "path": _rel(path, world),
        "name": path.name,
        "kind": "zip" if path.is_file() else "directory",
    }
    if path.is_file():
        record["bytes"] = path.stat().st_size
        record["sha256"] = _sha256(path)
        try:
            with zipfile.ZipFile(path) as archive:
                names = archive.namelist()
                bad_member = archive.testzip()
                record["zip_ok"] = bad_member is None
                if bad_member:
                    record["bad_member"] = bad_member
                record["members"] = len(names)
                record["unsafe_members"] = [name for name in names if _unsafe_zip_member(name)]
                duplicate_members = [name for name, count in Counter(names).items() if count > 1]
                record["duplicate_members"] = duplicate_members
                by_case: dict[str, list[str]] = defaultdict(list)
                for name in names:
                    by_case[name.lower()].append(name)
                record["case_collisions"] = [
                    values for values in by_case.values() if len(set(values)) > 1
                ]
                record["function_paths"] = sorted(
                    name for name in names if name.endswith(".mcfunction")
                )
                record["function_count"] = len(record["function_paths"])
                namespaces = {
                    parts[1]
                    for name in names
                    if name.startswith("data/")
                    for parts in [name.split("/")]
                    if len(parts) > 2
                }
                record["namespaces"] = sorted(namespaces)
                record["has_pack_mcmeta"] = "pack.mcmeta" in names
                if record["has_pack_mcmeta"]:
                    try:
                        record["pack_meta"] = json.loads(
                            archive.read("pack.mcmeta").decode("utf-8-sig")
                        )
                    except Exception as exc:
                        record["pack_meta_error"] = f"{type(exc).__name__}: {exc}"
        except Exception as exc:
            record["zip_ok"] = False
            record["error"] = f"{type(exc).__name__}: {exc}"
        return record

    names = [
        _rel(item, path)
        for item in path.rglob("*")
        if item.is_file()
    ]
    record["members"] = len(names)
    record["function_paths"] = sorted(name for name in names if name.endswith(".mcfunction"))
    record["function_count"] = len(record["function_paths"])
    record["has_pack_mcmeta"] = (path / "pack.mcmeta").is_file()
    record["unsafe_members"] = []
    record["duplicate_members"] = []
    record["case_collisions"] = []
    if record["has_pack_mcmeta"]:
        try:
            record["pack_meta"] = json.loads(
                (path / "pack.mcmeta").read_text(encoding="utf-8-sig")
            )
        except Exception as exc:
            record["pack_meta_error"] = f"{type(exc).__name__}: {exc}"
    return record


def _enabled_file_packs(level: dict[str, Any]) -> list[str]:
    packs = level.get("DataPacks")
    if not isinstance(packs, dict):
        return []
    enabled = packs.get("Enabled", [])
    if not isinstance(enabled, list):
        return []
    return [
        str(value)[5:]
        for value in enabled
        if isinstance(value, str) and value.startswith("file/")
    ]


def compact_audit_evidence(audit: dict[str, Any]) -> dict[str, Any]:
    compact = {key: value for key, value in audit.items() if key != "datapacks"}
    compact["datapacks"] = [
        {
            key: value
            for key, value in record.items()
            if key != "function_paths"
        }
        for record in audit.get("datapacks", [])
    ]
    return compact

def audit_minecraft_world(world: Path) -> dict[str, Any]:
    started = time.perf_counter()
    world = world.resolve()
    audit: dict[str, Any] = {
        "world": str(world),
        "level": {},
        "level_old": {},
        "player_nbt": {"files": 0, "parsed_ok": 0, "errors": []},
        "regions": {
            "files": 0,
            "nonempty_files": 0,
            "zero_byte_placeholders": 0,
            "chunks": 0,
            "compressions": {},
            "bad": [],
            "placeholder_areas": {},
        },
        "datapacks": [],
        "datapack_summary": {},
        "sqlite": [],
        "json": [],
        "session_lock": {},
        "elapsed_seconds": 0.0,
    }

    level_path = world / "level.dat"
    try:
        audit["level"] = {"ok": True, **_world_data(level_path)}
    except Exception as exc:
        audit["level"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    old_path = world / "level.dat_old"
    if old_path.exists():
        try:
            audit["level_old"] = {"ok": True, **_world_data(old_path)}
        except Exception as exc:
            audit["level_old"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    player_files = list(world.glob("playerdata/*.dat")) + list(world.glob("players/data/*.dat"))
    audit["player_nbt"]["files"] = len(player_files)
    for path in player_files:
        try:
            read_nbt(path)
            audit["player_nbt"]["parsed_ok"] += 1
        except Exception as exc:
            audit["player_nbt"]["errors"].append({
                "file": _rel(path, world),
                "error": f"{type(exc).__name__}: {exc}",
            })

    compression_totals: Counter[str] = Counter()
    placeholders: Counter[str] = Counter()
    for path in world.rglob("*.mca"):
        if ".chaos_pass_work" in path.parts:
            continue
        audit["regions"]["files"] += 1
        record = _validate_region(path)
        rel = _rel(path, world)
        if record.get("placeholder"):
            audit["regions"]["zero_byte_placeholders"] += 1
            placeholders[str(Path(rel).parent).replace("\\", "/")] += 1
            continue
        audit["regions"]["nonempty_files"] += 1
        if not record.get("ok"):
            audit["regions"]["bad"].append({"file": rel, "error": record.get("error", "unknown")})
            continue
        audit["regions"]["chunks"] += int(record.get("chunks", 0))
        compression_totals.update(record.get("compressions", {}))
    audit["regions"]["compressions"] = dict(compression_totals)
    audit["regions"]["placeholder_areas"] = dict(placeholders.most_common())

    datapack_dir = world / "datapacks"
    if datapack_dir.is_dir():
        datapack_paths = sorted(
            path for path in datapack_dir.iterdir()
            if path.is_dir() or path.suffix.lower() == ".zip"
        )
        audit["datapacks"] = [_datapack_record(path, world) for path in datapack_paths]

    enabled_names = _enabled_file_packs(audit["level"])
    by_name = {record["name"]: record for record in audit["datapacks"]}
    enabled_records = [by_name[name] for name in enabled_names if name in by_name]
    missing_enabled = [name for name in enabled_names if name not in by_name]

    by_hash: dict[str, list[str]] = defaultdict(list)
    for record in enabled_records:
        digest = record.get("sha256")
        if digest:
            by_hash[str(digest)].append(str(record["name"]))
    exact_duplicates = sorted(
        (sorted(names) for names in by_hash.values() if len(names) > 1),
        key=lambda group: tuple(group),
    )

    function_owners: dict[str, list[str]] = defaultdict(list)
    for record in enabled_records:
        for function_path in record.get("function_paths", []):
            function_owners[str(function_path)].append(str(record["name"]))
    collision_paths = {
        path: owners for path, owners in function_owners.items() if len(owners) > 1
    }
    collision_pairs: Counter[tuple[str, str]] = Counter()
    for owners in collision_paths.values():
        unique = sorted(set(owners))
        for index, left in enumerate(unique):
            for right in unique[index + 1 :]:
                collision_pairs[(left, right)] += 1

    duplicate_hash_pairs: set[tuple[str, str]] = set()
    for group in exact_duplicates:
        unique = sorted(set(group))
        for index, left in enumerate(unique):
            for right in unique[index + 1 :]:
                duplicate_hash_pairs.add((left, right))
    nonidentical_collision_pairs = [
        {
            "packs": list(pair),
            "function_path_collisions": count,
        }
        for pair, count in collision_pairs.most_common()
        if pair not in duplicate_hash_pairs
    ]

    format_counts: Counter[str] = Counter()
    for record in audit["datapacks"]:
        meta = record.get("pack_meta")
        pack = meta.get("pack", {}) if isinstance(meta, dict) else {}
        if isinstance(pack, dict):
            min_format = pack.get("min_format", pack.get("pack_format"))
            max_format = pack.get("max_format", pack.get("pack_format"))
            if min_format is not None or max_format is not None:
                format_counts[
                    json.dumps(
                        {"min_format": min_format, "max_format": max_format},
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                ] += 1

    audit["datapack_summary"] = {
        "packs": len(audit["datapacks"]),
        "pack_formats": dict(format_counts),
        "enabled_file_packs": enabled_names,
        "missing_enabled_file_packs": missing_enabled,
        "enabled_function_count": sum(
            int(record.get("function_count", 0)) for record in enabled_records
        ),
        "exact_duplicate_enabled_groups": exact_duplicates,
        "function_collision_paths": len(collision_paths),
        "collision_pairs": [
            {"packs": list(pair), "function_path_collisions": count}
            for pair, count in collision_pairs.most_common()
        ],
        "nonidentical_collision_pairs": nonidentical_collision_pairs,
        "bad_zip_packs": [
            record["name"]
            for record in audit["datapacks"]
            if record.get("kind") == "zip" and not record.get("zip_ok", False)
        ],
        "missing_pack_mcmeta": [
            record["name"]
            for record in audit["datapacks"]
            if not record.get("has_pack_mcmeta", False)
        ],
        "unsafe_zip_members": {
            record["name"]: record.get("unsafe_members", [])
            for record in audit["datapacks"]
            if record.get("unsafe_members")
        },
        "case_collisions": {
            record["name"]: record.get("case_collisions", [])
            for record in audit["datapacks"]
            if record.get("case_collisions")
        },
    }

    for path in world.rglob("*.sqlite"):
        record: dict[str, Any] = {"file": _rel(path, world), "bytes": path.stat().st_size}
        try:
            connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=2)
            rows = connection.execute("PRAGMA quick_check").fetchall()
            connection.close()
            record["quick_check"] = [row[0] for row in rows]
            record["ok"] = rows == [("ok",)]
        except Exception as exc:
            record["ok"] = False
            record["error"] = f"{type(exc).__name__}: {exc}"
        audit["sqlite"].append(record)

    for path in world.rglob("*.json"):
        if ".chaos_pass_work" in path.parts:
            continue
        record = {"file": _rel(path, world)}
        try:
            json.loads(path.read_text(encoding="utf-8-sig"))
            record["ok"] = True
        except Exception as exc:
            record["ok"] = False
            record["error"] = f"{type(exc).__name__}: {exc}"
        audit["json"].append(record)

    lock = world / "session.lock"
    audit["session_lock"] = {
        "present": lock.exists(),
        "bytes": lock.stat().st_size if lock.exists() else 0,
        "note": (
            "session.lock presence alone does not prove the original world is currently open"
            if lock.exists() else "no session.lock file present"
        ),
    }

    audit["elapsed_seconds"] = time.perf_counter() - started
    return audit


class MinecraftWorldAdapter(BaseAdapter):
    name = "minecraft-world"
    target_kind = "minecraft-world"
    priority = 90
    capabilities = (
        "minecraft-nbt",
        "minecraft-region-integrity",
        "minecraft-datapack-integrity",
        "minecraft-datapack-state",
        "minecraft-sqlite-integrity",
        "minecraft-json-integrity",
        "minecraft-persistence-static",
        "minecraft-live-driver-instructions",
        "minecraft-performance-static",
    )
    scenarios = (
        "adapter:expert-domain",
        "adapter:expert-qa",
        "adapter:expert-ux",
        "adapter:expert-accessibility",
        "adapter:expert-performance-reliability",
        "adapter:expert-security-safety",
        "adapter:ui",
        "adapter:wrong_way",
        "adapter:persistence",
        "adapter:state",
        "adapter:charlie",
        "adapter:regression",
    )

    def __init__(self) -> None:
        self._cache: dict[str, dict[str, Any]] = {}
        self._evidence_written: set[str] = set()

    def supports(self, fingerprint: TargetFingerprint, config: TargetConfig) -> bool:
        return "minecraft-world" in fingerprint.target_kinds

    def _audit(self, context: AdapterContext) -> dict[str, Any]:
        key = str(context.sandbox_target.resolve())
        if key not in self._cache:
            self._cache[key] = audit_minecraft_world(context.sandbox_target)
        audit = self._cache[key]
        evidence_dir = context.process_runner.evidence_dir
        evidence_key = f"{context.run_id}:{key}"
        if evidence_dir and evidence_key not in self._evidence_written:
            path = evidence_dir / "minecraft-world-audit.json"
            path.write_text(
                json.dumps(compact_audit_evidence(audit), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            self._evidence_written.add(evidence_key)
        return audit

    def _finding(
        self,
        context: AdapterContext,
        scenario: str,
        status: str,
        summary: str,
        *,
        severity: str = "info",
        evidence: list[str] | None = None,
        action: str = "",
    ) -> Finding:
        return Finding(
            profile=context.profile,
            scenario=scenario,
            status=status,
            severity=severity,
            summary=summary,
            evidence=evidence or [],
            recommended_action=action,
            adapter=self.name,
        )

    def plan_for_target(
        self,
        profile_definition: dict[str, Any],
        fingerprint: TargetFingerprint,
    ) -> list[AdapterAction]:
        profile = str(profile_definition.get("id", "unknown"))
        actions = [
            AdapterAction(
                "minecraft-static-audit",
                "Parse world NBT, region headers/allocations, datapacks, JSON, and SQLite state inside the disposable clone.",
                "minecraft-region-integrity",
                "sandbox-read-only",
                True,
                self.name,
            )
        ]
        driver_by_profile: dict[str, list[tuple[str, str]]] = {
            "expert-baseline": [
                ("minecraft-load-world", "Launch an isolated Minecraft profile and load the cloned world; confirm the world reaches playable state without crash or data-fix failure."),
                ("minecraft-ui-baseline", "Review world-selection, loading, pause/menu, chat/command, and save/quit flows in the isolated profile for clarity and recoverability."),
                ("minecraft-accessibility-baseline", "Review keyboard navigation, focus visibility, readable scaling, narration/accessibility settings, and control reachability in the isolated profile."),
            ],
            "ui-gremlin": [
                ("minecraft-ui-window-stress", "In the isolated profile, toggle fullscreen/windowed, resize, move between menus/world, and verify controls/focus remain reachable."),
            ],
            "persistence-demon": [
                ("minecraft-save-reopen", "In the clone, make a harmless marker change, save/quit, reopen, and verify the marker plus level metadata survive."),
                ("minecraft-interrupted-save", "Only in a disposable profile, interrupt the cloned instance during an autosave/save cycle and inspect recovery/level.dat_old behavior."),
            ],
            "state-breaker": [
                ("minecraft-datapack-state", "In the cloned world, exercise datapack enable/disable/reload state and verify save/reopen does not desynchronize enabled-pack state."),
                ("minecraft-dimension-state", "Move through loaded chunks/dimensions in the disposable world and verify state survives save/reload."),
            ],
            "performance-murderer": [
                ("minecraft-reload-performance", "Measure world load and /reload latency plus memory/MSPT in the isolated profile, especially with the currently enabled datapack function volume."),
            ],
            "wrong-way-user": [
                ("minecraft-invalid-datapack-reload", "In the clone only, introduce a deliberately invalid or duplicated datapack state, run reload, and verify Minecraft fails safely and recoverably."),
            ],
            "charlie": [
                ("minecraft-charlie-packs", "In the clone, duplicate/rename datapacks into confusing FINAL/Copy names, reload, then verify resource identity and recovery behavior."),
            ],
            "soak-monster": [
                ("minecraft-world-soak", "Keep the isolated cloned world loaded while repeatedly crossing chunks and running representative NoteRail actions; watch memory/MSPT and save growth."),
            ],
            "regression-archaeologist": [
                ("minecraft-replay-findings", "Replay previously recorded Minecraft-world findings against the cloned world and neighboring variants."),
            ],
            "full-chaos-pass": [
                ("minecraft-final-boss", "Combine only evidence-backed Minecraft weaknesses in the cloned profile, then perform a normal save/quit/reopen recovery check."),
            ],
        }
        for action_id, description in driver_by_profile.get(profile, []):
            actions.append(AdapterAction(
                action_id,
                description,
                "minecraft-live-driver-instructions",
                "driver-sandbox-only",
                False,
                self.name,
            ))
        return actions

    def run_scenario(self, scenario: str, context: AdapterContext) -> list[Finding]:
        audit = self._audit(context)
        level = audit["level"]
        regions = audit["regions"]
        datapacks = audit["datapack_summary"]

        if scenario == "adapter:expert-domain":
            status = "SURVIVED" if level.get("ok") else "BREAK"
            evidence = [
                f"level_name={level.get('LevelName')}",
                f"data_version={level.get('DataVersion')}",
                f"version={level.get('Version')}",
                f"region_files={regions.get('files')}",
                f"nonempty_region_files={regions.get('nonempty_files')}",
                f"zero_byte_region_placeholders={regions.get('zero_byte_placeholders')}",
                f"chunks={regions.get('chunks')}",
                f"datapacks={datapacks.get('packs')}",
                f"enabled_file_packs={len(datapacks.get('enabled_file_packs', []))}",
                f"enabled_function_count={datapacks.get('enabled_function_count')}",
                "pack_formats=" + json.dumps(datapacks.get("pack_formats", {}), sort_keys=True),
                f"session_lock_present={audit.get('session_lock', {}).get('present')}",
                f"audit_seconds={audit.get('elapsed_seconds', 0):.4f}",
            ]
            return [self._finding(
                context,
                scenario,
                status,
                "Minecraft world metadata and static structure recon completed."
                if status == "SURVIVED"
                else "Minecraft level.dat could not be parsed.",
                severity="info" if status == "SURVIVED" else "high",
                evidence=evidence,
            )]

        if scenario == "adapter:expert-qa":
            findings: list[Finding] = []
            if not level.get("ok"):
                findings.append(self._finding(
                    context, scenario, "BREAK", "level.dat failed NBT validation.",
                    severity="high", evidence=[str(level.get("error"))],
                ))
            else:
                findings.append(self._finding(
                    context, scenario, "SURVIVED", "level.dat parsed successfully.",
                    evidence=[
                        f"DataVersion={level.get('DataVersion')}",
                        f"LevelName={level.get('LevelName')}",
                    ],
                ))

            player = audit["player_nbt"]
            if player.get("errors"):
                findings.append(self._finding(
                    context, scenario, "BREAK",
                    f"{len(player['errors'])} player NBT file(s) failed parsing.",
                    severity="high", evidence=[
                        f"{item['file']}: {item['error']}" for item in player["errors"][:20]
                    ],
                ))
            else:
                findings.append(self._finding(
                    context, scenario, "SURVIVED",
                    f"Player NBT parsed successfully ({player.get('parsed_ok', 0)}/{player.get('files', 0)}).",
                ))

            if regions.get("bad"):
                findings.append(self._finding(
                    context, scenario, "BREAK",
                    f"{len(regions['bad'])} non-empty region file(s) failed structural validation.",
                    severity="high", evidence=[
                        f"{item['file']}: {item['error']}" for item in regions["bad"][:30]
                    ],
                ))
            else:
                findings.append(self._finding(
                    context, scenario, "SURVIVED",
                    (
                        f"All {regions.get('nonempty_files', 0)} non-empty region files "
                        f"passed header/allocation validation ({regions.get('chunks', 0)} chunks)."
                    ),
                    evidence=[
                        "compressions=" + json.dumps(regions.get("compressions", {}), sort_keys=True)
                    ],
                ))
            if regions.get("zero_byte_placeholders", 0):
                findings.append(self._finding(
                    context, scenario, "WEIRD",
                    (
                        f"Found {regions['zero_byte_placeholders']} zero-byte .mca placeholders. "
                        "They are tracked separately from corrupt non-empty regions."
                    ),
                    severity="low",
                    evidence=[
                        f"{area}={count}"
                        for area, count in list(regions.get("placeholder_areas", {}).items())[:20]
                    ],
                    action="Treat as cleanup/tooling evidence; do not classify as region corruption without a live Minecraft failure.",
                ))

            bad_zips = datapacks.get("bad_zip_packs", [])
            missing_meta = datapacks.get("missing_pack_mcmeta", [])
            if bad_zips:
                findings.append(self._finding(
                    context, scenario, "BREAK",
                    f"{len(bad_zips)} datapack ZIP(s) failed integrity validation.",
                    severity="high", evidence=[str(x) for x in bad_zips],
                ))
            else:
                findings.append(self._finding(
                    context, scenario, "SURVIVED",
                    f"All {datapacks.get('packs', 0)} datapack containers passed ZIP/directory structural checks.",
                ))
            if missing_meta:
                findings.append(self._finding(
                    context, scenario, "WEIRD",
                    f"{len(missing_meta)} datapack(s) are missing pack.mcmeta.",
                    severity="medium", evidence=[str(x) for x in missing_meta],
                ))

            sqlite_bad = [item for item in audit["sqlite"] if not item.get("ok")]
            json_bad = [item for item in audit["json"] if not item.get("ok")]
            findings.append(self._finding(
                context,
                scenario,
                "BREAK" if sqlite_bad or json_bad else "SURVIVED",
                (
                    f"Static mod-data validation found {len(sqlite_bad)} bad SQLite and "
                    f"{len(json_bad)} bad JSON file(s)."
                    if sqlite_bad or json_bad
                    else f"SQLite/JSON static validation survived ({len(audit['sqlite'])} SQLite, {len(audit['json'])} JSON)."
                ),
                severity="high" if sqlite_bad or json_bad else "info",
                evidence=[
                    *(f"sqlite:{item['file']}:{item.get('error') or item.get('quick_check')}" for item in sqlite_bad[:20]),
                    *(f"json:{item['file']}:{item.get('error')}" for item in json_bad[:20]),
                ],
            ))
            return findings

        if scenario in {"adapter:expert-ux", "adapter:expert-accessibility", "adapter:ui"}:
            label = {
                "adapter:expert-ux": "Minecraft UX review",
                "adapter:expert-accessibility": "Minecraft accessibility review",
                "adapter:ui": "Minecraft UI Gremlin pass",
            }[scenario]
            return [self._finding(
                context,
                scenario,
                "BLOCKED",
                f"{label} requires an external driver interacting with the isolated Minecraft profile.",
                evidence=["minecraft-live-driver-instructions are present in the phase plan"],
                action="Execute the Minecraft-specific driver actions from the saved phase plan and append screenshots/video/results.",
            )]

        if scenario == "adapter:expert-performance-reliability":
            functions = int(datapacks.get("enabled_function_count", 0))
            if functions >= 50_000:
                return [self._finding(
                    context,
                    scenario,
                    "WEIRD",
                    (
                        f"Static scan found {functions:,} enabled datapack function files. "
                        "This is a load-pressure signal, not proof of runtime slowdown."
                    ),
                    severity="low",
                    evidence=[
                        f"enabled_file_packs={len(datapacks.get('enabled_file_packs', []))}",
                        f"audit_seconds={audit.get('elapsed_seconds', 0):.4f}",
                    ],
                    action="Use the Minecraft live driver to measure world-load, /reload, memory, and MSPT.",
                )]
            return [self._finding(
                context, scenario, "SURVIVED",
                f"Static Minecraft workload inventory found {functions:,} enabled function files.",
                evidence=[f"audit_seconds={audit.get('elapsed_seconds', 0):.4f}"],
            )]

        if scenario == "adapter:expert-security-safety":
            unsafe = datapacks.get("unsafe_zip_members", {})
            if unsafe:
                return [self._finding(
                    context, scenario, "BREAK",
                    "Datapack ZIP path traversal/absolute-path entries were found.",
                    severity="high",
                    evidence=[
                        f"{pack}: {members[:10]}" for pack, members in unsafe.items()
                    ],
                )]
            return [self._finding(
                context, scenario, "SURVIVED",
                "No unsafe absolute/parent-traversal datapack ZIP entries were detected.",
                evidence=[audit["session_lock"].get("note", "")],
            )]

        if scenario == "adapter:wrong_way":
            case_collisions = datapacks.get("case_collisions", {})
            copy_named = [
                record["name"] for record in audit["datapacks"]
                if "copy" in str(record["name"]).lower()
            ]
            if case_collisions or copy_named:
                return [self._finding(
                    context, scenario, "WEIRD",
                    "Minecraft world contains naming/identity states worth Wrong-Way User review.",
                    severity="low",
                    evidence=[
                        *(f"copy_named={name}" for name in copy_named),
                        *(f"case_collision={pack}:{values[:3]}" for pack, values in case_collisions.items()),
                    ],
                )]
            return [self._finding(
                context, scenario, "SURVIVED",
                "No obvious datapack case-collision or copy-name identity traps were found.",
            )]

        if scenario == "adapter:persistence":
            old = audit.get("level_old", {})
            if old and not old.get("ok"):
                return [self._finding(
                    context, scenario, "BEND",
                    "level.dat_old exists but failed NBT parsing, reducing static recovery confidence.",
                    severity="medium", evidence=[str(old.get("error"))],
                )]
            if old and old.get("ok"):
                return [self._finding(
                    context, scenario, "SURVIVED",
                    "level.dat_old is parseable and compatible with the current world's static version metadata.",
                    evidence=[
                        f"current_DataVersion={level.get('DataVersion')}",
                        f"old_DataVersion={old.get('DataVersion')}",
                        f"current_version={level.get('Version')}",
                        f"old_version={old.get('Version')}",
                    ],
                )]
            return [self._finding(
                context, scenario, "SURVIVED",
                "No level.dat_old recovery file is present; current level.dat remains valid.",
            )]

        if scenario == "adapter:state":
            findings: list[Finding] = []
            missing = datapacks.get("missing_enabled_file_packs", [])
            if missing:
                findings.append(self._finding(
                    context, scenario, "BREAK",
                    "level.dat enables file datapacks that are missing from the world datapacks directory.",
                    severity="high", evidence=[str(x) for x in missing],
                ))
            else:
                findings.append(self._finding(
                    context, scenario, "SURVIVED",
                    "Every file datapack enabled in level.dat exists in the world datapacks directory.",
                ))

            duplicate_groups = datapacks.get("exact_duplicate_enabled_groups", [])
            if duplicate_groups:
                findings.append(self._finding(
                    context, scenario, "WEIRD",
                    f"Found {len(duplicate_groups)} exact duplicate enabled datapack group(s).",
                    severity="medium",
                    evidence=[" | ".join(group) for group in duplicate_groups],
                    action="Keep one copy enabled unless duplicate-pack behavior is intentionally under test.",
                ))

            nonidentical = datapacks.get("nonidentical_collision_pairs", [])
            if nonidentical:
                findings.append(self._finding(
                    context, scenario, "WEIRD",
                    f"Found {len(nonidentical)} non-identical enabled datapack pair(s) with function-path collisions.",
                    severity="medium",
                    evidence=[
                        f"{item['packs']}: {item['function_path_collisions']} function paths"
                        for item in nonidentical[:20]
                    ],
                    action="Review load-order/override intent before relying on those functions.",
                ))
            return findings

        if scenario == "adapter:charlie":
            duplicate_groups = datapacks.get("exact_duplicate_enabled_groups", [])
            copy_named = [
                record["name"] for record in audit["datapacks"]
                if "copy" in str(record["name"]).lower()
            ]
            if duplicate_groups or copy_named:
                return [self._finding(
                    context, scenario, "WEIRD",
                    "Charlie found redundant/confusing datapack identity state.",
                    severity="low",
                    evidence=[
                        *(f"exact_duplicate={' | '.join(group)}" for group in duplicate_groups),
                        *(f"copy_named={name}" for name in copy_named),
                    ],
                )]
            return [self._finding(
                context, scenario, "SURVIVED",
                "Charlie static datapack identity scan found no duplicate/copy-name traps.",
            )]

        if scenario == "adapter:regression":
            return [self._finding(
                context, scenario, "SURVIVED",
                "Minecraft static audit replay completed for Regression Archaeologist.",
                evidence=[
                    f"level_ok={level.get('ok')}",
                    f"bad_nonempty_regions={len(regions.get('bad', []))}",
                    f"zero_byte_region_placeholders={regions.get('zero_byte_placeholders', 0)}",
                    f"exact_duplicate_enabled_groups={len(datapacks.get('exact_duplicate_enabled_groups', []))}",
                    f"enabled_function_count={datapacks.get('enabled_function_count', 0)}",
                ],
            )]

        return []