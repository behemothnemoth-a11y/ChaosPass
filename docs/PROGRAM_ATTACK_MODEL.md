# Program Attack Model

Chaos Pass uses "attack" in the QA/stress-testing sense: deliberately challenge assumptions inside an authorized disposable environment, document what happens, then prove the original target is unchanged.

## Universal sequence

1. **Authorize + isolate** — capture the original manifest and create a disposable clone, snapshot, test world, VM, container, temp profile, or equivalent. No destructive probe runs against the original.
2. **Recon** — identify purpose, users, major features, data/state lifecycle, expensive operations, persistence points, external side effects, and recovery paths.
3. **Expert baseline** — establish golden paths, normal expectations, baseline performance/state, and ordinary defects.
4. **Surface map** — map UI, data/input, state machine, persistence, performance, filesystem/resources, integrations, concurrency, and recovery.
5. **Single-variable probes** — each persona first attacks one dimension at a time so cause and threshold are clear.
6. **Controlled escalation** — increase intensity stepwise. Record the first SURVIVED -> BEND -> WEIRD -> BREAK transition rather than racing straight to a crash.
7. **Profile handoffs** — weak signals move to the persona best suited to characterize them.
8. **Final Boss** — combine only evidence-backed weaknesses from earlier phases, adding one ingredient at a time.
9. **Recovery + teardown** — exercise safe recovery in the sandbox, preserve evidence, then destroy/detach disposable state.
10. **Zero-trace verification** — resnapshot the original and compare to baseline. Any unexpected original change is a CATASTROPHIC framework failure.
11. **Full report** — attempts, survivors, bends, weirdness, breaks, blocked tests, reproduction, evidence, thresholds, likely weak points, recommended fixes, cleanup, and integrity.

## Generic program attack surfaces

- **UI:** geometry, focus, navigation, modals, fullscreen, scaling, mixed input.
- **State:** modes, selections, stale references, undo/redo, transitions, multiple views of the same resource.
- **Persistence:** save/load/autosave/restart/interruption/stale versions/migration.
- **Data/input:** empty, malformed-but-safe, Unicode, long names, large valid data, ordering, duplicates.
- **Performance:** size, count, repetition, concurrency, expensive operations, cleanup, long sessions.
- **Filesystem/resources:** paths, moves/renames, missing resources, read-only states, temp files, caches.
- **Integration boundaries:** unavailable dependencies, stale connections, retries, test doubles, sandbox credentials.
- **Recovery:** cancel, undo, restart, restore, reopen, retry, rollback, conflict handling.

## Evidence rule

A finding is not complete because "something looked broken." Record the starting state, exact actions, intensity, observed change, recovery behavior, replay result, and original-target integrity result.