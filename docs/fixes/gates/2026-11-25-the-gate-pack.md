# gates · 2026-11-25 — Ymir's gate pack replaces the light privacy guard

## What was wrong

This repository was guarded by `privacy-guard.yml`: gitleaks through a marketplace action, and a grep of the tree
for private words read from an Actions secret. That was a weaker gate than Ymir judges itself with, and it kept the
private word list on the hosting service.

## What changed

- **Ymir's gate pack is seated** (`VENDORED` lists every file, at Ymir `83039d8923c4`): Ymir's own secret, personal-data,
  identity and vault wards, one door for hooks and CI (`bin/gates/run-gates.sh`), the hooks (`.githooks/`), the CI
  workflow (`.github/workflows/gates.yml`, gitleaks pinned and checksum-verified), the sync check
  (`bin/gates/vendor-sync.sh`) and a planted-fault test per gate (`tests/gates.test.sh`).
- **`privacy-guard.yml` is retired.** Its gitleaks scan is carried by the new workflow over the whole history. Its
  word list is not: the list stays in the operator's home, read by the hooks on a seat, and CI judges shapes.
- **`.pi/` and `RULES/00-the-gate-pack.md`** are the root mark the wards look for, and the rule in plain words.

Seat the hooks once in each clone: `bin/gates/install-hooks.sh`.

## Proof

```bash
bash tests/gates.test.sh                 # 16 passed, 0 failed
bin/gates/run-gates.sh tree              # clean, with the home's list and without it (CI posture)
bin/gates/vendor-sync.sh --check         # every file in step with Ymir at ymir_ref
```

The history was audited for leaks before the pack was turned on; the findings are in the operator's plan 372.
