---
name: check
description: Local pre-check of an integrative-structure file (IHMCIF .cif, .cif.gz, or .bcif) before PDB-IHM validation or deposition. Checks syntax, PDBx/IHM dictionary compliance, python-ihm readability, dataset linkage, representation consistency, and optionally atom names against the CCD. Use when the user asks to check, lint, or sanity-check an IHM/IHMCIF/mmCIF integrative model, asks whether a file is ready for validation or deposition, or before uploading with the validate or deposit skills.
argument-hint: <file.cif|file.cif.gz|file.bcif> [--check-atom-names]
---

# Check an IHMCIF file

This is a **local pre-check, not PDB-IHM validation**. Say so when you report
results. The official report comes from validate.pdb-ihm.org (the `validate`
skill).

## 1. Probe and pick a runner

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/probe.sh"
```

- `uv` present: `uv run --script "${CLAUDE_SKILL_DIR}/scripts/check_entry.py" FILE`
  (isolated environment; nothing is installed into the user's Python).
- Otherwise, if `ihm` and `msgpack` are present:
  `python3 "${CLAUDE_SKILL_DIR}/scripts/check_entry.py" FILE`
- Otherwise stop and tell the user to run `pip install ihm msgpack` or to
  install uv. Ask before installing anything yourself.

## 2. Run

```
<runner> FILE [--check-atom-names] [--json] [--offline] [--cache-dir DIR]
```

- Add `--check-atom-names` when the user asks about atom names or wants a
  thorough check of an all-atom model. It downloads one small CCD file per
  residue type.
- The first run downloads about 6 MB of dictionaries into
  `~/.cache/ihmtools/`. Without network access the dictionary stage is NOT
  CHECKED. Never describe that result as valid.
- Large files take time: dictionary validation runs at roughly 2.5 MB/s.
  For files over about 100 MB, run in the background and tell the user what
  to expect.
- Use `--json` when you need to process the findings.

Exit codes: 0 means no BLOCKER or ERROR (verdict PASS or INCOMPLETE),
1 means at least one BLOCKER or ERROR (FAIL), 2 means the script could not
run (unreadable file, bad arguments).

## 3. Report

- Lead with the verdict line. INCOMPLETE means some stage did not run: list
  which and why, and do not present it as a clean result.
- Give BLOCKERs and ERRORs first. For each, explain at the user's level what
  is wrong, where (`_category.keyword`, row), and the fix the report gives.
- If the first finding says the file has no `ihm_*` categories, address that
  first; most other findings follow from it.
- An unused-dataset WARNING can be legitimate. Ask whether the dataset was
  used before advising removal.
- NOTEs (items python-ihm does not model) are informational. Summarize them
  in one line unless asked; they mean "do not repair this file by rewriting
  it with python-ihm".
- "depositor input required" means only the user can supply the value.
  Never invent one.

## 4. Next steps

- To repair the file, hand off to the `ihmtools:curator` agent with the file
  path and the findings.
- When the check is clean, offer the `validate` skill for the official
  IHMValidation report.
