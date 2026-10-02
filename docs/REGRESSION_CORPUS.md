# Regression Corpus

Chaos Pass can carry historical findings inside a target under `regressions/*.json`.

These files are read-only inputs for Regression Archaeologist. They are not arbitrary command manifests and do not automatically execute target code.

Each case records:

- stable case ID;
- title;
- historical symptom;
- current expected behavior;
- regression test or replay reference.

Use:

```powershell
python -m chaos_pass list-regressions --target .
python -m chaos_pass plan --target . --profile regression-archaeologist
```

The regression-corpus adapter adds the historical cases to the Regression Archaeologist plan and records them in the regression phase findings.

ChaosPass itself currently ships a self-regression corpus containing findings discovered when Chaos Pass was run against Chaos Pass:

- Windows path-length harness crash / misclassification;
- repeated generic-scenario workdir collision;
- Git EOL/autocrlf false-positive QA failure;
- missing subcommand help description;
- overclassified configured-CLI UX expectation failure.

Historical cases are evidence and routing context. They do not bypass the Zero-Trace Contract or permit arbitrary execution.