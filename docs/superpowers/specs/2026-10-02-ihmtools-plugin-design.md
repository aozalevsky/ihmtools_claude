# ihmtools Claude Code plugin — design

Date: 2026-10-02
Status: draft, awaiting review

## 1. Goal

A public Claude Code plugin named `ihmtools` that makes Claude competent with
integrative structures and the PDB-IHM toolchain: building IHMCIF files with
python-ihm, checking them offline, obtaining IHMValidation reports, and
depositing through PDB-IHM. "ihmtools" is the umbrella name for the bundled
knowledge of python-ihm (`ihmwg/python-ihm`), IHMValidation
(`salilab/IHMValidation`), and the `ihmv` / `ihmdep` CLIs (`salilab/ihmtools`).

The plugin is to be listed in the official Claude Code plugin directory
(`anthropics/claude-plugins-official`, third-party submission form). Until
then, and independently of it, it is installable from its own repository via a
bundled `marketplace.json`.

### Success criteria

1. `/plugin marketplace add <repo>` followed by `/plugin install ihmtools@<marketplace>` works.
2. On a fresh machine with only `pip install ihm gemmi ihmtools` (or with `uv`
   and nothing else installed), every skill completes its smoke scenario
   (section 7) on entries 9A9W (atomic) and 9A8W (coarse-grained).
3. No file in the plugin references the author's machine: no `/home/...` paths,
   no named conda environment, no internal ops repositories.
4. `claude plugin validate .` passes.
5. The plugin is fit to submit to the official directory: README, MIT
   LICENSE, accurate descriptions, no undeclared side effects.

### Decisions already made

| Question | Decision |
|---|---|
| Audience | Both, tiered: depositor/modeler workflows are the default surface; curator-depth repair and triage sit behind them. |
| How reports are produced | Default: `ihmv` against validate.pdb-ihm.org. Optional: a user-supplied local `ihmv.sif` Apptainer image. The plugin never builds the image. |
| Architecture | Skills + one agent + small bundled Python scripts. No MCP server in v1. |
| Source location | This directory (`claude_plugin/`) for now; GitHub home decided later. |
| Package availability | `ihm` 2.11, `gemmi` 0.7.5, and `ihmtools` 0.0.1a13 are all on PyPI. `ihmtools` has only pre-releases, so plain `pip install ihmtools` resolves to the latest alpha. |

### Out of scope for v1

- An MCP server (revisit if users ask for Claude Desktop support or the CLIs prove awkward for Claude to drive).
- Hooks, including a SessionStart dependency check.
- Building the IHMValidation Apptainer image.
- FRET validation (not supported by the pipeline yet).
- A `claude plugin eval` trigger-accuracy suite (follow-up after v1).

## 2. Layout

```
claude_plugin/                         # repo root
├── .claude-plugin/
│   ├── plugin.json                    # name: ihmtools, version, description, author, license, homepage
│   └── marketplace.json               # single-plugin marketplace; source "./"
├── skills/
│   ├── ihmcif/
│   │   ├── SKILL.md                   # knowledge skill (model-invoked)
│   │   └── references/
│   │       ├── data-model.md          # ihm_* category map, invariants
│   │       └── tooling.md             # gemmi vs python-ihm vs ChimeraX, verified pitfalls
│   ├── check/
│   │   ├── SKILL.md
│   │   └── scripts/check_entry.py
│   ├── validate/
│   │   ├── SKILL.md
│   │   └── references/report-sections.md
│   ├── build/
│   │   ├── SKILL.md
│   │   └── references/python-ihm-patterns.md
│   └── deposit/
│       └── SKILL.md
├── agents/
│   └── curator.md
├── tests/
│   ├── conftest.py                    # fixture builders
│   └── test_check_entry.py
├── docs/superpowers/specs/            # this document
├── README.md
└── LICENSE                            # MIT
```

Namespacing: plugin skills surface as `/ihmtools:check`, `/ihmtools:validate`,
`/ihmtools:build`, `/ihmtools:deposit`, `/ihmtools:ihmcif`; the agent as
`ihmtools:curator`. The author's personal `~/.claude/agents/pdb-ihm-curator.md`
is untouched and coexists.

## 3. Components

Each skill's `description` frontmatter is written for triggering: it names the
user phrasings and file types that should load it, and nothing broader.

### 3.1 `ihmcif` — shared domain knowledge

- **Purpose:** the one place that holds the IHM data model and tool-selection
  knowledge, so the four task skills and the agent do not each carry a copy.
- **Triggers:** user is reading, writing, or asking about IHM/IHMCIF mmCIF or
  BinaryCIF files, `ihm_*` categories, or python-ihm code.
- **Contents:** `SKILL.md` is a short index; detail lives in `references/`.
  - `data-model.md`: the category table from the current agent (composition,
    assembly, representation, coordinates, models/ensembles, states, input
    data, starting models, restraints, protocol), and the two invariants most
    entries break: linkage and representation consistency. Entry identifier
    forms (`PDBDEV_########` and 4-character PDB IDs) and where each appears.
  - `tooling.md`: when to use gemmi (lexical/dictionary level, reads files
    python-ihm rejects), python-ihm (semantic level; round-trip is a check, not
    a repair), ChimeraX (geometry/visuals, headless invocation). Includes the
    verified pitfalls carried over from the current agent: iterating gemmi
    items must cover both `loop` and `pair` forms; `block.find()` returns an
    empty table on a missing tag; `_all_models()` yields 2-tuples; the dumper
    silently drops unmodeled items; dictionary validation skips `chem_comp_*`
    parents so atom names are never checked; `mmcif_ihm_ext.dic` and
    `mmcif_ihm.dic` are the same file and must be merged with
    `mmcif_pdbx_v50.dic` for full coverage. There is no `gemmi` CLI assumption.
- **Dependencies:** none at runtime.

### 3.2 `check` — offline check of an IHMCIF file

- **Triggers:** "check / lint / is this file valid / will this pass" on a
  `.cif` or `.bcif`; also invoked by `validate` and `deposit` as a pre-flight.
- **Behavior:** run the tool probe (section 4.1), then
  `check_entry.py <file>` (section 5), then present the findings. For each
  BLOCKER or ERROR, explain it at the user's level and propose the fix; hand
  off to the `curator` agent if the user wants the file repaired.
- **Dependencies:** `ihm`, `gemmi` (via `uv` or the user's Python); network on
  first run for dictionaries.

### 3.3 `validate` — IHMValidation report

- **Triggers:** "validate", "validation report", "run IHMValidation", or
  questions about an existing report PDF/HTML.
- **Server path (default):**
  1. Offer a pre-flight `check`; recommend it if not yet run on this file.
  2. `ihmv whoami`. If not logged in, ask the user to run `! ihmv login`
     (Globus flow requires pasting a code back; Claude cannot complete it).
  3. Confirm before upload: the structure leaves the machine and goes to
     PDB-IHM. Always the production server unless the user asks for
     `--mode dev`.
  4. `ihmv upload <file>`, record the returned id.
  5. Poll `ihmv get_status <id>` at a coarse interval (minutes, not seconds);
     tell the user typical time is 5–115 minutes and that they can leave and
     come back by asking for the status of `<id>`.
  6. `ihmv download <id>` into `<stem>_validation/`.
- **Local path (opt-in):** only when the user sets `IHMV_SIF=/path/ihmv.sif`
  or names an image. Detect `apptainer`, fall back to `singularity`. Run
  `apptainer run --pid "$IHMV_SIF" --cache-root <cache> --output-root <out> -f <abs file>`
  in the background; add `--html-mode local` if the user wants the HTML
  report. Use the `--enable-*` switches to bisect a failing run.
- **Reading reports:** `references/report-sections.md` describes the six
  report sections, which are data-type dependent (an entry with no SAS data
  legitimately has an empty SAS section), and links to
  https://pdb-ihm.org/validation_help.html for metric definitions. Fault-line
  triage (entry data vs. pipeline code vs. environment) is delegated to the
  `curator` agent.
- **Dependencies:** `ihmtools` for the server path; Apptainer/Singularity plus
  a user-built image for the local path.

### 3.4 `build` — produce an IHMCIF with python-ihm

- **Triggers:** "make my model depositable", "convert to IHMCIF/mmCIF for
  PDB-IHM", "write an ihm file", or writing python-ihm code.
- **Behavior:** gather what the user actually has (coordinates, crosslink
  tables, EM maps, SAS profiles, accessions, protocol facts), then write an
  `assemble.py` in the user's project modeled on the `ihmtools` examples:
  9A9W (atomic, DSSO crosslinks, 3DEM) and 9A8W (coarse-grained spheres, SDA
  crosslinks, 3DEM). Run it, then run `check` on the output.
- **Points users to native exporters first** when their modeling software
  already writes IHMCIF (e.g. IMP/PMI), rather than rebuilding by hand.
- **Never fabricates** depositor-supplied values (citation, accessions,
  sample description, protocol details); unknowns are left as explicit
  TODO markers in `assemble.py` and listed to the user.
- `references/python-ihm-patterns.md`: condensed patterns from the two
  examples (entities and sequences, one asym per chain copy, representation,
  datasets with database references, crosslink restraints, 3DEM restraints,
  protocol, model with atoms vs. spheres).
- **Dependencies:** `ihm`, `gemmi`.

### 3.5 `deposit` — PDB-IHM deposition lifecycle

- **Triggers:** "deposit", "submit to PDB-IHM", "deposition status".
- **Behavior:** `ihmdep whoami` / `! ihmdep login` as in 3.3. Free actions:
  `get_status`, `download`. Each of these requires explicit confirmation every
  time, naming the entry and the action: `upload` (with `--image` when the
  user has one), `set_status --to DEPO` and `--to SUBMIT` (the only two
  transitions the tool allows), and `delete` (DRAFT/DEPO only). Recommend
  `check` before upload. Production server unless the user asks for dev.
- **Dependencies:** `ihmtools`.

### 3.6 `curator` agent — repair, triage, annotation QC

Derived from `~/.claude/agents/pdb-ihm-curator.md` with these changes:

- **Removed:** the author's conda environment and versions, all
  `/home/arthur/...` paths, `IHMValidation_*` checkout names, the sandbox path
  `~/work/validation/tmp/fix/`, references to `pdb-ihm-ops`,
  `standalone/pdb-ihm`, `pdb-ihm.wiki`, and DERIVA internals.
- **Moved to `ihmcif`:** the domain model (section 1 of the current agent)
  and tool selection (section 3). The agent loads `ihmcif` at startup via the
  agent frontmatter `skills:` field; if that field does not preload plugin
  skills, the agent body instead instructs it to read
  `${CLAUDE_PLUGIN_ROOT}/skills/ihmcif/SKILL.md` and its references first.
- **Kept:** the defining habit (never assert a fact not read from the file;
  never invent a depositor-supplied value), workflows A–D (repair, report
  triage, annotation QC, structure inspection), working rules, output format.
- **Changed:** "you work alongside an IHMValidation developer" becomes "match
  the user's level": explain for depositors, report tersely for curators.
  Environment section becomes a runtime probe (section 4.1). Sandbox becomes
  `./ihmtools-work/<stem>/`.
- **Added:** a short developer note: when running IHMValidation from a source
  checkout instead of the container, run `ihm_validator.py` from inside
  `ihm_validation/` because of its flat imports.
- **Tools:** Bash, Read, Write, Edit, Glob, Grep, WebFetch, WebSearch.

## 4. Runtime behavior

### 4.1 Tool probe

Every task skill and the agent begin with one probe command that reports, without installing anything:

- Python imports `ihm` and `gemmi`, with versions.
- `ihmv`, `ihmdep`, `uv`, `apptainer`, `singularity` on PATH.
- ChimeraX: `chimerax` on PATH, or the platform default location (Linux `/usr/bin/chimerax`, macOS `/Applications/ChimeraX*.app/Contents/bin/ChimeraX`).
- `IHMV_SIF` if set.

Missing pieces are reported with the exact install command. Installation
happens only after the user agrees; the plugin never runs `pip install`
unprompted.

### 4.2 Running bundled scripts

`check_entry.py` carries PEP 723 inline metadata
(`dependencies = ["ihm>=2.11", "gemmi>=0.7", "msgpack"]`). Resolution order:

1. `uv` present → `uv run --script ${CLAUDE_PLUGIN_ROOT}/skills/check/scripts/check_entry.py ...` (isolated env; user env untouched).
2. else the user's `python` if it imports `ihm` and `gemmi` → `python ${CLAUDE_PLUGIN_ROOT}/...`.
3. else report the install line and stop.

### 4.3 Caches

`~/.cache/ihmtools/` (respecting `XDG_CACHE_HOME`):

- `dictionaries/`: `mmcif_pdbx_v50.dic` and `mmcif_ihm_ext.dic`, downloaded on first use from `https://mmcif.wwpdb.org/dictionaries/ascii/`, refreshed when older than 30 days.
- `ccd/`: per-component CCD files for the opt-in atom-name check.

### 4.4 File handling

Input files are never modified in place. Repairs copy the input to
`./ihmtools-work/<stem>/<stem>.orig.cif`, patch
`./ihmtools-work/<stem>/<stem>.fixed.cif`, and leave helper scripts there so
the work is repeatable. Validation downloads go to `<stem>_validation/` next
to the input.

### 4.5 Side effects requiring confirmation

| Action | Why |
|---|---|
| `ihmv upload` | Sends an unreleased structure to PDB-IHM. |
| `ihmv delete`, `ihmv set_status` | Changes server state. |
| `ihmdep upload`, `set_status`, `delete` | Changes deposition state; confirmed every time, naming entry and action. |
| `pip install` / `uv tool install` | Changes the user's environment. |

Logins are always run by the user (`! ihmv login`, `! ihmdep login`).

## 5. `check_entry.py` specification

```
check_entry.py FILE [--json] [--check-atom-names] [--cache-dir DIR] [--offline]
```

`FILE` is `.cif`, `.cif.gz`, or `.bcif`. Stages run independently: a failed
stage is reported and the rest continue, except that a stage-1 parse failure
skips all later stages, since every one of them needs a parsed file.

BinaryCIF: gemmi's Python API (0.7.5) reads only text and gzipped CIF, while
python-ihm reads BinaryCIF with `format='BCIF'` (needs `msgpack`). For a
`.bcif` input, stage 1 is performed by python-ihm's reader (parse only, no
inventory), stages 2–6 run with `format='BCIF'`, and stage 7 is reported
NOT CHECKED (bcif). The script's inline dependencies therefore include
`msgpack`.

| # | Stage | Tool | Reports |
|---|---|---|---|
| 1 | Parse and inventory | gemmi (mmCIF) / python-ihm (BCIF) | Syntax errors (BLOCKER). For mmCIF, category inventory from both loop and pair items. |
| 2 | Dictionary validation | `ihm.dictionary`, PDBx + IHM merged | Each `ValidatorError` item as ERROR, anchored to `_category.keyword`. If dictionaries cannot be obtained (offline, no cache), the stage is NOT CHECKED, never passed. |
| 3 | Semantic read | `ihm.reader.read(..., warn_unknown_category=True, warn_unknown_keyword=True)` | Exception → BLOCKER. Unknown-category/keyword warnings are not emitted directly; they are only reported if stage 2 also flags the item. |
| 4 | Linkage | python-ihm object graph | Restraints or model groups referring to missing ids (ERROR); datasets referenced by no restraint or starting model (WARNING). |
| 5 | Representation consistency | python-ihm object graph | Segments declared coarse-grained that carry atoms, or atomic segments that carry spheres/Gaussians (ERROR). |
| 6 | Round-trip | `ihm.dumper.write` + category/item diff | Items present in the original and absent from the round-trip, as NOTE "not modeled by python-ihm". Never an error. |
| 7 | Atom names vs. CCD (opt-in `--check-atom-names`) | gemmi + CCD downloads | Distinct `(comp_id, atom_id)` pairs in `atom_site` missing from the component's `_chem_comp_atom.atom_id` set (ERROR), e.g. PDB v2.3 hydrogen names. |

**Text output** (default), most severe first:

```
[BLOCKER|ERROR|WARNING|NOTE] _category.keyword (row/id)
  Observed: ...
  Expected: ...
  Evidence: ...
  Fix:      ... | depositor input required: ...
```

followed by `Verified:` (stages run, with counts) and `Not checked:` (stages skipped and why).

**JSON output** (`--json`): `{"file": ..., "stages": [{"name", "status": "ok|findings|not_checked|error", "detail"}], "findings": [{"severity", "category", "keyword", "row", "observed", "expected", "evidence", "fix"}]}`.

**Exit codes:** 0: no BLOCKER/ERROR. 1: at least one BLOCKER/ERROR. 2: the script could not run (bad arguments, unreadable file).

**Offline:** `--offline` uses only cached dictionaries/CCD and marks stages
NOT CHECKED when the cache is empty.

## 6. Distribution

- `plugin.json`: `name: "ihmtools"`, semver `version` starting at `0.1.0`,
  description, `author: {"name": "Sali Lab"}`, `license: "MIT"`. `homepage`
  and `repository` are added when the GitHub home is chosen (section 1); the
  author field is revisited at the same time.
- `marketplace.json`: a single-plugin marketplace whose source is `./`, so the
  repo is installable as soon as it is on GitHub.
- Official directory: after the GitHub repo exists and a tagged release
  passes section 7, submit via the plugin directory submission form. The
  plugin `name` is immutable once published; `displayName` can change.
- Release tags via `claude plugin tag` so `plugin.json` and the marketplace
  entry agree.

## 7. Testing

1. **Unit tests** (`pytest tests/`) for `check_entry.py`. Fixtures are built
   in `conftest.py` with python-ihm: a minimal valid entry, and mutations of
   it covering one defect each: syntax error, dangling dataset id in a
   restraint, orphan dataset, coarse-grained segment with `atom_site` rows,
   obsolete hydrogen names. Each test asserts the expected severity,
   `_category.keyword`, and exit code. Tests needing network (dictionaries,
   CCD) are marked `@pytest.mark.network`; a cached-dictionary fixture lets
   the rest run offline.
2. **Structure:** `claude plugin validate .` passes.
3. **Smoke scenarios** in a clean environment (fresh venv or `uv` only, no
   author paths), on 9A9W and 9A8W from the ihmtools examples:
   - `check`: runs, produces a report, exit code matches findings.
   - `build`: regenerates a depositable file from the example `data/` and the result passes `check`.
   - `validate` (server): login prompt shown when logged out; upload confirmation requested; status and download work for an existing id.
   - `validate` (local): only exercised where an `ihmv.sif` exists; otherwise verified to decline cleanly and explain.
   - `deposit`: status and download work; each state-changing action stops for confirmation. Exercised against `--mode dev` only.
   - `curator`: repairs a mutated fixture into a file that passes dictionary validation and a python-ihm round-trip.
4. **Portability grep:** no `/home/`, `arthur`, `ihm_latest`, or
   `work/validation` strings anywhere in the plugin tree.
