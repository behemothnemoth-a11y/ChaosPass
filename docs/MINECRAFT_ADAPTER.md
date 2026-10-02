# Minecraft World Adapter

DROP 0005 adds a first-class Minecraft world adapter.

## Detection

A target is classified as a Minecraft world when it contains `level.dat` plus at least one normal world structure such as `dimensions`, `region`, `datapacks`, or `data`.

Detected worlds receive the `minecraft-world` target kind and the Minecraft adapter is stacked with the normal filesystem adapter.

## Automatic static checks

All automatic checks operate on the disposable cloned world.

### NBT

- parses `level.dat`;
- parses `level.dat_old` when present;
- records DataVersion, LevelName, Version, and DataPacks state;
- parses player NBT under both modern/alternate player-data layouts;
- distinguishes current-world failure from recovery-backup weakness.

### Region files

- scans every `.mca` file;
- treats 0-byte files as **placeholders**, not corruption;
- validates the two-sector region header for non-empty files;
- validates chunk sector offsets/counts;
- validates chunk record lengths and compression types;
- detects sector overlap;
- records chunk counts and compression distribution.

A 0-byte region file may be surfaced as WEIRD because it is useful cleanup/tooling evidence, but it is never automatically reported as a corrupt region.

### Datapacks

- validates ZIP integrity;
- verifies `pack.mcmeta` presence/JSON;
- records pack-format ranges;
- counts functions and namespaces;
- checks unsafe absolute / parent-traversal ZIP members;
- detects duplicate member paths and case-colliding members;
- compares `level.dat` enabled file packs to the world datapacks directory;
- hashes enabled ZIPs to find byte-identical enabled duplicates;
- finds enabled function-path collisions;
- distinguishes exact duplicate collisions from collisions between different packs.

### Mod/world side data

- runs SQLite `PRAGMA quick_check` read-only on `.sqlite` files;
- parses loose JSON files;
- records `session.lock` presence without claiming that file presence proves the original world is currently open.

## Minecraft-specific findings

Examples:

- missing enabled datapack -> BREAK;
- malformed non-empty region file -> BREAK;
- unsafe ZIP traversal path -> BREAK;
- invalid player/level NBT -> BREAK;
- exact duplicate enabled datapacks -> WEIRD;
- copy-style datapack naming -> WEIRD;
- zero-byte region placeholders -> WEIRD;
- very large enabled function volume -> WEIRD static pressure signal, never proof of runtime lag;
- parseable compatible `level.dat_old` -> persistence SURVIVED.

## Live-driver plans

Chaos Pass still does not launch Minecraft automatically.

Instead, the Minecraft adapter emits Minecraft-specific external-driver actions for:

- baseline cloned-world load;
- UX review;
- accessibility review;
- UI Gremlin fullscreen/focus/menu stress;
- save/quit/reopen persistence;
- disposable interrupted-save recovery;
- datapack enable/disable/reload state;
- chunk/dimension state transitions;
- live world-load and `/reload` performance;
- Wrong-Way invalid/duplicate datapack reloads;
- Charlie copy/rename datapack workflows;
- long-session chunk/action soak;
- Minecraft regression replay;
- Final Boss recovery testing.

Those tasks must run in an isolated Minecraft profile pointed at the cloned world.

## Evidence

Each Minecraft run writes `minecraft-world-audit.json` into the run evidence directory.

Function paths are kept in memory long enough to calculate collisions but removed from the persisted audit evidence, keeping reports compact while retaining collision counts/groups.

## NoteRail Testing acceptance run

The first real acceptance target was the local `NoteRail Testing` world.

Result with the integrated adapter:

- original integrity: PASS;
- CATASTROPHIC: 0;
- BREAK: 0;
- BEND: 1 (generic Windows path-length boundary);
- WEIRD: 5;
- BLOCKED: 3 (driver-only UI/accessibility paths);
- SURVIVED: 44.

Minecraft-specific observations included:

- Minecraft 26.2 / DataVersion 4903;
- 323 non-empty region files structurally valid;
- 66,593 chunk records validated;
- 479 zero-byte region placeholders tracked separately;
- 15 datapacks structurally valid;
- 91,865 enabled datapack function files;
- one exact duplicate enabled Hypa Hypa datapack pair;
- no non-identical cross-song function collision pairs;
- player NBT, JSON, and SQLite integrity checks survived.