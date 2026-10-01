# Zero-Trace Contract

Chaos Pass exists to learn how a target fails without leaving the real target damaged, modified, polluted, or reconfigured.

## Hard invariants

1. Capture a pre-run manifest of the original target.
2. Never execute mutating break tests against the original target.
3. Create a disposable clone, snapshot, VM, container, test world, staging copy, or equivalent.
4. Confine destructive actions to that disposable environment.
5. Record evidence and reproduction information during the run.
6. Destroy or detach the disposable environment after testing.
7. Capture a second manifest of the original target.
8. Compare the manifests.
9. A run is incomplete unless original-target integrity passes.

## Zero-trace failure

If the original changes unexpectedly, that is a **CATASTROPHIC framework failure**, even if the target itself appears healthy. The report must identify the detected differences and the adapter or external process must be corrected before another destructive run.

## Irreversible external effects

Tests involving real messages, purchases, billing, destructive remote writes, third-party production systems, customer data, or other effects that cannot be guaranteed reversible are BLOCKED by default. Use mocks, fixtures, staging, test accounts, or provider-supported sandboxes instead.
