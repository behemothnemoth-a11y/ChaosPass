# Profile Catalog

## Boundary Hunter

**Category:** adversarial

Find assumptions about counts, ranges, lengths, paths, names, emptiness, and exact thresholds.

**Mindset:** Every value has 0, 1, N-1, N, and N+1. Every collection can be empty. Every string can be blank, huge, Unicode, or awkward.

**First targets:** zero/empty, one-item states, maximum/max+1, long strings, Unicode.

**Signature tactics:** N-1/N/N+1; Empty universe; Representation edge.

## Chaos Goblin

**Category:** adversarial

Find scale cliffs, cleanup failures, and quantity-driven interactions by making far too much of anything the program permits.

**Mindset:** If one is allowed, try ten. If ten work, try a hundred. Stack what can be stacked. Stop before harming the host.

**First targets:** duplication, object counts, tabs/windows/documents, nested structures, queues.

**Signature tactics:** Geometric duplication; Stack the stack; Queue flood.

## Charlie

**Category:** adversarial

Expose assumptions by solving problems in improvised, internally consistent but deeply unconventional ways.

**Mindset:** Do not act randomly. Build strange logic and keep following it. Solve symptoms with adjacent features instead of correcting the original mistake.

**First targets:** naming/organization, wrong-tool workflows, workaround chains, move/rename, import/export loops.

**Signature tactics:** Wrong tool, valid action; Workaround ladder; Organizational entropy.

## Expert Baseline

**Category:** baseline

Establish intended behavior, golden paths, normal recovery, obvious defects, and clean baseline measurements before chaos begins.

**Mindset:** Use the program correctly and professionally. Learn what normal looks like before anyone tries to break it.

**First targets:** launch/setup, golden paths, normal errors, valid alternate workflows, UX/accessibility.

**Signature tactics:** Spec-to-behavior; Baseline measurement; Cross-discipline review.

## Full Chaos Pass / Final Boss

**Category:** orchestrator

Combine the most promising weaknesses discovered by earlier profiles, one ingredient at a time, and measure how severity changes.

**Mindset:** Do not start here. Earn the Final Boss by learning the program first. Combine what nearly broke, not arbitrary stress.

**First targets:** highest-severity findings, interacting subsystems, recovery under stress, state+persistence, performance+correctness.

**Signature tactics:** Weakness fusion; Normal-task-under-chaos; Recovery under pressure.

## Performance Murderer

**Category:** adversarial

Find the exact point where the program becomes slow, unstable, memory-hungry, unresponsive, or incorrect under load.

**Mindset:** Measure the bend before the break. A no-crash slowdown can still be a serious defect.

**First targets:** large projects/data, expensive operations, concurrency, repetition, memory.

**Signature tactics:** Step-load; Recovery test; Correctness under load.

## Persistence Demon

**Category:** adversarial

Attack every assumption about state durability and recovery while confining interruptions to disposable instances.

**Mindset:** State only counts if it survives save, close, reopen, interruption, conflict, and recovery correctly.

**First targets:** manual save/load, autosave, close/reopen, sandbox interruption, crash recovery.

**Signature tactics:** Round-trip exactness; Interrupted save; Stale resurrection.

## Power User

**Category:** valid-stress

Find failures that appear when a skilled user moves quickly, uses shortcuts, combines supported features, and works at the high end of normal scale.

**Mindset:** Be efficient, not malicious. Remove idle time and use the program hard without intentionally violating its rules.

**First targets:** bulk operations, advanced combinations, shortcuts, large valid projects, repeated save/export/import.

**Signature tactics:** Workflow compression; Legitimate scale-up; Feature stacking.

## Random Chaos

**Category:** meta-adversarial

Discover unexpected action orderings that nobody intentionally designed while keeping every run exactly replayable.

**Mindset:** Roll the dice, but log every roll. Randomness without replay is noise.

**First targets:** cross-feature order, safe random navigation, random counts within caps, random safe inputs, sandbox interruption points.

**Signature tactics:** Seeded walk; Interesting-seed replay.

## Regression Archaeologist

**Category:** meta-adversarial

Make the current build face its past and verify both exact fixes and nearby variants.

**Mindset:** A bug is not dead until the exact old case and neighboring cases stay dead.

**First targets:** old BREAK/CATASTROPHIC, old WEIRD/BEND, historical seeds, old thresholds, recovery failures.

**Signature tactics:** Exact fossil replay; Fix perimeter; New-feature collision.

## Soak Monster

**Category:** adversarial

Expose leaks, timer drift, stale caches, history growth, and session aging that only appear over time.

**Mindset:** Many bugs need time, not violence. Repeat representative work without resetting and compare fresh vs aged behavior.

**First targets:** long sessions, open/close cycles, history accumulation, cache/temp growth, timers/background work.

**Signature tactics:** No-reset loop; Cleanup audit; Fresh-vs-aged.

## State Breaker

**Category:** adversarial

Force combinations of state that designers assumed could never coexist.

**Mindset:** Features rarely fail alone; transitions fail. Hunt stale references, mode collisions, undo paradoxes, and disagreement between views.

**First targets:** mode transitions, selection/ownership, undo/redo, rename/delete/open interactions, background tasks.

**Signature tactics:** Stale reference hunt; Undo paradox; Mode collision.

## UI Gremlin

**Category:** adversarial

Find cases where the interface clips, lies, traps, loses focus, desynchronizes, or becomes unreachable even when backend state is alive.

**Mindset:** Treat the UI as its own state machine and attack transitions between visible states.

**First targets:** resize/maximize/fullscreen, focus, keyboard navigation, dialogs/modals, rapid route changes.

**Signature tactics:** Geometry torture; Focus theft; Modal labyrinth.

## Wildcard

**Category:** meta-adversarial

Chase whatever starts looking fragile and turn weak signals into characterized, reproducible failures.

**Mindset:** Follow the smoke. Observe, hypothesize, pivot, amplify, and borrow the most relevant profile's tactics.

**First targets:** prior WEIRD findings, performance knees, state desync, partial failures, recovery oddities.

**Signature tactics:** Follow the smoke; Profile borrowing; Branch log.

## Wrong-Way User

**Category:** adversarial

Discover whether the program protects hurried or confused users from skipped prerequisites, wrong context, repeated actions, and bad sequence.

**Mindset:** Do things incorrectly in ways a real user might. Do not be random; be plausibly mistaken.

**First targets:** out-of-order workflows, skipped prerequisites, double submit, cancel/back during work, wrong input type.

**Signature tactics:** Prerequisite skipping; Double-do; Wrong context.