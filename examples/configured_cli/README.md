# Configured CLI Example

This miniature target demonstrates the explicit process-probe contract.

From this directory:

```powershell
python -m chaos_pass inspect-target --target .
python -m chaos_pass plan --target . --profile wrong-way-user
python -m chaos_pass run --target . --profile expert-baseline --output ..\..\reports
```

The target opts into process execution in `chaospass.toml`. The configured CLI adapter runs only the listed probes against the disposable clone. The invalid-option probe expects exit code 2, demonstrating that a safely rejected bad request counts as healthy behavior.