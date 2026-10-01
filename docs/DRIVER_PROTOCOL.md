# External Driver Protocol

Some of the most valuable profiles target GUI behavior, focus, fullscreen, navigation, modal state, or application-specific workflows. The standalone Chaos Pass runner should not pretend those are tested when it has no UI driver.

Instead, `chaos-pass plan` emits two classes of actions:

- **auto_actions** — actions the selected adapters can execute safely themselves;
- **driver_actions** — structured persona actions that require an authorized computer/UI driver.

## Driver contract

An external driver must:

1. verify it is interacting with the disposable/sandbox instance, never the original;
2. preserve the action ID and persona/profile;
3. perform only the intended action or a documented target-specific translation;
4. capture screenshots/video/logs/state observations where relevant;
5. report SURVIVED, BEND, WEIRD, BREAK, CATASTROPHIC, or BLOCKED;
6. return exact reproduction steps and evidence paths;
7. stop if a real external side effect, credential use, production system, or non-reversible action would be reached;
8. hand findings back to Wildcard/Final Boss only when evidence supports escalation.

## Example plan fragment

```json
{
  "action_id": "ui-gremlin-tactic-1",
  "description": "Geometry torture: expose clipping and fake fullscreen...",
  "capability": "external-driver-instructions",
  "risk": "driver-sandbox-only",
  "executable": false,
  "source_adapter": "playbook-driver"
}
```

A Computer Use/Desktop Commander-style orchestrator can consume these tasks, translate them into target-specific interactions, and append evidence to the Chaos Pass report. Until such a driver actually performs the task, the runner does not count it as tested.