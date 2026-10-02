---
name: build
description: Build a depositable integrative-structure IHMCIF (mmCIF) file with python-ihm from a model's coordinates and the data used to compute it (crosslinks, EM maps, SAS profiles, database accessions, starting models, protocol). Use when the user wants to package or convert an integrative model for PDB-IHM, write or fix python-ihm code that creates an ihm.System, or asks how to represent their datasets, restraints, or representation in IHMCIF.
argument-hint: <model coordinates> [data files...]
---

# Build an IHMCIF file with python-ihm

## 1. Use a native exporter if there is one

If the modeling software already writes IHMCIF (IMP/PMI does, through
`IMP.pmi.mmcif.ProtocolOutput`), use that output and run the `check` skill on
it. Rebuild by hand only what the exporter leaves out.

## 2. Probe

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/probe.sh"
```

You need `ihm` (python-ihm) and `gemmi` (to read the coordinates). If either
is missing, offer `pip install ihm gemmi` and ask before installing.

## 3. Inventory what the user has

Ask for, and record where each item comes from:

| Item | Typical source |
|---|---|
| Model coordinates | atomic mmCIF/PDB, or beads (`_ihm_sphere_obj_site`, IMP RMF exported to mmCIF) |
| Entity names and sequences | the coordinate file's `_entity.pdbx_description`, or UniProt |
| Experimental datasets | accessions: PRIDE (crosslinking-MS), EMDB (maps), SASBDB (SAS), BMRB, PDB |
| Starting models | PDB IDs, AlphaFold DB or ModelArchive accessions, comparative models |
| Restraints | crosslink tables (measured links, and the subset actually restrained), map fitting, SAS fits |
| Protocol | sampling method, number of models per step, clustering, ensembles |
| Citation and authors | the publication |

Every fact the user cannot supply stays unknown. **Never fabricate** a
citation, accession, sample description, or protocol detail. Put
`# TODO(depositor): ...` at the exact place in `assemble.py` and list every
TODO for the user at the end.

## 4. Write `assemble.py`

Write it into the user's project, never into the plugin directory. Before
writing, read `${CLAUDE_SKILL_DIR}/references/python-ihm-patterns.md`. It
condenses the two worked examples in `salilab/ihmtools`:
`examples/9A9W/assemble.py` (atomic) and `examples/9A8W/assemble.py`
(coarse-grained). Adapt the patterns; do not copy entry-specific metadata.

The script must end by writing the file and reading it back with
`ihm.reader.read`, the cheapest check that what it wrote is well formed.

## 5. Run and check

Run `python3 assemble.py`. Then run the `check` skill on the output, with
`--check-atom-names` for atomic models. Fix the script, not the generated
file, and repeat until the check has no BLOCKER or ERROR. Then offer the
`validate` skill.
