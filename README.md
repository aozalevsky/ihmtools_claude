# ihmtools

> **Unofficial plugin.** ihmtools is an independent project. It is not
> affiliated with, endorsed by, or supported by RCSB PDB, Rutgers, The State
> University of New Jersey, or the University of California, San Francisco
> (UCSF). PDB-IHM, IHMValidation, python-ihm, and the `ihmv`/`ihmdep`
> command-line tools are developed and maintained by their own authors; this
> plugin only helps Claude use them. Names are used solely to identify those
> tools and services.

A Claude Code plugin for integrative structures and the PDB-IHM toolchain.
It helps Claude build IHMCIF files with [python-ihm], check them locally,
get [IHMValidation] reports from validate.pdb-ihm.org, and deposit with the
[ihmtools] command-line tools.

## What's inside

| Component | What it does | Invoke |
|---|---|---|
| `check` skill | Local pre-check of a `.cif`, `.cif.gz`, or `.bcif` file: syntax, PDBx/IHM dictionary, python-ihm readability, dataset linkage, representation consistency, optional atom names against the CCD | "check model.cif", `/ihmtools:check model.cif` |
| `validate` skill | Uploads to validate.pdb-ihm.org with `ihmv`, tracks status, downloads the reports; or runs your local IHMValidation Apptainer image; explains reports | "validate model.cif", `/ihmtools:validate` |
| `build` skill | Writes an `assemble.py` that builds an IHMCIF file with python-ihm from your coordinates and data | "make my model depositable", `/ihmtools:build` |
| `deposit` skill | Deposits with `ihmdep`, tracks status, DRAFT→DEPO and RECORD READY→SUBMIT, downloads results | "deposit model.cif", `/ihmtools:deposit` |
| `ihmcif` skill | Reference on the IHM data model and on gemmi/python-ihm/ChimeraX pitfalls; loads when you work with IHM files | automatic |
| `curator` agent | In-depth work: repairing files, triaging validation failures, annotation QC, structure inspection | "use the curator agent to repair ..." |

The `check` skill is a local pre-check, not PDB-IHM validation. Official
reports come only from the PDB-IHM validation server.

## Requirements

Python 3.9 or newer, and whichever of these the tasks you use need:

```bash
pip install ihm msgpack gemmi   # check, build, curator
pip install ihmtools            # validate (server route), deposit
```

With [uv] installed, the `check` skill runs in an isolated environment and
needs nothing else. Optional: Apptainer and an IHMValidation image (local
validation; set `IHMV_SIF=/path/to/ihmv.sif`), ChimeraX (geometry and
images). Each skill starts by reporting which of these it found
(`scripts/probe.sh`) and asks before installing anything.

## Install

In Claude Code:

```
/plugin marketplace add aozalevsky/ihmtools_claude
/plugin install ihmtools@ihmtools
```

From a local clone, use the clone's path instead of `aozalevsky/ihmtools_claude`.

## What leaves your machine

- **Nothing, until you confirm.** The plugin asks before every upload
  (`ihmv upload`, `ihmdep upload`) and before every action that changes
  server state (`set_status`, `delete`).
- The `check` skill downloads the public PDBx and IHM dictionaries from
  mmcif.wwpdb.org and, with `--check-atom-names`, Chemical Component
  Dictionary files from files.rcsb.org. They are cached in
  `~/.cache/ihmtools/`. Your files are never sent anywhere by `check`.
- Logging in to PDB-IHM (Globus) is always done by you (`! ihmv login`).

## Development

```bash
python3 -m venv .venv && .venv/bin/pip install ihm msgpack pytest
.venv/bin/python -m pytest -m "not network"   # offline tests
.venv/bin/python -m pytest                    # all tests (downloads dictionaries)
claude plugin validate .
```

## Credits

If you use IHMValidation reports in your research, cite: Zalevsky, A., et
al. "IHMValidation: Assessment of Integrative Structure Models Deposited to
the Protein Data Bank." J. Mol. Biol. (2025),
[doi:10.1016/j.jmb.2025.169598](https://doi.org/10.1016/j.jmb.2025.169598).

## License

MIT; see [LICENSE](LICENSE).

[python-ihm]: https://github.com/ihmwg/python-ihm
[IHMValidation]: https://github.com/salilab/IHMValidation
[ihmtools]: https://github.com/salilab/ihmtools
[uv]: https://docs.astral.sh/uv/
