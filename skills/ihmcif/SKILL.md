---
name: ihmcif
description: Reference for integrative-structure files in IHMCIF (the IHM extension of PDBx/mmCIF, text or BinaryCIF) and the python-ihm and gemmi APIs used on them. Use when reading, writing, editing, or explaining files with ihm_* categories, PDB-IHM or PDB-Dev entries (PDBDEV_######## or 4-character IDs), or python-ihm (`import ihm`) code.
---

# IHMCIF essentials

IHMCIF is the integrative/hybrid methods (IHM) extension of PDBx/mmCIF used
by the PDB-IHM archive. Before acting, read the reference that matches the
task:

- `${CLAUDE_SKILL_DIR}/references/data-model.md`: which `ihm_*` categories
  hold what, the invariants entries most often break, entry identifiers, and
  where the dictionaries and archive files live.
- `${CLAUDE_SKILL_DIR}/references/tooling.md`: choosing gemmi, python-ihm,
  or ChimeraX; verified API pitfalls; dictionary validation in Python.

## Rules for every IHMCIF task

- Never state a fact about an entry that you have not read from the file.
- Never invent a value the depositor must supply (citation, accession code,
  sample description, protocol detail). Report it as "depositor input
  required".
- Never edit the user's file in place. Copy it to
  `./ihmtools-work/<stem>/<stem>.orig.cif` and write fixes to
  `./ihmtools-work/<stem>/<stem>.fixed.cif`.
- Anchor every finding to `_category.keyword` and, where one exists, a row id.
- When a definition matters, consult the live dictionary. Remembering an
  enumeration or a list of mandatory items is not evidence.
- For a quick health check of a file, use the `check` skill
  (`/ihmtools:check <file>`). Its output is a local pre-check, not PDB-IHM
  validation.
