from __future__ import annotations

import gzip
import json
from pathlib import Path
import shutil
import sqlite3
import struct
import tempfile
import unittest
import zipfile

from chaos_pass.adapters import discover_adapters
from chaos_pass.config import TargetConfig
from chaos_pass.minecraft_adapter import audit_minecraft_world
from chaos_pass.profiles import load_profile_definition
from chaos_pass.runner import run


def _nbt_string(value: str) -> bytes:
    raw = value.encode("utf-8")
    return struct.pack(">H", len(raw)) + raw


def _named(tag: int, name: str, payload: bytes) -> bytes:
    return bytes([tag]) + _nbt_string(name) + payload


def _compound(items: list[bytes]) -> bytes:
    return b"".join(items) + b"\x00"


def _list_strings(values: list[str]) -> bytes:
    return bytes([8]) + struct.pack(">i", len(values)) + b"".join(_nbt_string(v) for v in values)


def _write_level(path: Path, enabled: list[str]) -> None:
    version = _compound([
        _named(3, "Id", struct.pack(">i", 4903)),
        _named(8, "Name", _nbt_string("26.2")),
        _named(8, "Series", _nbt_string("main")),
        _named(1, "Snapshot", b"\x00"),
    ])
    datapacks = _compound([
        _named(9, "Enabled", _list_strings(enabled)),
        _named(9, "Disabled", _list_strings([])),
    ])
    data = _compound([
        _named(3, "DataVersion", struct.pack(">i", 4903)),
        _named(8, "LevelName", _nbt_string("Synthetic Minecraft World")),
        _named(10, "Version", version),
        _named(10, "DataPacks", datapacks),
    ])
    root = bytes([10]) + _nbt_string("") + _named(10, "Data", data) + b"\x00"
    path.write_bytes(gzip.compress(root))


def _write_valid_region(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = bytearray(3 * 4096)
    # Chunk slot 0 -> sector 2, length 1 sector.
    data[0:4] = ((2 << 8) | 1).to_bytes(4, "big")
    pos = 2 * 4096
    data[pos : pos + 4] = (2).to_bytes(4, "big")
    data[pos + 4] = 2  # zlib compression type
    data[pos + 5] = 0  # one byte of placeholder compressed payload; structural check only
    path.write_bytes(data)


def _write_datapack(path: Path, namespace: str = "demo") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "pack.mcmeta",
            json.dumps({
                "pack": {
                    "description": "synthetic",
                    "min_format": [107, 1],
                    "max_format": [107, 1],
                }
            }),
        )
        archive.writestr(f"data/{namespace}/function/test.mcfunction", "say test\n")


def _make_world(root: Path, *, duplicate_pack: bool = True) -> Path:
    world = root / "world"
    world.mkdir()
    enabled = ["vanilla", "file/demo.zip"]
    if duplicate_pack:
        enabled.append("file/demo - Copy.zip")
    _write_level(world / "level.dat", enabled)
    shutil.copy2(world / "level.dat", world / "level.dat_old")

    _write_valid_region(
        world / "dimensions" / "minecraft" / "overworld" / "region" / "r.0.0.mca"
    )
    placeholder = (
        world / "dimensions" / "minecraft" / "overworld" / "poi" / "r.0.0.mca"
    )
    placeholder.parent.mkdir(parents=True, exist_ok=True)
    placeholder.write_bytes(b"")

    _write_datapack(world / "datapacks" / "demo.zip")
    if duplicate_pack:
        shutil.copy2(
            world / "datapacks" / "demo.zip",
            world / "datapacks" / "demo - Copy.zip",
        )

    player = world / "players" / "data" / "player.dat"
    player.parent.mkdir(parents=True, exist_ok=True)
    _write_level(player, ["vanilla"])

    db = world / "data" / "example.sqlite"
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db)
    con.execute("create table demo (id integer primary key, value text)")
    con.execute("insert into demo(value) values ('ok')")
    con.commit()
    con.close()
    (world / "data" / "example.json").write_text('{"ok": true}', encoding="utf-8")
    (world / "session.lock").write_bytes(b"lock")
    return world


class MinecraftAdapterTests(unittest.TestCase):
    def test_minecraft_world_is_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            world = _make_world(Path(temp))
            fingerprint, stack = discover_adapters(world, TargetConfig({}, None))
            self.assertIn("minecraft-world", fingerprint.target_kinds)
            self.assertIn("minecraft-world", stack.names)

    def test_static_audit_distinguishes_placeholders_and_duplicate_packs(self):
        with tempfile.TemporaryDirectory() as temp:
            world = _make_world(Path(temp))
            audit = audit_minecraft_world(world)
            self.assertTrue(audit["level"]["ok"])
            self.assertEqual(audit["regions"]["nonempty_files"], 1)
            self.assertEqual(audit["regions"]["zero_byte_placeholders"], 1)
            self.assertEqual(audit["regions"]["bad"], [])
            self.assertEqual(audit["regions"]["chunks"], 1)
            self.assertEqual(audit["datapack_summary"]["packs"], 2)
            self.assertEqual(
                audit["datapack_summary"]["exact_duplicate_enabled_groups"],
                [["demo - Copy.zip", "demo.zip"]],
            )
            self.assertEqual(
                audit["datapack_summary"]["nonidentical_collision_pairs"],
                [],
            )
            self.assertTrue(all(item["ok"] for item in audit["sqlite"]))
            self.assertTrue(all(item["ok"] for item in audit["json"]))

    def test_state_breaker_flags_exact_duplicate_enabled_packs_without_breaking_original(self):
        with tempfile.TemporaryDirectory() as temp:
            world = _make_world(Path(temp))
            report = run(world, "state-breaker", 32 * 1024 * 1024, seed=44)
            self.assertTrue(report.integrity_passed)
            self.assertIn("minecraft-world", report.adapter_names)
            self.assertTrue(any(
                finding.adapter == "minecraft-world"
                and finding.scenario == "adapter:state"
                and finding.status == "WEIRD"
                and "duplicate" in finding.summary.lower()
                for finding in report.findings
            ))
            self.assertFalse(any(
                finding.adapter == "minecraft-world"
                and finding.status in {"BREAK", "CATASTROPHIC"}
                for finding in report.findings
            ))

    def test_minecraft_plan_has_live_persistence_driver_actions(self):
        with tempfile.TemporaryDirectory() as temp:
            world = _make_world(Path(temp), duplicate_pack=False)
            _, stack = discover_adapters(world, TargetConfig({}, None))
            plan = stack.plan(load_profile_definition("persistence-demon"))
            self.assertTrue(any(
                action.action_id == "minecraft-save-reopen"
                and not action.executable
                and action.source_adapter == "minecraft-world"
                for action in plan.actions
            ))

    def test_minecraft_expert_plan_has_ui_and_accessibility_driver_actions(self):
        with tempfile.TemporaryDirectory() as temp:
            world = _make_world(Path(temp), duplicate_pack=False)
            _, stack = discover_adapters(world, TargetConfig({}, None))
            plan = stack.plan(load_profile_definition("expert-baseline"))
            action_ids = {action.action_id for action in plan.actions}
            self.assertIn("minecraft-load-world", action_ids)
            self.assertIn("minecraft-ui-baseline", action_ids)
            self.assertIn("minecraft-accessibility-baseline", action_ids)

    def test_bad_nonempty_region_is_break(self):
        with tempfile.TemporaryDirectory() as temp:
            world = _make_world(Path(temp), duplicate_pack=False)
            bad = world / "dimensions" / "minecraft" / "overworld" / "region" / "r.1.0.mca"
            bad.write_bytes(b"broken")
            report = run(world, "expert-baseline", 32 * 1024 * 1024, seed=45)
            self.assertTrue(report.integrity_passed)
            self.assertTrue(any(
                finding.adapter == "minecraft-world"
                and finding.scenario == "adapter:expert-qa"
                and finding.status == "BREAK"
                and "region" in finding.summary.lower()
                for finding in report.findings
            ))

    def test_unsafe_datapack_member_is_security_break(self):
        with tempfile.TemporaryDirectory() as temp:
            world = _make_world(Path(temp), duplicate_pack=False)
            evil = world / "datapacks" / "evil.zip"
            with zipfile.ZipFile(evil, "w") as archive:
                archive.writestr("pack.mcmeta", '{"pack":{"description":"x","min_format":[107,1],"max_format":[107,1]}}')
                archive.writestr("../escape.txt", "nope")
            # Add to level.dat enabled list.
            _write_level(world / "level.dat", ["vanilla", "file/demo.zip", "file/evil.zip"])
            report = run(world, "expert-baseline", 32 * 1024 * 1024, seed=46)
            self.assertTrue(report.integrity_passed)
            self.assertTrue(any(
                finding.adapter == "minecraft-world"
                and finding.scenario == "adapter:expert-security-safety"
                and finding.status == "BREAK"
                for finding in report.findings
            ))


if __name__ == "__main__":
    unittest.main()