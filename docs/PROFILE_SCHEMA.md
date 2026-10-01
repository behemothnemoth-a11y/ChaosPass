# Profile Schema v1

Every `profiles/*.json` file is an executable testing persona definition, not just a scenario list.

Required fields:

- `schema_version`, `id`, `display_name`, `category`
- `mission` — what weakness class this persona is trying to expose
- `mindset` — how this persona makes testing decisions
- `attack_surface_priority`
- `opening_moves`
- `escalation_ladder`
- `signature_tactics` — named tactics with purpose, actions, and signals to watch
- `combination_rules`
- `handoff_triggers`
- `stop_conditions`
- `required_evidence`
- `scenarios`

Profiles inherit the Zero-Trace Contract and Program Attack Model. Adapters translate persona intent into target-specific, safely isolated operations.

## Key distinctions

**Random Chaos** chooses a seeded action sequence first and then executes it. It is unpredictable but replayable.

**Wildcard** reacts to evidence during the run. It observes weak signals, forms a hypothesis, borrows tactics from other profiles, and pivots mid-run.

**Charlie** is not random. It follows bizarre but internally consistent problem-solving logic: wrong-tool solutions, workaround chains, confusing organization, and fixes layered on fixes.

**Final Boss** may not invent arbitrary compound stress. It combines weaknesses actually discovered or justified by earlier passes.