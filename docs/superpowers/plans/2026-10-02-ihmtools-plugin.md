# ihmtools Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the public, unofficial `ihmtools` Claude Code plugin: a local IHMCIF checker, five skills (`ihmcif`, `check`, `validate`, `build`, `deposit`), and a generalized `curator` agent, installable from its own repository marketplace.

**Architecture:** A plain plugin (no MCP server, no hooks). Skills and the agent are Markdown; the only code is the checker (`skills/check/scripts/`: `ihmcheck_io.py` for file/cache access through python-ihm's low-level readers, `ihmcheck_stages.py` for seven independent stages, `check_entry.py` for the CLI) and `scripts/probe.sh`. Servers are reached only through the existing `ihmv`/`ihmdep` CLIs.

**Tech Stack:** Python >= 3.9, python-ihm (`ihm`) >= 2.11, `msgpack`, pytest, bash; `uv` for zero-install runs; Claude Code plugin format (`.claude-plugin/plugin.json`, `skills/*/SKILL.md`, `agents/*.md`).

**Spec:** `docs/superpowers/specs/2026-10-02-ihmtools-plugin-design.md`

**Repository:** https://github.com/aozalevsky/ihmtools_claude (`origin`; the local `main` is already rebased onto its initial commit)

## Global Constraints

- Plugin `name` is `ihmtools` (immutable once published); `version` `0.1.0` in both manifests; `author`/`owner` `{"name": "Arthur Zalevsky"}`; license MIT; `homepage`/`repository` `https://github.com/aozalevsky/ihmtools_claude`.
- The disclaimer is verbatim: the 7-line block in README lines 3-9 (spec 6.1), and the first sentence of every manifest description is `Unofficial, community plugin, not affiliated with RCSB PDB, Rutgers, or UCSF.`
- Shipped files (`.claude-plugin`, `skills`, `agents`, `scripts`, `README.md`) contain no `/home/`, `arthur/`, `ihm_latest`, `work/validation`, or `pdb-ihm-ops`.
- Skills and the agent reference bundled files only through `${CLAUDE_PLUGIN_ROOT}/...` or `${CLAUDE_SKILL_DIR}/...` (both verified to be substituted in SKILL.md and agent bodies).
- The checker depends only on `ihm>=2.11` and `msgpack` (PEP 723 header); it must not import gemmi.
- Checker output is always labeled `Local pre-check, not PDB-IHM validation.`; nothing in the plugin presents its own output as a PDB-IHM assessment.
- Production server by default; `--mode dev` only when the user asks. Every upload and every server state change is confirmed in chat first; `-y` is passed only after that confirmation.
- Never install packages without asking the user.
- Development environment: `.venv/` in the repository root (gitignored), created in Task 1. Run tests with `.venv/bin/python -m pytest`. Tests marked `network` download the wwPDB dictionaries (~6 MB) and CCD files once per session.
- Commit after every task; every commit carries the two trailers shown in the commit steps.
- All code in this plan was prototyped and its full test suite (100 tests) run against python-ihm 2.11 before the plan was written, and the plan itself was replayed task by task in a fresh directory. Transcribe file contents exactly.

## Review Focus

Inputs real users will send that the spec does not mention; each is pinned by a test in the owning task:

1. **Windows line endings (CRLF)** from depositors' tools must give the same results as LF. Task 2, `test_inventory_crlf_line_endings`.
2. **Uppercase or mixed-case tags** (`_IHM_DATASET_LIST.ID`; mmCIF is case-insensitive) must be read like lowercase. Task 2 `test_tags_are_case_insensitive`, Task 4 `test_linkage_reads_uppercase_tags`.
3. **Several data blocks in one file** must all be read, not just the first. Task 4, `test_read_two_data_blocks`.
4. **An unwritable cache directory** (containers, read-only home) must make the dictionary stage NOT CHECKED, not crash the checker. Task 2, `test_unwritable_cache_dir_is_unavailable_not_a_crash`.
5. **Paths with spaces and non-ASCII characters** (`my models (v2)/entrée 1.cif`) must work end to end. Task 7, `test_path_with_spaces_and_unicode`.

## File map

| Path | Responsibility | Task |
|---|---|---|
| `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` | Plugin and single-plugin marketplace manifests | 1 |
| `README.md`, `.gitignore`, `pytest.ini` | Docs (disclaimer first), ignores, pytest markers (`LICENSE` already exists from the repository's initial commit) | 1, 15 |
| `tests/test_repo.py` | Manifests, disclaimer, frontmatter, referenced paths, portability, expected files | 1 (+8-14) |
| `skills/check/scripts/ihmcheck_io.py` | File formats, generic table/inventory reading, dictionary and CCD cache | 2 |
| `tests/conftest.py` | Minimal valid IHMCIF fixture (python-ihm) and helpers | 2 |
| `skills/check/scripts/ihmcheck_stages.py` | Finding model and stages 1-7 | 3-6 |
| `skills/check/scripts/check_entry.py` | CLI, orchestration, verdict, text/JSON output | 7 |
| `scripts/probe.sh` | Reports available tools; installs nothing | 8 |
| `skills/ihmcif/` | Knowledge skill: data model, tooling pitfalls | 9 |
| `skills/check/SKILL.md` | Pre-check workflow | 10 |
| `skills/validate/` | IHMValidation via server or local image; report reference | 11 |
| `skills/build/` | python-ihm build workflow and patterns; `tests/test_build_patterns.py` | 12 |
| `skills/deposit/SKILL.md` | ihmdep deposition lifecycle | 13 |
| `agents/curator.md` | Generalized curator agent | 14 |

---


### Task 1: Repository scaffold, manifests, and disclaimer

Creates the plugin skeleton and the repository-level tests that guard the manifests, the unofficial-status disclaimer (spec 6.1), skill and agent frontmatter, referenced paths, and portability.

**Files:**
- Create: `.claude-plugin/plugin.json`
- Create: `.claude-plugin/marketplace.json`
- Create: `README.md`
- Create: `.gitignore`
- Create: `pytest.ini`
- Test: `tests/test_repo.py`

**Interfaces:**
- Produces: `tests/test_repo.py` with `EXPECTED_FILES` (later tasks append to it), `frontmatter(path)`, and parametrized checks that automatically cover every `skills/*/SKILL.md` and `agents/*.md` added later.

- [ ] **Step 1: Set up the development environment**

The working directory already tracks https://github.com/aozalevsky/ihmtools_claude as `origin`, and its initial commit provides `LICENSE` (MIT, Arthur Zalevsky); do not recreate it. Confirm with `git remote -v` (shows `origin`) and `head -1 LICENSE` (prints `MIT License`).

Create the development environment (once; `.venv/` is gitignored):

```bash
python3 -m venv .venv
.venv/bin/pip install ihm msgpack pytest gemmi ihmtools uv
```

Expected: installs ihm 2.11 or newer; `.venv/bin/uv --version` prints a version.

- [ ] **Step 2: Write the test `tests/test_repo.py`**

```python
"""Repository-level checks: manifests, disclaimer, skills, agents, portability."""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHORT_DISCLAIMER = ('Unofficial, community plugin, not affiliated with RCSB PDB, '
                    'Rutgers, or UCSF.')
README_DISCLAIMER = """\
> **Unofficial plugin.** ihmtools is an independent project. It is not
> affiliated with, endorsed by, or supported by RCSB PDB, Rutgers, The State
> University of New Jersey, or the University of California, San Francisco
> (UCSF). PDB-IHM, IHMValidation, python-ihm, and the `ihmv`/`ihmdep`
> command-line tools are developed and maintained by their own authors; this
> plugin only helps Claude use them. Names are used solely to identify those
> tools and services."""
REPO_URL = 'https://github.com/aozalevsky/ihmtools_claude'
SHIPPED = ['.claude-plugin', 'skills', 'agents', 'scripts', 'README.md']
EXPECTED_FILES = [
    '.claude-plugin/plugin.json', '.claude-plugin/marketplace.json', 'README.md',
    'LICENSE', '.gitignore', 'pytest.ini',
]
SKILLS = sorted(p.parent for p in ROOT.glob('skills/*/SKILL.md'))
AGENTS = sorted(ROOT.glob('agents/*.md'))


def frontmatter(path):
    """Parse the simple YAML frontmatter used here: scalars and '- item' lists."""
    text = path.read_text(encoding='utf-8')
    assert text.startswith('---\n'), f'{path} has no frontmatter'
    block = text.split('---\n', 2)[1]
    data, key = {}, None
    for line in block.splitlines():
        if line.startswith('  - ') and key:
            data.setdefault(key, []).append(line[4:].strip())
        elif ':' in line:
            key, _, value = line.partition(':')
            key, value = key.strip(), value.strip()
            if value:
                data[key] = value
    return data, text.split('---\n', 2)[2]


def manifest(name):
    return json.loads((ROOT / '.claude-plugin' / name).read_text(encoding='utf-8'))


@pytest.mark.parametrize('rel', EXPECTED_FILES)
def test_expected_file_exists(rel):
    assert (ROOT / rel).is_file()


def test_plugin_manifest():
    m = manifest('plugin.json')
    assert m['name'] == 'ihmtools'
    assert re.fullmatch(r'\d+\.\d+\.\d+', m['version'])
    assert m['description'].startswith(SHORT_DISCLAIMER)
    assert m['author'] == {'name': 'Arthur Zalevsky'}
    assert m['license'] == 'MIT'
    assert m['homepage'] == m['repository'] == REPO_URL


def test_marketplace_manifest_agrees_with_plugin():
    plugin, market = manifest('plugin.json'), manifest('marketplace.json')
    assert market['owner'] == {'name': 'Arthur Zalevsky'}
    assert market['description'].startswith(SHORT_DISCLAIMER)
    [entry] = market['plugins']
    assert (entry['name'], entry['source'], entry['version']) == \
        (plugin['name'], './', plugin['version'])
    assert entry['description'].startswith(SHORT_DISCLAIMER)
    assert entry['homepage'] == REPO_URL


def test_readme_opens_with_disclaimer():
    lines = (ROOT / 'README.md').read_text(encoding='utf-8').split('\n')
    assert lines[0] == '# ihmtools'
    assert '\n'.join(lines[2:9]) == README_DISCLAIMER


def test_license_is_mit():
    assert (ROOT / 'LICENSE').read_text(encoding='utf-8').startswith('MIT License')


@pytest.mark.parametrize('skill', SKILLS, ids=lambda p: p.name)
def test_skill_frontmatter(skill):
    meta, body = frontmatter(skill / 'SKILL.md')
    assert meta['name'] == skill.name
    assert 50 <= len(meta['description']) <= 1024
    assert body.strip()


@pytest.mark.parametrize('agent', AGENTS, ids=lambda p: p.stem)
def test_agent_frontmatter(agent):
    meta, body = frontmatter(agent)
    assert meta['name'] == agent.stem
    assert 50 <= len(meta['description']) <= 1024
    for skill in meta.get('skills', []):
        assert (ROOT / 'skills' / skill / 'SKILL.md').is_file(), skill
    assert body.strip()


def _shipped_text_files():
    for name in SHIPPED:
        path = ROOT / name
        files = [path] if path.is_file() else sorted(path.rglob('*'))
        yield from (f for f in files if f.is_file() and f.suffix in ('.md', '.json', '.py', '.sh'))


def test_referenced_plugin_paths_exist():
    for path in _shipped_text_files():
        text = path.read_text(encoding='utf-8')
        for rel in re.findall(r'\$\{CLAUDE_PLUGIN_ROOT\}/([\w./-]+)', text):
            assert (ROOT / rel).exists(), f'{path}: {rel}'
        for rel in re.findall(r'\$\{CLAUDE_SKILL_DIR\}/([\w./-]+)', text):
            assert (path.parent / rel).exists(), f'{path}: {rel}'


@pytest.mark.parametrize('pattern', ['/home/', 'arthur/', 'ihm_latest',
                                     'work/validation', 'pdb-ihm-ops'])
def test_nothing_machine_specific_is_shipped(pattern):
    hits = [str(p.relative_to(ROOT)) for p in _shipped_text_files()
            if pattern in p.read_text(encoding='utf-8')]
    assert hits == []
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_repo.py -q`

Expected: FAIL; the output contains `FileNotFoundError`.

- [ ] **Step 4: Write `.claude-plugin/plugin.json`**

```json
{
  "name": "ihmtools",
  "version": "0.1.0",
  "description": "Unofficial, community plugin, not affiliated with RCSB PDB, Rutgers, or UCSF. Helps Claude build, check, validate, and deposit integrative structures (IHMCIF) for PDB-IHM using python-ihm, IHMValidation, and the ihmv/ihmdep CLIs.",
  "author": {
    "name": "Arthur Zalevsky"
  },
  "homepage": "https://github.com/aozalevsky/ihmtools_claude",
  "repository": "https://github.com/aozalevsky/ihmtools_claude",
  "license": "MIT",
  "keywords": [
    "pdb-ihm",
    "ihmcif",
    "integrative-modeling",
    "structural-biology",
    "mmcif",
    "validation"
  ]
}
```

- [ ] **Step 5: Write `.claude-plugin/marketplace.json`**

```json
{
  "name": "ihmtools",
  "owner": {
    "name": "Arthur Zalevsky"
  },
  "description": "Unofficial, community plugin, not affiliated with RCSB PDB, Rutgers, or UCSF. Claude Code plugin for integrative structures and PDB-IHM.",
  "plugins": [
    {
      "name": "ihmtools",
      "source": "./",
      "description": "Unofficial, community plugin, not affiliated with RCSB PDB, Rutgers, or UCSF. Build, check, validate, and deposit integrative structures (IHMCIF) for PDB-IHM.",
      "version": "0.1.0",
      "homepage": "https://github.com/aozalevsky/ihmtools_claude",
      "category": "science"
    }
  ]
}
```

- [ ] **Step 6: Write `README.md`**

Initial version; Task 15 replaces it with the full README.

```markdown
# ihmtools

> **Unofficial plugin.** ihmtools is an independent project. It is not
> affiliated with, endorsed by, or supported by RCSB PDB, Rutgers, The State
> University of New Jersey, or the University of California, San Francisco
> (UCSF). PDB-IHM, IHMValidation, python-ihm, and the `ihmv`/`ihmdep`
> command-line tools are developed and maintained by their own authors; this
> plugin only helps Claude use them. Names are used solely to identify those
> tools and services.

A Claude Code plugin for integrative structures and the PDB-IHM toolchain.
Components are added as they are built; the design is in
`docs/superpowers/specs/2026-10-02-ihmtools-plugin-design.md`.

## License

MIT; see [LICENSE](LICENSE).
```

- [ ] **Step 7: Write `.gitignore`**

```text
.venv/
__pycache__/
.pytest_cache/
ihmtools-work/
*_validation/
```

- [ ] **Step 8: Write `pytest.ini`**

```ini
[pytest]
testpaths = tests
markers =
    network: needs internet access (wwPDB dictionaries, RCSB CCD)
```

- [ ] **Step 9: Run the tests and checks to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_repo.py -q`
Expected: `16 passed`

Run: `claude plugin validate .claude-plugin/plugin.json`
Expected: `Validation passed`

Run: `claude plugin validate .claude-plugin/marketplace.json`
Expected: `Validation passed`

- [ ] **Step 10: Commit**

```bash
git add .claude-plugin README.md .gitignore pytest.ini tests/test_repo.py
git commit -m "chore: scaffold ihmtools plugin with manifests and disclaimer" \
  --trailer "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" \
  --trailer "Claude-Session: https://claude.ai/code/session_012ee19x4Mb2BvMSdFbUvwzB"
```


### Task 2: Checker file access layer (`ihmcheck_io.py`) and test fixtures

All file reads go through python-ihm's low-level readers so `.cif`, `.cif.gz`, and `.bcif` share one code path (spec 5, "File access"). Also the dictionary/CCD cache. `conftest.py` builds a minimal valid IHMCIF entry with python-ihm; every later test mutates it.

**Files:**
- Create: `skills/check/scripts/ihmcheck_io.py`
- Create: `tests/conftest.py`
- Test: `tests/test_ihmcheck_io.py`

**Interfaces:**
- Produces (module `ihmcheck_io`, imported as `cio`): `Unavailable(Exception)`; `file_format(path) -> "BCIF"|"mmCIF"`; `open_entry(path)` (context manager); `read_tables(path, wanted: dict[str, list[str]]) -> dict[str, list[dict]]` (absent keyword or `.`/`?` value -> `None`); `inventory(path) -> dict[str, set[str]]` (lowercase names, no leading underscore); `cache_root(override=None) -> Path`; `fetch_cached(url, dest, offline, max_age=MAX_AGE) -> Path`; `load_dictionary(cache_dir, offline) -> ihm.dictionary.Dictionary`; `ccd_atoms(comp_id, cache_dir, offline) -> dict[atom_id, alt_atom_id]`; constants `CCD_URL`, `DICT_URL`, `DICT_FILES`, `MAX_AGE`.
- Produces (`tests/conftest.py`): `build_cif(atom_names=("CA","CA","CA")) -> str`, `replace_once(text, old, new)`, `to_bcif(cif_path, bcif_path) -> str`, `picked(findings, severity, category, keyword="")`; fixtures `write_entry`, `valid_cif`, `empty_cache`, `online_cache` (session-scoped).

- [ ] **Step 1: Write the test `tests/conftest.py`**

```python
"""Fixtures for check_entry.py: a minimal valid IHMCIF entry and mutations."""
import io
import os
import sys
from pathlib import Path

import pytest

import ihm
import ihm.cross_linkers
import ihm.dataset
import ihm.dumper
import ihm.location
import ihm.model
import ihm.protocol
import ihm.reader
import ihm.representation
import ihm.restraint

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills' / 'check' / 'scripts'
sys.path.insert(0, str(SCRIPTS))


def build_cif(atom_names=('CA', 'CA', 'CA')):
    """Return mmCIF text for a 3-residue, 1-model crosslink entry.

    `atom_names` gives the atom_id of the single atom on residues 1-3.
    The result validates cleanly against the PDBx + IHM dictionaries.
    """
    s = ihm.System(id='TEST')
    s.title = 'Minimal test entry'
    s.authors.append('Doe, J.')
    s.citations.append(ihm.Citation(
        pmid=None, title='Test', journal='J', volume='1', page_range=(1, 2),
        year='2026', authors=['Doe, J.'], doi='10.1/x'))
    entity = ihm.Entity('MKV', description='Test protein')
    s.entities.append(entity)
    asym = ihm.AsymUnit(entity, details='Chain A', id='A')
    s.asym_units.append(asym)
    assembly = ihm.Assembly([asym], name='Complete')
    dataset = ihm.dataset.CXMSDataset(ihm.location.PRIDELocation('PXD000001'))
    rep = ihm.representation.Representation(
        [ihm.representation.AtomicSegment(asym, rigid=False)])
    protocol = ihm.protocol.Protocol(name='Modeling')
    protocol.steps.append(ihm.protocol.Step(
        assembly=assembly, dataset_group=ihm.dataset.DatasetGroup([dataset]),
        method='Monte Carlo', num_models_begin=0, num_models_end=1))
    xl = ihm.restraint.CrossLinkRestraint(dataset, ihm.cross_linkers.dss)
    exp = ihm.restraint.ExperimentalCrossLink(entity.residue(1), entity.residue(3))
    xl.experimental_cross_links.append([exp])
    xl.cross_links.append(ihm.restraint.ResidueCrossLink(
        exp, asym, asym, ihm.restraint.UpperBoundDistanceRestraint(30.0)))
    s.restraints.append(xl)
    model = ihm.model.Model(assembly=assembly, protocol=protocol,
                            representation=rep, name='Model 1')
    for seq_id, (atom_id, x) in enumerate(zip(atom_names, (0., 3.8, 7.6)), start=1):
        model.add_atom(ihm.model.Atom(asym_unit=asym, seq_id=seq_id, atom_id=atom_id,
                                      type_symbol=atom_id.lstrip('0123456789')[0],
                                      x=x, y=0., z=0., het=False))
    group = ihm.model.ModelGroup([model], name='Group 1')
    s.state_groups.append(ihm.model.StateGroup([ihm.model.State([group])]))
    fh = io.StringIO()
    ihm.dumper.write(fh, [s])
    return fh.getvalue()


def replace_once(text, old, new):
    """str.replace that fails loudly if the fixture text has drifted."""
    assert text.count(old) == 1, f'expected exactly one {old!r} in fixture'
    return text.replace(old, new)


@pytest.fixture
def write_entry(tmp_path):
    """Write mmCIF text to tmp_path/<name> and return the path as str."""
    def _write(text, name='entry.cif'):
        path = tmp_path / name
        path.write_text(text, encoding='utf-8')
        return str(path)
    return _write


@pytest.fixture
def valid_cif():
    return build_cif()


@pytest.fixture
def empty_cache(tmp_path):
    path = tmp_path / 'empty-cache'
    path.mkdir()
    return str(path)


@pytest.fixture(scope='session')
def online_cache(tmp_path_factory):
    """A cache dir shared by network tests; dictionaries download once."""
    return str(tmp_path_factory.mktemp('ihmtools-cache'))


def to_bcif(cif_path, bcif_path):
    with open(cif_path, encoding='utf-8') as fh:
        systems = ihm.reader.read(fh)
    with open(bcif_path, 'wb') as fh:
        ihm.dumper.write(fh, systems, format='BCIF')
    return str(bcif_path)


def picked(findings, severity, category, keyword=''):
    """Findings (objects or JSON dicts) with this severity and anchor."""
    get = (lambda f, k: f[k]) if findings and isinstance(findings[0], dict) \
        else getattr
    return [f for f in findings if get(f, 'severity') == severity
            and get(f, 'category') == category and get(f, 'keyword') == keyword]
```

- [ ] **Step 2: Write the test `tests/test_ihmcheck_io.py`**

```python
import gzip
import os
import stat

import pytest

import ihmcheck_io as cio
from conftest import to_bcif


def test_file_format():
    assert cio.file_format('x.bcif') == 'BCIF'
    assert cio.file_format('x.BCIF') == 'BCIF'
    assert cio.file_format('x.cif') == 'mmCIF'
    assert cio.file_format('x.cif.gz') == 'mmCIF'


def test_inventory_sees_pair_and_loop_categories(write_entry, valid_cif):
    inv = cio.inventory(write_entry(valid_cif))
    assert 'title' in inv['struct']                 # single-row (pair) category
    assert {'label_atom_id', 'cartn_x'} <= inv['atom_site']    # loop category
    assert all(not c.startswith('_') for c in inv)


def test_inventory_gzip_and_bcif_match_cif(tmp_path, write_entry, valid_cif):
    cif = write_entry(valid_cif)
    gz = tmp_path / 'entry.cif.gz'
    with gzip.open(gz, 'wt', encoding='utf-8') as fh:
        fh.write(valid_cif)
    assert cio.inventory(str(gz)) == cio.inventory(cif)
    bcif = to_bcif(cif, tmp_path / 'entry.bcif')
    assert set(cio.inventory(cif)) <= set(cio.inventory(bcif))


def test_read_tables_rows_missing_and_special_values(write_entry, valid_cif):
    t = cio.read_tables(write_entry(valid_cif), {
        'ihm_dataset_list': ['id', 'data_type', 'no_such_keyword'],
        'ihm_sas_restraint': ['dataset_list_id'],
        'ihm_dataset_list_x': ['id'],
        'ihm_dataset_group': ['name']})
    assert t['ihm_dataset_list'] == [
        {'id': '1', 'data_type': 'Crosslinking-MS data', 'no_such_keyword': None}]
    assert t['ihm_sas_restraint'] == []
    assert t['ihm_dataset_list_x'] == []
    assert t['ihm_dataset_group'] == [{'name': None}]       # '.' in the file


def test_cache_root(monkeypatch, tmp_path):
    assert cio.cache_root(str(tmp_path)) == tmp_path
    monkeypatch.setenv('XDG_CACHE_HOME', str(tmp_path))
    assert cio.cache_root() == tmp_path / 'ihmtools'


def test_offline_without_cache_raises(tmp_path):
    with pytest.raises(cio.Unavailable, match='--offline'):
        cio.fetch_cached('https://example.invalid/x', tmp_path / 'x', offline=True)


def test_offline_uses_cache_of_any_age(tmp_path):
    dest = tmp_path / 'x'
    dest.write_text('cached')
    os.utime(dest, (0, 0))
    assert cio.fetch_cached('https://example.invalid/x', dest, offline=True) == dest


def test_stale_cache_used_when_download_fails(tmp_path, monkeypatch):
    dest = tmp_path / 'dictionaries' / 'x.dic'
    dest.parent.mkdir()
    dest.write_text('cached')
    os.utime(dest, (0, 0))  # far older than MAX_AGE

    def fail(*args, **kwargs):
        raise cio.urllib.error.URLError('no network')
    monkeypatch.setattr(cio.urllib.request, 'urlopen', fail)
    assert cio.fetch_cached('https://example.invalid/x.dic', dest, offline=False) == dest


def test_download_failure_without_cache_raises(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise cio.urllib.error.URLError('no network')
    monkeypatch.setattr(cio.urllib.request, 'urlopen', fail)
    with pytest.raises(cio.Unavailable):
        cio.fetch_cached('https://example.invalid/x', tmp_path / 'x', offline=False)
    assert not (tmp_path / 'x').exists()


@pytest.mark.parametrize('comp_id', ['../etc', '', 'TOOLONG', 'A B', None])
def test_ccd_rejects_unsafe_component_ids(tmp_path, comp_id):
    with pytest.raises(cio.Unavailable):
        cio.ccd_atoms(comp_id, tmp_path, offline=False)


@pytest.mark.network
def test_ccd_atoms_has_alt_names(online_cache):
    atoms = cio.ccd_atoms('MET', online_cache, offline=False)
    assert atoms['HB2'] == '1HB'
    assert atoms['CA'] == 'CA'


@pytest.mark.network
def test_load_dictionary_merges_pdbx_and_ihm(online_cache):
    d = cio.load_dictionary(online_cache, offline=False)
    assert 'atom_site' in d.categories and 'ihm_dataset_list' in d.categories


def test_inventory_crlf_line_endings(tmp_path, valid_cif):
    crlf = tmp_path / 'crlf.cif'
    crlf.write_bytes(valid_cif.replace('\n', '\r\n').encode('utf-8'))
    lf = tmp_path / 'lf.cif'
    lf.write_text(valid_cif, encoding='utf-8')
    assert cio.inventory(str(crlf)) == cio.inventory(str(lf))


def test_tags_are_case_insensitive(write_entry, valid_cif):
    path = write_entry(valid_cif.replace('_ihm_dataset_list.', '_IHM_DATASET_LIST.'))
    assert 'ihm_dataset_list' in cio.inventory(path)
    assert cio.read_tables(path, {'ihm_dataset_list': ['id']}) == {
        'ihm_dataset_list': [{'id': '1'}]}


@pytest.mark.skipif(os.geteuid() == 0, reason='root ignores directory permissions')
def test_unwritable_cache_dir_is_unavailable_not_a_crash(tmp_path):
    readonly = tmp_path / 'readonly'
    readonly.mkdir()
    readonly.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        with pytest.raises(cio.Unavailable):
            cio.fetch_cached('https://example.invalid/x', readonly / 'sub' / 'x',
                             offline=False)
    finally:
        readonly.chmod(stat.S_IRWXU)
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_ihmcheck_io.py -q -m "not network"`

Expected: FAIL; the output contains `No module named 'ihmcheck_io'`.

- [ ] **Step 4: Write `skills/check/scripts/ihmcheck_io.py`**

```python
"""File and cache access for check_entry.py.

Every read goes through python-ihm's low-level readers, so .cif, .cif.gz and
.bcif files share one code path.
"""
import gzip
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

import ihm.dictionary
import ihm.format
import ihm.format_bcif

DICT_URL = 'https://mmcif.wwpdb.org/dictionaries/ascii/'
DICT_FILES = ('mmcif_pdbx_v50.dic', 'mmcif_ihm_ext.dic')
CCD_URL = 'https://files.rcsb.org/ligands/download/{}.cif'
MAX_AGE = 30 * 24 * 3600
_COMP_ID = re.compile(r'[A-Za-z0-9]{1,5}')


class Unavailable(Exception):
    """A remote resource could not be obtained and is not cached."""


def file_format(path):
    """Return 'BCIF' for BinaryCIF input, else 'mmCIF'."""
    return 'BCIF' if str(path).lower().endswith('.bcif') else 'mmCIF'


def open_entry(path):
    """Open an entry file in the mode its format needs."""
    p = str(path)
    if file_format(p) == 'BCIF':
        return open(p, 'rb')
    if p.lower().endswith('.gz'):
        return gzip.open(p, 'rt', encoding='utf-8')
    return open(p, encoding='utf-8')


class _Collect:
    """Generic handler: records each row as a dict of the requested keys."""
    not_in_file = None
    omitted = None
    unknown = None

    def __init__(self, keys):
        self._keys = [k.lower() for k in keys]
        self.rows = []

    def __call__(self, *args):
        self.rows.append(dict(zip(self._keys, args)))


def _read(path, handlers, **callbacks):
    reader_cls = (ihm.format_bcif.BinaryCifReader
                  if file_format(path) == 'BCIF' else ihm.format.CifReader)
    with open_entry(path) as fh:
        reader = reader_cls(fh, handlers, **callbacks)
        while reader.read_file():
            pass


def read_tables(path, wanted):
    """Return {category: [row dicts]} for the requested keywords.

    `wanted` maps category names (no leading underscore) to keyword lists.
    Absent categories give empty lists; absent keywords and '.'/'?' values
    give None.
    """
    handlers = {'_' + c.lower(): _Collect(k) for c, k in wanted.items()}
    _read(path, handlers)
    return {c: handlers['_' + c.lower()].rows for c in wanted}


def inventory(path):
    """Return {category: set(keywords)} for everything in the file.

    Uses the readers' unknown-category/keyword callbacks, which fire for
    both loop and single-row (pair) categories.
    """
    cats = set()
    _read(path, {},
          unknown_category_handler=lambda cat, line: cats.add(cat.lower()))
    keys = {c: set() for c in cats}
    _read(path, {c: _Collect([]) for c in cats},
          unknown_keyword_handler=lambda cat, key, line:
              keys[cat.lower()].add(key.lower()))
    return {c.lstrip('_'): k for c, k in keys.items()}


def cache_root(override=None):
    """Cache directory: --cache-dir, else $XDG_CACHE_HOME/ihmtools."""
    if override:
        return Path(override)
    base = os.environ.get('XDG_CACHE_HOME') or os.path.join(
        os.path.expanduser('~'), '.cache')
    return Path(base) / 'ihmtools'


def fetch_cached(url, dest, offline, max_age=MAX_AGE):
    """Return a local path for `url`, downloading into `dest` when needed.

    A cached copy younger than `max_age` seconds is used as is. An older
    copy is refreshed when possible and used as a fallback when not.
    Raises Unavailable when there is no copy and none can be downloaded.
    """
    dest = Path(dest)
    if dest.exists() and (offline or time.time() - dest.stat().st_mtime < max_age):
        return dest
    if offline:
        raise Unavailable(f'{dest.name} is not cached and --offline was given')
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        part = dest.with_name(dest.name + '.part')
        with urllib.request.urlopen(url, timeout=60) as resp, open(part, 'wb') as fh:
            fh.write(resp.read())
        os.replace(part, dest)
        return dest
    except (urllib.error.URLError, OSError) as e:
        if dest.exists():
            return dest
        raise Unavailable(f'{url}: {e}') from e


def load_dictionary(cache_dir, offline):
    """Return the merged PDBx + IHM dictionary, or raise Unavailable."""
    merged = None
    for name in DICT_FILES:
        path = fetch_cached(DICT_URL + name, Path(cache_dir) / 'dictionaries' / name,
                            offline)
        with open(path, encoding='utf-8') as fh:
            d = ihm.dictionary.read(fh)
        merged = d if merged is None else merged + d
    return merged


def ccd_atoms(comp_id, cache_dir, offline):
    """Return {atom_id: alt_atom_id} for a CCD component, or raise Unavailable."""
    if not _COMP_ID.fullmatch(comp_id or ''):
        raise Unavailable(f'{comp_id!r} is not a valid CCD component id')
    comp_id = comp_id.upper()
    path = fetch_cached(CCD_URL.format(comp_id),
                        Path(cache_dir) / 'ccd' / f'{comp_id}.cif', offline)
    rows = read_tables(path, {'chem_comp_atom': ['atom_id', 'alt_atom_id']})
    return {r['atom_id']: r['alt_atom_id'] for r in rows['chem_comp_atom']}
```

- [ ] **Step 5: Run the tests and checks to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_ihmcheck_io.py -q -m "not network"`
Expected: `17 passed`

Run: `.venv/bin/python -m pytest tests/test_ihmcheck_io.py -q`
Expected: `19 passed`

- [ ] **Step 6: Commit**

```bash
git add skills/check/scripts/ihmcheck_io.py tests/conftest.py tests/test_ihmcheck_io.py
git commit -m "feat(check): add file access and cache layer for the checker" \
  --trailer "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" \
  --trailer "Claude-Session: https://claude.ai/code/session_012ee19x4Mb2BvMSdFbUvwzB"
```


### Task 3: Findings model, stage 1 (parse), stage 2 (dictionary)

Creates `ihmcheck_stages.py` with the shared data model and the first two stages. Later tasks append to this file in order, so the stage sections end up numbered 1-7.

**Files:**
- Create: `skills/check/scripts/ihmcheck_stages.py`
- Test: `tests/test_stage_parse_dictionary.py`

**Interfaces:**
- Consumes: `ihmcheck_io` (Task 2).
- Produces: `SEVERITIES = ("BLOCKER","ERROR","WARNING","NOTE")`; dataclasses `Finding(severity, category="", keyword="", row="", observed="", expected="", evidence="", fix="")` and `StageResult(name, status, detail="", findings=[])` with status in `ok|findings|not_checked|error`; helpers `_some`, `_result`, `_clean`, `_FIX`; `stage_parse(path) -> (StageResult, inventory|None)`; `stage_dictionary(path, cache_dir, offline) -> StageResult`.

- [ ] **Step 1: Write the test `tests/test_stage_parse_dictionary.py`**

```python
import re

import pytest

import ihmcheck_stages as st
from conftest import picked, replace_once

DANGLING = (r'(1 DSS) 1 \.', r'\1 99 .')     # crosslink list -> dataset 99


def test_parse_valid(write_entry, valid_cif):
    result, inv = st.stage_parse(write_entry(valid_cif))
    assert result.status == 'ok'
    assert 'ihm_dataset_list' in inv
    assert result.detail.endswith('items')


def test_parse_syntax_error_is_blocker(write_entry, valid_cif):
    bad = replace_once(valid_cif, "'Minimal test entry'", "'Minimal test entry")
    result, inv = st.stage_parse(write_entry(bad))
    assert inv is None
    [f] = result.findings
    assert f.severity == 'BLOCKER'
    assert 'CifParserError' in f.evidence and 'line' in f.evidence


def test_parse_non_utf8_is_blocker(tmp_path, valid_cif):
    path = tmp_path / 'latin1.cif'
    path.write_bytes(replace_once(valid_cif, "'Minimal test entry'",
                                  "'Minimal t\xe9st entry'").encode('latin-1'))
    result, inv = st.stage_parse(str(path))
    assert inv is None
    assert 'UnicodeDecodeError' in result.findings[0].evidence


def test_parse_empty_file_is_blocker(write_entry):
    result, inv = st.stage_parse(write_entry(''))
    assert inv is None
    assert result.detail == 'no data'
    assert result.findings[0].severity == 'BLOCKER'


def test_parse_without_ihm_categories_is_error(write_entry):
    result, inv = st.stage_parse(write_entry('data_x\n_entry.id x\n'))
    assert inv == {'entry': {'id'}}
    [f] = result.findings
    assert f.severity == 'ERROR' and 'no ihm_' in f.observed


def test_some_truncates():
    assert st._some('abc') == 'a, b, c'
    assert st._some(range(10), limit=3) == '0, 1, 2 (+7 more)'


def test_clean_strips_object_reprs():
    msg = '<ihm.model.Atom object at 0x7f00ab12> vs <ihm.representation.ResidueSegment object at 0x1>'
    assert st._clean(msg) == 'Atom vs ResidueSegment'
    assert st._clean('x' * 400).endswith('...')


def test_parse_validator_messages():
    def parse(msg):
        return list(st._parse_validator_message(msg))
    assert parse("Mandatory keyword struct.title cannot have value '?'") == [
        ('struct', 'title', "mandatory item is '?'", None, 'a value (mandatory item)')]
    assert parse('The following IDs referenced by _ihm_cross_link_list.dataset_list_id '
                 'were not defined in the parent category (_ihm_dataset_list.id): 7, 9'
                 ) == [('ihm_cross_link_list', 'dataset_list_id',
                        'reference to undefined id', v,
                        'ids defined in _ihm_dataset_list.id') for v in ('7', '9')]
    assert parse('The following keywords are not defined in the dictionary: '
                 '_struct.foo, _entry.bar') == [
        ('struct', 'foo', 'item not in dictionary', None,
         'items defined in PDBx or IHMCIF'),
        ('entry', 'bar', 'item not in dictionary', None,
         'items defined in PDBx or IHMCIF')]
    assert parse('something new') == [('', '', 'other', 'something new', '')]


def test_group_validator_errors_merges_rows():
    msg = ('Keyword atom_site.group_pdb value ATOMX is not a valid enumerated value '
           '(options are ATOM, HETATM)')
    [f] = st._group_validator_errors([msg, msg, msg])
    assert (f.severity, f.category, f.keyword) == ('ERROR', 'atom_site', 'group_pdb')
    assert f.observed == 'value not in enumeration (3 rows): ATOMX'
    assert f.expected == 'one of: ATOM, HETATM'


def test_dictionary_offline_without_cache_not_checked(write_entry, valid_cif,
                                                      empty_cache):
    result = st.stage_dictionary(write_entry(valid_cif), empty_cache, offline=True)
    assert result.status == 'not_checked'
    assert result.detail.startswith('dictionaries unavailable')


@pytest.mark.network
def test_dictionary_valid(write_entry, valid_cif, online_cache):
    result = st.stage_dictionary(write_entry(valid_cif), online_cache, offline=False)
    assert result.status == 'ok'


@pytest.mark.network
def test_dictionary_dangling_reference(write_entry, valid_cif, online_cache):
    bad = re.sub(*DANGLING, valid_cif)
    result = st.stage_dictionary(write_entry(bad), online_cache, offline=False)
    [f] = picked(result.findings, 'ERROR', 'ihm_cross_link_list', 'dataset_list_id')
    assert f.observed == 'reference to undefined id: 99'


@pytest.mark.network
def test_dictionary_repeated_violation_grouped(write_entry, valid_cif, online_cache):
    bad = re.sub(r'^ATOM ', 'ATOMX ', valid_cif, flags=re.M)
    result = st.stage_dictionary(write_entry(bad), online_cache, offline=False)
    # the validator reports keywords lowercased
    [f] = picked(result.findings, 'ERROR', 'atom_site', 'group_pdb')
    assert f.observed.startswith('value not in enumeration (3 rows): ATOMX')
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_stage_parse_dictionary.py -q -m "not network"`

Expected: FAIL; the output contains `No module named 'ihmcheck_stages'`.

- [ ] **Step 3: Write `skills/check/scripts/ihmcheck_stages.py`**

```python
"""The seven stages run by check_entry.py.

Each stage returns a StageResult; stages that later stages depend on also
return the data those stages need (the inventory, the python-ihm systems).
"""
import os
import re
import tempfile
import warnings
from dataclasses import dataclass, field

import ihm.dictionary
import ihm.dumper
import ihm.reader

import ihmcheck_io as cio

SEVERITIES = ('BLOCKER', 'ERROR', 'WARNING', 'NOTE')

@dataclass
class Finding:
    severity: str
    category: str = ''
    keyword: str = ''
    row: str = ''
    observed: str = ''
    expected: str = ''
    evidence: str = ''
    fix: str = ''


@dataclass
class StageResult:
    name: str
    status: str  # ok | findings | not_checked | error
    detail: str = ''
    findings: list = field(default_factory=list)


def _some(values, limit=8):
    """'a, b, c' or 'a, b, ... (+n more)' for display."""
    values = list(values)
    shown = ', '.join(str(v) for v in values[:limit])
    return shown + (f' (+{len(values) - limit} more)' if len(values) > limit else '')


def _result(name, findings, detail):
    return StageResult(name, 'findings' if findings else 'ok', detail, findings)


def _clean(msg, limit=300):
    """Strip python-ihm object reprs and cap length for display."""
    msg = re.sub(r'<ihm\.[\w.]+\.(\w+) object at 0x[0-9a-f]+>', r'\1', msg)
    return msg if len(msg) <= limit else msg[:limit] + '...'


# ---- stage 1 -------------------------------------------------------------

def stage_parse(path):
    """Parse the file and inventory it. Returns (result, inventory or None)."""
    try:
        inv = cio.inventory(path)
    except Exception as e:  # any failure here means nothing else can run
        return StageResult('parse', 'findings', 'file could not be parsed', [Finding(
            'BLOCKER',
            observed=f'the file cannot be parsed as {cio.file_format(path)}',
            expected='a syntactically valid mmCIF or BinaryCIF file',
            evidence=f'{type(e).__name__}: {_clean(str(e))}',
            fix='repair the syntax at the reported location; '
                'no other check can run until the file parses')]), None
    if not inv:
        return StageResult('parse', 'findings', 'no data', [Finding(
            'BLOCKER', observed='the file contains no categories',
            expected='a data block describing the entry',
            fix='check that this is the right file')]), None
    findings = []
    if not any(c.startswith('ihm_') for c in inv):
        findings.append(Finding(
            'ERROR',
            observed='the file has no ihm_* categories',
            expected='an integrative (IHMCIF) entry; PDB-IHM requires the IHM '
                     'extension',
            evidence=f'{len(inv)} categories, none starting with ihm_',
            fix='check this is the integrative model file you meant to use; '
                'other findings may be consequences of this one'))
    nkeys = sum(len(k) for k in inv.values())
    return _result('parse', findings, f'{len(inv)} categories, {nkeys} items'), inv


# ---- stage 2 -------------------------------------------------------------

_FIX = {
    "mandatory item is '?'": "supply the value; if it is a fact about the "
                             "study, depositor input is required",
    'mandatory item is missing': 'add the item',
    'mandatory category is missing': 'add the category',
    'value not in enumeration': 'use one of the allowed values',
    'value does not match item type': 'correct the value format',
    'reference to undefined id': 'define the id in the parent category, '
                                 'or correct the reference',
    'category not in dictionary': 'remove it or correct the name '
                                  '(check the spelling against the dictionary)',
    'item not in dictionary': 'remove it or correct the name '
                              '(check the spelling against the dictionary)',
}


def _parse_validator_message(msg):
    """Yield (category, keyword, problem, value, expected) for one message."""
    m = re.match(r"Mandatory keyword (\w+)\.(\S+) cannot have value '\?'$", msg)
    if m:
        yield m[1], m[2], "mandatory item is '?'", None, 'a value (mandatory item)'
        return
    m = re.match(r'Mandatory keyword (\w+)\.(\S+) cannot be missing from the file$', msg)
    if m:
        yield m[1], m[2], 'mandatory item is missing', None, 'the item (mandatory)'
        return
    m = re.match(r'Keyword (\w+)\.(\S+) value (.*) is not a valid enumerated '
                 r'value \(options are (.*)\)$', msg, re.S)
    if m:
        yield m[1], m[2], 'value not in enumeration', m[3], 'one of: ' + m[4]
        return
    m = re.match(r'Keyword (\w+)\.(\S+) value (.*) does not match item type '
                 r'\((.*?)\) regular expression', msg, re.S)
    if m:
        yield m[1], m[2], 'value does not match item type', m[3], f'type {m[4]}'
        return
    m = re.match(r'The following IDs referenced by _(\w+)\.(\S+) were not defined '
                 r'in the parent category \(_(\w+)\.(\S+)\): (.*)$', msg, re.S)
    if m:
        for value in m[5].split(', '):
            yield (m[1], m[2], 'reference to undefined id', value,
                   f'ids defined in _{m[3]}.{m[4]}')
        return
    m = re.match(r'The following mandatory categories are missing in the file: (.*)$',
                 msg, re.S)
    if m:
        for cat in m[1].split(', '):
            yield cat, '', 'mandatory category is missing', None, 'the category'
        return
    m = re.match(r'The following categories are not defined in the dictionary: (.*)$',
                 msg, re.S)
    if m:
        for cat in m[1].split(', '):
            yield (cat.lstrip('_'), '', 'category not in dictionary', None,
                   'categories defined in PDBx or IHMCIF')
        return
    m = re.match(r'The following keywords are not defined in the dictionary: (.*)$',
                 msg, re.S)
    if m:
        for item in m[1].split(', '):
            cat, _, key = item.lstrip('_').partition('.')
            yield (cat, key, 'item not in dictionary', None,
                   'items defined in PDBx or IHMCIF')
        return
    yield '', '', 'other', msg, ''


def _group_validator_errors(messages):
    groups = {}
    for msg in messages:
        for cat, key, problem, value, expected in _parse_validator_message(msg):
            g = groups.setdefault((cat, key, problem),
                                  {'n': 0, 'values': [], 'expected': expected,
                                   'msg': msg})
            g['n'] += 1
            if value is not None and value not in g['values']:
                g['values'].append(value)
    findings = []
    for (cat, key, problem), g in groups.items():
        observed = problem if problem != 'other' else 'dictionary violation'
        if g['n'] > 1:
            observed += f" ({g['n']} rows)"
        if g['values'] and problem != 'other':
            observed += ': ' + _some(g['values'], limit=5)
        findings.append(Finding(
            'ERROR', cat, key, observed=observed, expected=g['expected'],
            evidence='ihm.dictionary: ' + _clean(g['msg']),
            fix=_FIX.get(problem, 'see the evidence')))
    return findings


def stage_dictionary(path, cache_dir, offline):
    """Validate against the merged PDBx + IHM dictionaries."""
    try:
        dictionary = cio.load_dictionary(cache_dir, offline)
    except cio.Unavailable as e:
        return StageResult('dictionary', 'not_checked', f'dictionaries unavailable: {e}')
    try:
        with cio.open_entry(path) as fh:
            dictionary.validate(fh, format=cio.file_format(path))
    except ihm.dictionary.ValidatorError as e:
        findings = _group_validator_errors(str(e).split('\n\n'))
        return _result('dictionary', findings, 'PDBx + IHM dictionaries')
    return StageResult('dictionary', 'ok', 'PDBx + IHM dictionaries: no violations')
```

- [ ] **Step 4: Run the tests and checks to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_stage_parse_dictionary.py -q -m "not network"`
Expected: `10 passed`

Run: `.venv/bin/python -m pytest tests/test_stage_parse_dictionary.py -q`
Expected: `13 passed`

- [ ] **Step 5: Commit**

```bash
git add skills/check/scripts/ihmcheck_stages.py tests/test_stage_parse_dictionary.py
git commit -m "feat(check): add findings model, parse and dictionary stages" \
  --trailer "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" \
  --trailer "Claude-Session: https://claude.ai/code/session_012ee19x4Mb2BvMSdFbUvwzB"
```


### Task 4: Stage 3 (python-ihm read) and stage 4 (linkage)

Appends stages 3 and 4. Linkage reports unused datasets always, and dangling references only when the dictionary stage could not run (it reports them itself otherwise), so a dangling id is never reported twice.

**Files:**
- Modify: `skills/check/scripts/ihmcheck_stages.py` (append at end)
- Test: `tests/test_stage_read_linkage.py`

**Interfaces:**
- Consumes: Task 3 model and helpers.
- Produces: `stage_read(path) -> (StageResult, list[ihm.System]|None)`; `stage_linkage(path, dangling: bool) -> StageResult`; constants `DATASET_USERS`, `CORE_LINKS`.

- [ ] **Step 1: Write the test `tests/test_stage_read_linkage.py`**

```python
import re

import ihmcheck_stages as st
from conftest import picked, replace_once

DANGLING = (r'(1 DSS) 1 \.', r'\1 99 .')     # crosslink list -> dataset 99


def test_read_valid(write_entry, valid_cif):
    result, systems = st.stage_read(write_entry(valid_cif))
    assert result.status == 'ok'
    assert result.detail == '1 data block(s), 1 model(s)'
    assert len(systems) == 1


def test_read_exception_is_blocker(write_entry, valid_cif):
    # num_models_begin must be an integer: the file parses, python-ihm cannot read it
    bad = replace_once(valid_cif, "'Monte Carlo' 0 1", "'Monte Carlo' x 1")
    result, systems = st.stage_read(write_entry(bad))
    assert systems is None
    [f] = result.findings
    assert f.severity == 'BLOCKER'
    assert f.evidence.startswith("ValueError: Cannot parse 'x' as integer")


def test_read_two_data_blocks(write_entry, valid_cif):
    text = valid_cif + valid_cif.replace('data_TEST', 'data_TEST2')
    result, systems = st.stage_read(write_entry(text))
    assert result.detail == '2 data block(s), 2 model(s)'


def test_linkage_valid_has_no_findings(write_entry, valid_cif):
    assert st.stage_linkage(write_entry(valid_cif), dangling=True).status == 'ok'


def test_linkage_reports_dangling_only_when_asked(write_entry, valid_cif):
    path = write_entry(re.sub(*DANGLING, valid_cif))
    with_check = st.stage_linkage(path, dangling=True)
    [f] = picked(with_check.findings, 'ERROR', 'ihm_cross_link_list', 'dataset_list_id')
    assert '99' in f.observed and f.evidence == '_ihm_dataset_list.id has: 1'
    without = st.stage_linkage(path, dangling=False)
    assert not picked(without.findings, 'ERROR', 'ihm_cross_link_list', 'dataset_list_id')


def test_linkage_unused_dataset_warns(write_entry, valid_cif):
    text = replace_once(valid_cif, "1 'Crosslinking-MS data' YES .",
                        "1 'Crosslinking-MS data' YES .\n2 'SAS data' NO .")
    result = st.stage_linkage(write_entry(text), dangling=False)
    [f] = picked(result.findings, 'WARNING', 'ihm_dataset_list', 'id')
    assert f.row == 'id 2' and '(SAS data)' in f.observed


def test_linkage_primary_of_used_dataset_is_used(write_entry, valid_cif):
    text = replace_once(valid_cif, "1 'Crosslinking-MS data' YES .",
                        "1 'Crosslinking-MS data' YES .\n2 'Mass Spectrometry data' NO .\n"
                        "3 'Mass Spectrometry data' NO .")
    text += ('#\nloop_\n_ihm_related_datasets.dataset_list_id_derived\n'
             '_ihm_related_datasets.dataset_list_id_primary\n'
             '_ihm_related_datasets.transformation_id\n1 2 .\n2 3 .\n#\n')
    result = st.stage_linkage(write_entry(text), dangling=True)
    assert result.status == 'ok', result.findings   # 3 is used via 1 -> 2 -> 3


def test_linkage_reads_uppercase_tags(write_entry, valid_cif):
    text = valid_cif.replace('_ihm_dataset_list.', '_IHM_DATASET_LIST.')
    assert st.stage_linkage(write_entry(text), dangling=True).status == 'ok'
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_stage_read_linkage.py -q`

Expected: FAIL; the output contains `has no attribute 'stage_read'`.

- [ ] **Step 3: Append to `skills/check/scripts/ihmcheck_stages.py`**

Append this to the end of the file, separated from the existing last line by exactly two blank lines:

```python
# ---- stage 3 -------------------------------------------------------------

def stage_read(path):
    """Read with python-ihm. Returns (result, systems or None)."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            with cio.open_entry(path) as fh:
                systems = ihm.reader.read(fh, format=cio.file_format(path))
    except Exception as e:
        return StageResult('read', 'findings', 'python-ihm could not read the file', [
            Finding('BLOCKER',
                    observed='python-ihm raised an exception while reading',
                    expected='a file python-ihm can read',
                    evidence=f'{type(e).__name__}: {_clean(str(e))}',
                    fix='find the item named in the exception; the curator '
                        'agent can bisect this')]), None
    nmodels = sum(1 for s in systems for _ in s._all_models())
    return (StageResult('read', 'ok', f'{len(systems)} data block(s), {nmodels} model(s)'),
            systems)


# ---- stage 4 -------------------------------------------------------------

# Categories whose dataset_list_id means "this dataset was used for modeling".
DATASET_USERS = (
    'ihm_2dem_class_average_restraint', 'ihm_3dem_restraint',
    'ihm_cross_link_list', 'ihm_derived_angle_restraint',
    'ihm_derived_dihedral_restraint', 'ihm_derived_distance_restraint',
    'ihm_epr_restraint', 'ihm_geometric_object_distance_restraint',
    'ihm_hdx_restraint', 'ihm_hydroxyl_radical_fp_restraint',
    'ihm_interface_residue_feature', 'ihm_ligand_probe',
    'ihm_poly_probe_conjugate', 'ihm_predicted_contact_restraint',
    'ihm_sas_restraint', 'ihm_starting_model_details',
)

# (child category, child keyword, parent category, parent keyword); used for
# dangling-reference checks only when dictionary validation could not run.
CORE_LINKS = (
    ('ihm_model_group_link', 'model_id', 'ihm_model_list', 'model_id'),
    ('ihm_model_group_link', 'group_id', 'ihm_model_group', 'id'),
    ('ihm_model_list', 'assembly_id', 'ihm_struct_assembly', 'id'),
    ('ihm_model_list', 'protocol_id', 'ihm_modeling_protocol', 'id'),
    ('ihm_model_list', 'representation_id', 'ihm_model_representation', 'id'),
    ('ihm_model_representation_details', 'representation_id',
     'ihm_model_representation', 'id'),
    ('ihm_struct_assembly_details', 'assembly_id', 'ihm_struct_assembly', 'id'),
    ('ihm_modeling_protocol_details', 'protocol_id', 'ihm_modeling_protocol', 'id'),
    ('ihm_modeling_protocol_details', 'dataset_group_id', 'ihm_dataset_group', 'id'),
    ('ihm_dataset_group_link', 'group_id', 'ihm_dataset_group', 'id'),
    ('ihm_dataset_group_link', 'dataset_list_id', 'ihm_dataset_list', 'id'),
    ('ihm_dataset_related_db_reference', 'dataset_list_id', 'ihm_dataset_list', 'id'),
    ('ihm_dataset_external_reference', 'dataset_list_id', 'ihm_dataset_list', 'id'),
    ('ihm_dataset_external_reference', 'file_id', 'ihm_external_files', 'id'),
    ('ihm_external_files', 'reference_id', 'ihm_external_reference_info',
     'reference_id'),
    ('ihm_related_datasets', 'dataset_list_id_derived', 'ihm_dataset_list', 'id'),
    ('ihm_related_datasets', 'dataset_list_id_primary', 'ihm_dataset_list', 'id'),
    ('ihm_starting_comparative_models', 'template_dataset_list_id',
     'ihm_dataset_list', 'id'),
) + tuple((c, 'dataset_list_id', 'ihm_dataset_list', 'id') for c in DATASET_USERS)


def _want(wanted, cat, key):
    keys = wanted.setdefault(cat, [])
    if key not in keys:
        keys.append(key)


def stage_linkage(path, dangling):
    """Find unused datasets; with `dangling`, also undefined references."""
    wanted = {}
    for c in DATASET_USERS:
        _want(wanted, c, 'dataset_list_id')
    _want(wanted, 'ihm_starting_comparative_models', 'template_dataset_list_id')
    _want(wanted, 'ihm_related_datasets', 'dataset_list_id_derived')
    _want(wanted, 'ihm_related_datasets', 'dataset_list_id_primary')
    _want(wanted, 'ihm_dataset_list', 'id')
    _want(wanted, 'ihm_dataset_list', 'data_type')
    if dangling:
        for child, ckey, parent, pkey in CORE_LINKS:
            _want(wanted, child, ckey)
            _want(wanted, parent, pkey)
    t = cio.read_tables(path, wanted)

    used = {r['dataset_list_id'] for c in DATASET_USERS for r in t[c]}
    used |= {r['template_dataset_list_id'] for r in t['ihm_starting_comparative_models']}
    used.discard(None)
    primaries = {}
    for r in t['ihm_related_datasets']:
        primaries.setdefault(r['dataset_list_id_derived'], set()).add(
            r['dataset_list_id_primary'])
    stack = list(used)
    while stack:
        for p in primaries.get(stack.pop(), ()):
            if p is not None and p not in used:
                used.add(p)
                stack.append(p)

    findings = []
    for r in t['ihm_dataset_list']:
        if r['id'] is not None and r['id'] not in used:
            findings.append(Finding(
                'WARNING', 'ihm_dataset_list', 'id', f"id {r['id']}",
                observed=f"dataset {r['id']} ({r['data_type']}) is not used by any "
                         "restraint, feature, or starting model",
                expected='every deposited dataset to be used by the modeling',
                evidence='no dataset_list_id reference to it, directly or as the '
                         'primary of a used dataset in _ihm_related_datasets',
                fix='reference it from the restraint or starting model that used '
                    'it; if it was not used, remove it or link it as the primary '
                    'of a used dataset in _ihm_related_datasets'))
    if not dangling:
        return _result('linkage', findings,
                       'dataset usage (references were checked by the dictionary stage)')
    for child, ckey, parent, pkey in CORE_LINKS:
        defined = {r[pkey] for r in t[parent]}
        missing = sorted({r[ckey] for r in t[child]} - defined - {None})
        if missing:
            findings.append(Finding(
                'ERROR', child, ckey,
                observed='reference to undefined id: ' + ', '.join(missing),
                expected=f'ids defined in _{parent}.{pkey}',
                evidence=f'_{parent}.{pkey} has: '
                         + (', '.join(sorted(defined - {None})) or 'no rows'),
                fix=_FIX['reference to undefined id']))
    return _result('linkage', findings,
                   'dataset usage and core references (dictionary not available)')
```

- [ ] **Step 4: Run the tests and checks to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_stage_read_linkage.py -q`
Expected: `8 passed`

- [ ] **Step 5: Commit**

```bash
git add skills/check/scripts/ihmcheck_stages.py tests/test_stage_read_linkage.py
git commit -m "feat(check): add python-ihm read and linkage stages" \
  --trailer "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" \
  --trailer "Claude-Session: https://claude.ai/code/session_012ee19x4Mb2BvMSdFbUvwzB"
```


### Task 5: Stage 5 (representation) and stage 6 (round-trip)

Stage 5 runs python-ihm's own write-time consistency check (`ihm.dumper._RangeChecker`) per atom/sphere and groups failures by problem across models and asyms (one bad assembly otherwise produces one finding per chain). Stage 6 reports only dropped items that carried a value.

**Files:**
- Modify: `skills/check/scripts/ihmcheck_stages.py` (append at end)
- Test: `tests/test_stage_model.py`

**Interfaces:**
- Consumes: `stage_read`, `stage_parse` (for tests), `cio.inventory`, `cio.read_tables`.
- Produces: `stage_representation(systems) -> StageResult`; `stage_roundtrip(path, systems, original_inventory) -> StageResult`.

- [ ] **Step 1: Write the test `tests/test_stage_model.py`**

```python
import ihmcheck_stages as st
from conftest import picked, replace_once

ATOMS_IN_SPHERES = ('atomistic . flexible by-atom', 'sphere . flexible by-residue')


def systems_of(path):
    result, systems = st.stage_read(path)
    assert result.status == 'ok'
    return systems


def test_representation_valid(write_entry, valid_cif):
    result = st.stage_representation(systems_of(write_entry(valid_cif)))
    assert result.status == 'ok'
    assert result.detail == '3 atoms/spheres checked'


def test_representation_atoms_in_sphere_segment(write_entry, valid_cif):
    bad = replace_once(valid_cif, *ATOMS_IN_SPHERES)
    result = st.stage_representation(systems_of(write_entry(bad)))
    [f] = picked(result.findings, 'ERROR', 'atom_site', 'label_asym_id')
    assert f.row == 'models 1; asyms A'
    assert f.observed == ('3 atom(s) do not match the primitive of the covering '
                          'representation segment; first at model 1 asym A seq_id 1 '
                          'atom CA')
    assert 'object at 0x' not in f.evidence


def test_representation_missing_checker_not_checked(monkeypatch, write_entry, valid_cif):
    monkeypatch.delattr(st.ihm.dumper, '_RangeChecker')
    result = st.stage_representation(systems_of(write_entry(valid_cif)))
    assert result.status == 'not_checked'


def test_roundtrip_valid_has_no_notes(write_entry, valid_cif):
    path = write_entry(valid_cif)
    _, inv = st.stage_parse(path)
    result = st.stage_roundtrip(path, systems_of(path), inv)
    assert result.status == 'ok'


def test_roundtrip_unmodeled_category_is_note(write_entry, valid_cif):
    path = write_entry(valid_cif + "#\n_struct_keywords.entry_id TEST\n"
                                   "_struct_keywords.text 'X'\n")
    _, inv = st.stage_parse(path)
    result = st.stage_roundtrip(path, systems_of(path), inv)
    [f] = picked(result.findings, 'NOTE', 'struct_keywords')
    assert f.observed == 'the whole category would be dropped by a python-ihm rewrite'


def test_roundtrip_ignores_dropped_items_without_values(write_entry, valid_cif):
    path = write_entry(replace_once(
        valid_cif, "_struct.title 'Minimal test entry'\n",
        "_struct.title 'Minimal test entry'\n_struct.pdbx_descriptor .\n"))
    _, inv = st.stage_parse(path)
    assert 'pdbx_descriptor' in inv['struct']
    result = st.stage_roundtrip(path, systems_of(path), inv)
    assert result.status == 'ok'
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_stage_model.py -q`

Expected: FAIL; the output contains `has no attribute 'stage_`.

- [ ] **Step 3: Append to `skills/check/scripts/ihmcheck_stages.py`**

Append this to the end of the file, separated from the existing last line by exactly two blank lines:

```python
# ---- stage 5 -------------------------------------------------------------

_RANGE_PROBLEMS = (
    ('type of any representation segment',
     'do not match the primitive of the covering representation segment',
     'atoms only in atomic (by-atom) segments, spheres only in coarse-grained '
     'segments',
     'make _ihm_model_representation_details match the coordinates: declare '
     'these residues atomic, or deposit them as spheres'),
    ('representation',
     'are not covered by any representation segment of the model',
     "every atom or sphere covered by the model's representation",
     'extend _ihm_model_representation_details to cover these residues, or '
     'remove the coordinates'),
    ('assembly',
     "are outside the model's assembly",
     "every atom or sphere inside the model's assembly",
     'add these residues to the assembly (_ihm_struct_assembly_details) or '
     'remove the coordinates'),
    ('Multiple atoms with same',
     'are duplicates (same asym, seq_id, atom_id, alt_id)',
     'unique atoms',
     'remove or rename the duplicates; use alt_id for alternate conformations'),
)


def _classify_range_error(msg):
    for needle, observed, expected, fix in _RANGE_PROBLEMS:
        if needle in msg:
            return observed, expected, fix
    return 'were rejected by python-ihm', 'coordinates python-ihm can write', \
        'see the evidence'


def stage_representation(systems):
    """Report atoms/spheres python-ihm would refuse to write."""
    checker_cls = getattr(ihm.dumper, '_RangeChecker', None)
    if checker_cls is None:
        return StageResult('representation', 'not_checked',
                           'this python-ihm version has no _RangeChecker')
    groups = {}
    findings = []
    count = 0
    for system in systems:
        for _, model in system._all_models():
            try:
                checker = checker_cls(model, True)
            except Exception as e:
                findings.append(Finding(
                    'ERROR', 'ihm_model_list', '', f'model {model._id}',
                    observed="the model's representation or assembly cannot be "
                             'resolved',
                    expected='a model with a valid assembly and representation',
                    evidence=f'{type(e).__name__}: {_clean(str(e))}',
                    fix='check assembly_id and representation_id for this model'))
                continue
            for kind, objs in (('atom', model.get_atoms()),
                               ('sphere', model.get_spheres())):
                for obj in objs:
                    count += 1
                    try:
                        checker(obj)
                    except ValueError as e:
                        # One finding per problem, however many models/asyms
                        # share it: a single bad assembly can touch them all.
                        key = (kind, _classify_range_error(str(e)))
                        g = groups.setdefault(key, {
                            'n': 0, 'models': {}, 'asyms': {}, 'obj': obj,
                            'model': model._id, 'msg': str(e)})
                        g['n'] += 1
                        g['models'][model._id] = None
                        g['asyms'][obj.asym_unit._id] = None
    for (kind, (observed, expected, fix)), g in groups.items():
        obj = g['obj']
        if kind == 'atom':
            where = f"model {g['model']} asym {obj.asym_unit._id} seq_id {obj.seq_id} " \
                    f"atom {obj.atom_id}"
            cat, key = 'atom_site', 'label_asym_id'
        else:
            where = f"model {g['model']} asym {obj.asym_unit._id} " \
                    'seq_id {}-{}'.format(*obj.seq_id_range)
            cat, key = 'ihm_sphere_obj_site', 'asym_id'
        findings.append(Finding(
            'ERROR', cat, key,
            f"models {_some(g['models'])}; asyms {_some(g['asyms'])}",
            observed=f"{g['n']} {kind}(s) {observed}; first at {where}",
            expected=expected, evidence='python-ihm: ' + _clean(g['msg']), fix=fix))
    return _result('representation', findings, f'{count} atoms/spheres checked')


# ---- stage 6 -------------------------------------------------------------

def stage_roundtrip(path, systems, original):
    """Report valued items a python-ihm rewrite would drop.

    `original` is the stage-1 inventory. Items whose every value is '.' or
    '?' are not reported: dropping them loses nothing.
    """
    try:
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, 'roundtrip.cif')
            with open(out, 'w', encoding='utf-8') as fh:
                ihm.dumper.write(fh, systems, check=False)
            rewritten = cio.inventory(out)
    except Exception as e:
        return StageResult('roundtrip', 'findings', 'python-ihm could not write the file', [
            Finding('WARNING', observed='python-ihm cannot write this entry back out',
                    expected='a python-ihm read/write round-trip to succeed',
                    evidence=f'{type(e).__name__}: {_clean(str(e))}',
                    fix='the curator agent can locate the object that fails')])
    dropped = {cat: sorted(keys - rewritten.get(cat, set()))
               for cat, keys in original.items()}
    dropped = {cat: keys for cat, keys in dropped.items() if keys}
    values = cio.read_tables(path, dropped)
    findings = []
    for cat in sorted(dropped):
        lost = [k for k in dropped[cat]
                if any(row[k] is not None for row in values[cat])]
        if not lost:
            continue
        what = ('the whole category' if cat not in rewritten
                else 'items ' + ', '.join(lost))
        findings.append(Finding(
            'NOTE', cat,
            observed=f'{what} would be dropped by a python-ihm rewrite',
            expected='nothing; python-ihm does not model these items',
            evidence='present in the input, absent after ihm.dumper.write',
            fix='none needed; do not repair this file by rewriting it with '
                'python-ihm, or these items are lost'))
    return _result('roundtrip', findings, 'python-ihm read/write round-trip')
```

- [ ] **Step 4: Run the tests and checks to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_stage_model.py -q`
Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add skills/check/scripts/ihmcheck_stages.py tests/test_stage_model.py
git commit -m "feat(check): add representation and round-trip stages" \
  --trailer "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" \
  --trailer "Claude-Session: https://claude.ai/code/session_012ee19x4Mb2BvMSdFbUvwzB"
```


### Task 6: Stage 7 (atom names against the CCD)

Opt-in check for the dictionary's blind spot: atom nomenclature. Uses the CCD `alt_atom_id` column to suggest the current name.

**Files:**
- Modify: `skills/check/scripts/ihmcheck_stages.py` (append at end)
- Test: `tests/test_stage_atom_names.py`

**Interfaces:**
- Consumes: `cio.read_tables`, `cio.ccd_atoms`, `cio.CCD_URL`.
- Produces: `stage_atom_names(path, cache_dir, offline) -> StageResult`; `TERMINAL_ATOMS`.

- [ ] **Step 1: Write the test `tests/test_stage_atom_names.py`**

```python
import pytest

import ihmcheck_stages as st
from conftest import build_cif, picked


def test_atom_names_offline_without_cache_not_checked(write_entry, valid_cif,
                                                      empty_cache):
    result = st.stage_atom_names(write_entry(valid_cif), empty_cache, offline=True)
    assert result.status == 'not_checked'
    assert result.detail == 'CCD unavailable for LYS, MET, VAL'


def test_atom_names_without_atoms(write_entry):
    result = st.stage_atom_names(write_entry('data_x\n_entry.id x\n'), '/nonexistent',
                                 offline=True)
    assert (result.status, result.detail) == ('ok', 'no atom_site rows')


@pytest.mark.network
def test_atom_names_valid(write_entry, valid_cif, online_cache):
    result = st.stage_atom_names(write_entry(valid_cif), online_cache, offline=False)
    assert result.status == 'ok'
    assert result.detail == '3 component(s) against the CCD'


@pytest.mark.network
def test_obsolete_hydrogen_name_gets_rename(write_entry, online_cache):
    path = write_entry(build_cif(atom_names=('1HB', 'CA', 'OXT')))
    result = st.stage_atom_names(path, online_cache, offline=False)
    [f] = picked(result.findings, 'ERROR', 'atom_site', 'label_atom_id')
    assert f.row == 'comp_id MET'
    assert f.observed == 'atom names not in the CCD: 1HB'
    assert f.fix == 'rename 1HB -> HB2'
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_stage_atom_names.py -q -m "not network"`

Expected: FAIL; the output contains `has no attribute 'stage_atom_names'`.

- [ ] **Step 3: Append to `skills/check/scripts/ihmcheck_stages.py`**

Append this to the end of the file, separated from the existing last line by exactly two blank lines:

```python
# ---- stage 7 -------------------------------------------------------------

# Accepted in atom_site even though the CCD component does not list them.
TERMINAL_ATOMS = frozenset({'H1', 'H2', 'H3', 'OXT', 'HXT', 'OP3'})


def stage_atom_names(path, cache_dir, offline):
    """Compare atom_site atom names with the CCD."""
    rows = cio.read_tables(path, {'atom_site': ['label_comp_id', 'label_atom_id']})
    by_comp = {}
    for r in rows['atom_site']:
        if r['label_comp_id'] and r['label_atom_id']:
            by_comp.setdefault(r['label_comp_id'], set()).add(r['label_atom_id'])
    if not by_comp:
        return StageResult('atom_names', 'ok', 'no atom_site rows')
    findings, unchecked = [], []
    for comp in sorted(by_comp):
        try:
            ccd = cio.ccd_atoms(comp, cache_dir, offline)
        except cio.Unavailable:
            unchecked.append(comp)
            continue
        current = {alt: atom for atom, alt in ccd.items() if alt and alt != atom}
        bad = sorted(by_comp[comp] - set(ccd) - TERMINAL_ATOMS)
        if not bad:
            continue
        renames = [f'{b} -> {current[b]}' for b in bad if b in current]
        findings.append(Finding(
            'ERROR', 'atom_site', 'label_atom_id', f'comp_id {comp}',
            observed='atom names not in the CCD: ' + ', '.join(bad),
            expected=f'atom names from the CCD definition of {comp}',
            evidence=cio.CCD_URL.format(comp.upper()),
            fix=('rename ' + ', '.join(renames)) if renames
                else 'check these atoms against the CCD definition'))
    if len(unchecked) == len(by_comp):
        return StageResult('atom_names', 'not_checked',
                           'CCD unavailable for ' + ', '.join(unchecked))
    detail = f'{len(by_comp) - len(unchecked)} component(s) against the CCD'
    if unchecked:
        detail += '; CCD unavailable for ' + ', '.join(unchecked)
    return _result('atom_names', findings, detail)
```

- [ ] **Step 4: Run the tests and checks to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_stage_atom_names.py -q -m "not network"`
Expected: `2 passed`

Run: `.venv/bin/python -m pytest tests/test_stage_atom_names.py -q`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add skills/check/scripts/ihmcheck_stages.py tests/test_stage_atom_names.py
git commit -m "feat(check): add opt-in atom-name check against the CCD" \
  --trailer "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" \
  --trailer "Claude-Session: https://claude.ai/code/session_012ee19x4Mb2BvMSdFbUvwzB"
```


### Task 7: Command-line entry point (`check_entry.py`)

Orchestrates the stages, isolates crashes (`_guard`), computes the verdict (FAIL / INCOMPLETE / PASS: INCOMPLETE whenever a core stage did not run, so an offline first run never reads as a pass), and renders text or JSON. PEP 723 header so `uv run --script` works with no install.

**Files:**
- Create: `skills/check/scripts/check_entry.py`
- Test: `tests/test_check_entry.py`

**Interfaces:**
- Consumes: all stage functions (Tasks 3-6), `cio.cache_root`.
- Produces: CLI `check_entry.py FILE [--json] [--check-atom-names] [--cache-dir DIR] [--offline]`, exit 0/1/2; `main(argv) -> int`; `run_checks(path, cache_dir=None, offline=False, atom_names=False) -> list[StageResult]`; `verdict(results)`; `render_text`, `render_json`. JSON: `{"file","verdict","stages":[{"name","status","detail"}],"findings":[{"severity","category","keyword","row","observed","expected","evidence","fix"}]}`. The `check` skill (Task 10) and `curator` agent (Task 14) call it.

- [ ] **Step 1: Write the test `tests/test_check_entry.py`**

```python
import json
import re

import pytest

import check_entry
from conftest import picked, replace_once, to_bcif


def check(capsys, path, *flags):
    code = check_entry.main([path, '--json', *flags])
    return code, json.loads(capsys.readouterr().out)


def stage(report, name):
    return next(s for s in report['stages'] if s['name'] == name)


def test_missing_file_exits_2(capsys, tmp_path):
    assert check_entry.main([str(tmp_path / 'nope.cif')]) == 2
    assert 'cannot read' in capsys.readouterr().err


def test_bad_arguments_exit_2(capsys):
    with pytest.raises(SystemExit) as e:
        check_entry.main(['--no-such-flag'])
    assert e.value.code == 2


def test_offline_valid_entry_is_incomplete_not_pass(capsys, write_entry, valid_cif,
                                                    empty_cache):
    code, report = check(capsys, write_entry(valid_cif), '--offline',
                         '--cache-dir', empty_cache)
    assert code == 0
    assert report['verdict'] == 'INCOMPLETE'
    assert [s['name'] for s in report['stages']] == [
        'parse', 'dictionary', 'read', 'linkage', 'representation', 'roundtrip',
        'atom_names']
    assert stage(report, 'dictionary')['status'] == 'not_checked'
    assert 'core references' in stage(report, 'linkage')['detail']
    assert stage(report, 'atom_names')['detail'] == 'not requested (use --check-atom-names)'
    assert report['findings'] == []


def test_json_finding_fields(capsys, write_entry, valid_cif, empty_cache):
    bad = replace_once(valid_cif, 'atomistic . flexible by-atom',
                       'sphere . flexible by-residue')
    code, report = check(capsys, write_entry(bad), '--offline', '--cache-dir', empty_cache)
    assert code == 1 and report['verdict'] == 'FAIL'
    assert set(report['findings'][0]) == {'severity', 'category', 'keyword', 'row',
                                          'observed', 'expected', 'evidence', 'fix'}


def test_text_output(capsys, write_entry, valid_cif, empty_cache):
    text = replace_once(valid_cif, "1 'Crosslinking-MS data' YES .",
                        "1 'Crosslinking-MS data' YES .\n2 'SAS data' NO .")
    code = check_entry.main([write_entry(text), '--offline', '--cache-dir', empty_cache])
    out = capsys.readouterr().out
    assert code == 0
    assert out.startswith('INCOMPLETE: ')
    assert '(0 BLOCKER, 0 ERROR, 1 WARNING, 0 NOTE)' in out
    assert 'Local pre-check, not PDB-IHM validation.' in out
    assert '\n[WARNING] _ihm_dataset_list.id (id 2)\n  Observed: dataset 2' in out
    assert re.search(r'^Verified:\n  parse: ', out, re.M)
    assert re.search(r'^Not checked:\n  dictionary: dictionaries unavailable', out, re.M)


def test_syntax_error_stops_every_later_stage(capsys, write_entry, valid_cif,
                                              empty_cache):
    bad = replace_once(valid_cif, "'Minimal test entry'", "'Minimal test entry")
    code, report = check(capsys, write_entry(bad), '--offline', '--cache-dir', empty_cache)
    assert code == 1
    assert [f['severity'] for f in report['findings']] == ['BLOCKER']
    assert all(s['status'] == 'not_checked' for s in report['stages'][1:])


def test_unreadable_by_python_ihm_skips_model_stages(capsys, write_entry, valid_cif,
                                                     empty_cache):
    bad = replace_once(valid_cif, "'Monte Carlo' 0 1", "'Monte Carlo' x 1")
    code, report = check(capsys, write_entry(bad), '--offline', '--cache-dir', empty_cache)
    assert code == 1
    assert stage(report, 'linkage')['status'] == 'ok'
    assert stage(report, 'representation')['detail'] == 'python-ihm could not read the file'


def test_stage_crash_is_isolated(capsys, monkeypatch, write_entry, valid_cif,
                                 empty_cache):
    def boom(*args):
        raise RuntimeError('bug')
    monkeypatch.setattr(check_entry.st, 'stage_linkage', boom)
    code, report = check(capsys, write_entry(valid_cif), '--offline',
                         '--cache-dir', empty_cache)
    assert stage(report, 'linkage') == {
        'name': 'linkage', 'status': 'error',
        'detail': 'checker error: RuntimeError: bug'}
    assert stage(report, 'representation')['status'] == 'ok'
    assert report['verdict'] == 'INCOMPLETE'


def test_path_with_spaces_and_unicode(capsys, tmp_path, valid_cif):
    folder = tmp_path / 'my models (v2)'
    folder.mkdir()
    path = folder / 'entr\u00e9e 1.cif'
    path.write_text(valid_cif, encoding='utf-8')
    code, report = check(capsys, str(path), '--offline', '--cache-dir',
                         str(tmp_path / 'cache'))
    assert code == 0 and report['verdict'] == 'INCOMPLETE'
    assert report['file'] == str(path)


@pytest.mark.network
def test_valid_entry_passes(capsys, write_entry, valid_cif, online_cache):
    code, report = check(capsys, write_entry(valid_cif), '--cache-dir', online_cache,
                         '--check-atom-names')
    assert code == 0
    assert report['verdict'] == 'PASS'
    assert all(s['status'] == 'ok' for s in report['stages'])


@pytest.mark.network
def test_bcif_entry_passes(capsys, tmp_path, write_entry, valid_cif, online_cache):
    bcif = to_bcif(write_entry(valid_cif), tmp_path / 'entry.bcif')
    code, report = check(capsys, bcif, '--cache-dir', online_cache, '--check-atom-names')
    assert code == 0 and report['verdict'] == 'PASS'


@pytest.mark.network
def test_dangling_reference_reported_once(capsys, write_entry, valid_cif, online_cache):
    bad = re.sub(r'(1 DSS) 1 \.', r'\1 99 .', valid_cif)
    code, report = check(capsys, write_entry(bad), '--cache-dir', online_cache)
    assert code == 1
    [f] = picked(report['findings'], 'ERROR', 'ihm_cross_link_list', 'dataset_list_id')
    assert f['evidence'].startswith('ihm.dictionary')
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_check_entry.py -q -m "not network"`

Expected: FAIL; the output contains `No module named 'check_entry'`.

- [ ] **Step 3: Write `skills/check/scripts/check_entry.py`**

Then make it executable: `chmod +x skills/check/scripts/check_entry.py`.

```python
#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["ihm>=2.11", "msgpack"]
# ///
"""Local pre-check of an integrative-structure (IHMCIF) file.

This is not PDB-IHM validation; it catches problems before a file is sent
to validate.pdb-ihm.org or deposited.

Usage: check_entry.py FILE [--json] [--check-atom-names] [--cache-dir DIR] [--offline]
Exit codes: 0 no BLOCKER/ERROR, 1 at least one BLOCKER/ERROR, 2 could not run.
"""
import argparse
import json
import os
import sys
from dataclasses import asdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ihmcheck_io as cio  # noqa: E402
import ihmcheck_stages as st  # noqa: E402

CORE_STAGES = ('parse', 'dictionary', 'read', 'linkage', 'representation', 'roundtrip')
_RANK = {s: i for i, s in enumerate(st.SEVERITIES)}


def _guard(name, fn, *args):
    """Run a stage so that a bug in it cannot stop the other stages."""
    try:
        return fn(*args)
    except Exception as e:
        return st.StageResult(name, 'error', f'checker error: {type(e).__name__}: {e}')


def run_checks(path, cache_dir=None, offline=False, atom_names=False):
    """Run every stage on `path` and return the list of StageResults."""
    cache = cio.cache_root(cache_dir)
    parse, inventory = st.stage_parse(path)
    results = [parse]
    if inventory is None:
        reason = 'the file could not be parsed'
        results += [st.StageResult(n, 'not_checked', reason)
                    for n in CORE_STAGES[1:] + ('atom_names',)]
        return results
    dictionary = _guard('dictionary', st.stage_dictionary, path, cache, offline)
    results.append(dictionary)
    read, systems = st.stage_read(path)
    results.append(read)
    dictionary_ran = dictionary.status in ('ok', 'findings')
    results.append(_guard('linkage', st.stage_linkage, path, not dictionary_ran))
    if systems is None:
        reason = 'python-ihm could not read the file'
        results += [st.StageResult('representation', 'not_checked', reason),
                    st.StageResult('roundtrip', 'not_checked', reason)]
    else:
        results.append(_guard('representation', st.stage_representation, systems))
        results.append(_guard('roundtrip', st.stage_roundtrip, path, systems, inventory))
    if atom_names:
        results.append(_guard('atom_names', st.stage_atom_names, path, cache, offline))
    else:
        results.append(st.StageResult('atom_names', 'not_checked',
                                      'not requested (use --check-atom-names)'))
    return results


def findings_of(results):
    return sorted((f for r in results for f in r.findings),
                  key=lambda f: _RANK[f.severity])


def verdict(results):
    """FAIL on any BLOCKER/ERROR; INCOMPLETE if a core stage did not run."""
    if any(f.severity in ('BLOCKER', 'ERROR') for f in findings_of(results)):
        return 'FAIL'
    if any(r.name in CORE_STAGES and r.status in ('not_checked', 'error')
           for r in results):
        return 'INCOMPLETE'
    return 'PASS'


def _anchor(f):
    if not f.category:
        return '(file)'
    anchor = f'_{f.category}.{f.keyword}' if f.keyword else f'_{f.category}'
    return f'{anchor} ({f.row})' if f.row else anchor


def render_text(path, results):
    findings = findings_of(results)
    counts = ', '.join(f'{sum(f.severity == s for f in findings)} {s}'
                       for s in st.SEVERITIES)
    lines = [f'{verdict(results)}: {path} ({counts}). '
             'Local pre-check, not PDB-IHM validation.']
    for f in findings:
        lines.append('')
        lines.append(f'[{f.severity}] {_anchor(f)}')
        for label, value in (('Observed', f.observed), ('Expected', f.expected),
                             ('Evidence', f.evidence), ('Fix', f.fix)):
            if value:
                lines.append(f'  {label + ":":<10}{value}')
    lines.append('')
    lines.append('Verified:')
    ran = [r for r in results if r.status in ('ok', 'findings')]
    lines += [f'  {r.name}: {r.detail}' for r in ran] or ['  (nothing)']
    lines.append('Not checked:')
    skipped = [r for r in results if r.status in ('not_checked', 'error')]
    lines += [f'  {r.name}: {r.detail}' for r in skipped] or ['  (nothing)']
    return '\n'.join(lines)


def render_json(path, results):
    return json.dumps({
        'file': str(path),
        'verdict': verdict(results),
        'stages': [{'name': r.name, 'status': r.status, 'detail': r.detail}
                   for r in results],
        'findings': [asdict(f) for f in findings_of(results)],
    }, indent=2)


def main(argv=None):
    p = argparse.ArgumentParser(
        description='Local pre-check of an IHMCIF file (not PDB-IHM validation).')
    p.add_argument('file', help='.cif, .cif.gz, or .bcif')
    p.add_argument('--json', action='store_true', help='machine-readable output')
    p.add_argument('--check-atom-names', action='store_true',
                   help='compare atom names with the CCD (downloads CCD files)')
    p.add_argument('--cache-dir', help='default: $XDG_CACHE_HOME/ihmtools')
    p.add_argument('--offline', action='store_true',
                   help='use cached dictionaries/CCD only; never download')
    args = p.parse_args(argv)
    if not os.path.isfile(args.file) or not os.access(args.file, os.R_OK):
        print(f'check_entry: cannot read {args.file}', file=sys.stderr)
        return 2
    results = run_checks(args.file, args.cache_dir, args.offline, args.check_atom_names)
    print(render_json(args.file, results) if args.json else render_text(args.file, results))
    return 1 if verdict(results) == 'FAIL' else 0


if __name__ == '__main__':
    sys.exit(main())
```

- [ ] **Step 4: Run the tests and checks to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_check_entry.py -q -m "not network"`
Expected: `9 passed`

Run: `.venv/bin/python -m pytest tests/test_check_entry.py -q`
Expected: `12 passed`

- [ ] **Step 5: Verify**

Smoke-test on two released entries exactly as users run it, through `uv` and the
script's inline dependencies (the first run downloads dictionaries and CCD files):

```bash
mkdir -p /tmp/ihmtools-smoke && cd /tmp/ihmtools-smoke
curl -sSfO https://files.rcsb.org/download/9A9W.cif
curl -sSfO https://files.rcsb.org/download/9A8W.cif
CHECK="$OLDPWD/skills/check/scripts/check_entry.py"
"$OLDPWD/.venv/bin/uv" run --quiet --script "$CHECK" 9A9W.cif --check-atom-names; echo "exit=$?"
"$OLDPWD/.venv/bin/uv" run --quiet --script "$CHECK" 9A8W.cif; echo "exit=$?"
cd "$OLDPWD"
```

Expected for 9A9W: first line `PASS: 9A9W.cif (0 BLOCKER, 0 ERROR, 0 WARNING, 0 NOTE). Local
pre-check, not PDB-IHM validation.`, `representation: 51729 atoms/spheres checked`,
`atom_names: 25 component(s) against the CCD`, `exit=0`. For 9A8W: `PASS`,
`representation: 1663 atoms/spheres checked`, `exit=0`. (Verified while writing this plan.)

- [ ] **Step 6: Commit**

```bash
git add skills/check/scripts/check_entry.py tests/test_check_entry.py
git commit -m "feat(check): add check_entry.py command-line entry point" \
  --trailer "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" \
  --trailer "Claude-Session: https://claude.ai/code/session_012ee19x4Mb2BvMSdFbUvwzB"
```


### Task 8: Tool probe (`scripts/probe.sh`)

One command every skill and the agent run first (spec 4.1). Installs nothing, always exits 0.

**Files:**
- Create: `scripts/probe.sh`
- Test: `tests/test_probe.py`
- Modify: `tests/test_repo.py` (EXPECTED_FILES)

**Interfaces:**
- Produces: `bash "${CLAUDE_PLUGIN_ROOT}/scripts/probe.sh"` printing one `name  status` line each for `python ihm msgpack gemmi ihmv ihmdep uv apptainer chimerax IHMV_SIF`, in that order; status is a version/path or `missing (...)`.

- [ ] **Step 1: Add the new files to `EXPECTED_FILES` in `tests/test_repo.py`**

Insert these lines just before the closing `]` of `EXPECTED_FILES`:

```python
    'scripts/probe.sh',
```

- [ ] **Step 2: Write the test `tests/test_probe.py`**

```python
import os
import shutil
import subprocess
from pathlib import Path

PROBE = Path(__file__).resolve().parents[1] / 'scripts' / 'probe.sh'
BASH = shutil.which('bash')
NAMES = ['python', 'ihm', 'msgpack', 'gemmi', 'ihmv', 'ihmdep', 'uv', 'apptainer',
         'chimerax', 'IHMV_SIF']


def probe(**env):
    out = subprocess.run([BASH, str(PROBE)], env=env, capture_output=True,
                         text=True, check=True).stdout
    return dict(line.split(None, 1) for line in out.splitlines())


def test_reports_every_tool_in_order():
    out = subprocess.run([BASH, str(PROBE)], capture_output=True, text=True,
                         check=True).stdout
    assert [line.split()[0] for line in out.splitlines()] == NAMES


def test_missing_tools_get_install_hints(tmp_path):
    rows = probe(PATH=str(tmp_path))          # empty PATH: nothing is found
    assert rows['python'].startswith('missing')
    assert rows['ihmv'] == 'missing (install: pip install ihmtools)'
    assert rows['IHMV_SIF'].startswith('unset')


def test_ihmv_sif_reported(tmp_path):
    sif = tmp_path / 'ihmv.sif'
    assert probe(PATH=os.environ['PATH'], IHMV_SIF=str(sif))['IHMV_SIF'] == \
        f'set to {sif} but no such file'
    sif.write_text('')
    assert probe(PATH=os.environ['PATH'], IHMV_SIF=str(sif))['IHMV_SIF'] == str(sif)
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_probe.py tests/test_repo.py -q`

Expected: FAIL; the output contains `failed`.

- [ ] **Step 4: Write `scripts/probe.sh`**

Then make it executable: `chmod +x scripts/probe.sh`.

```bash
#!/usr/bin/env bash
# Report which tools the ihmtools plugin can use on this machine.
# Installs nothing and always exits 0. One "name  status" line per tool.
set -u

row() { printf '%-12s %s\n' "$1" "$2"; }

py=$(command -v python3 || command -v python || true)
if [ -n "$py" ]; then
  row python "$py ($("$py" -c 'import sys; print(sys.version.split()[0])'))"
  for dist in ihm msgpack gemmi; do
    ver=$("$py" -c "import importlib.metadata as m; print(m.version('$dist'))" 2>/dev/null)
    row "$dist" "${ver:-missing (install: pip install $dist)}"
  done
else
  row python "missing (install Python 3.9 or newer)"
fi

for tool in ihmv ihmdep; do
  row "$tool" "$(command -v "$tool" || echo 'missing (install: pip install ihmtools)')"
done
row uv "$(command -v uv || echo 'missing (optional: https://docs.astral.sh/uv/)')"
row apptainer "$(command -v apptainer || command -v singularity || echo 'missing (optional: local IHMValidation only)')"

chimerax=$(command -v chimerax || command -v ChimeraX || true)
if [ -z "$chimerax" ]; then
  for app in /Applications/ChimeraX*.app/Contents/bin/ChimeraX; do
    [ -x "$app" ] && chimerax=$app
  done
fi
row chimerax "${chimerax:-missing (optional: geometry checks and images)}"

if [ -z "${IHMV_SIF:-}" ]; then
  row IHMV_SIF "unset (optional: path to a local IHMValidation image)"
elif [ -f "$IHMV_SIF" ]; then
  row IHMV_SIF "$IHMV_SIF"
else
  row IHMV_SIF "set to $IHMV_SIF but no such file"
fi
exit 0
```

- [ ] **Step 5: Run the tests and checks to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_probe.py tests/test_repo.py -q`
Expected: `20 passed`

- [ ] **Step 6: Commit**

```bash
git add scripts/probe.sh tests/test_probe.py tests/test_repo.py
git commit -m "feat: add dependency probe script" \
  --trailer "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" \
  --trailer "Claude-Session: https://claude.ai/code/session_012ee19x4Mb2BvMSdFbUvwzB"
```


### Task 9: `ihmcif` knowledge skill

The shared domain knowledge moved out of the original agent (spec 3.1). `SKILL.md` is a short index; detail lives in `references/`.

**Files:**
- Create: `skills/ihmcif/SKILL.md`
- Create: `skills/ihmcif/references/data-model.md`
- Create: `skills/ihmcif/references/tooling.md`
- Modify: `tests/test_repo.py` (EXPECTED_FILES)

**Interfaces:**
- Produces: skill `ihmcif` (surfaces as `/ihmtools:ihmcif`); preloaded by the `curator` agent (Task 14) via `skills: [ihmcif]`.

- [ ] **Step 1: Add the new files to `EXPECTED_FILES` in `tests/test_repo.py`**

Insert these lines just before the closing `]` of `EXPECTED_FILES`:

```python
    'skills/ihmcif/SKILL.md',
    'skills/ihmcif/references/data-model.md',
    'skills/ihmcif/references/tooling.md',
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_repo.py -q`

Expected: FAIL; the output contains `3 failed`.

- [ ] **Step 3: Write `skills/ihmcif/SKILL.md`**

```markdown
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
```

- [ ] **Step 4: Write `skills/ihmcif/references/data-model.md`**

```markdown
# IHM data model

## Archive and identifiers

- **PDBx/mmCIF** is the wwPDB format for coordinates and metadata. Chemical
  components come from the Chemical Component Dictionary (CCD):
  `https://files.rcsb.org/ligands/download/{COMP_ID}.cif`.
- **PDB-IHM** (formerly PDB-Dev) archives integrative structures, meaning
  models computed from several kinds of experimental and computational data
  rather than one diffraction or imaging experiment.
- Entry identifiers come in two forms: legacy `PDBDEV_########` (8 digits)
  and 4-character PDB IDs (e.g. `9A8R`), used since PDB-IHM entries joined
  the main PDB archive. Both can appear in one file (`_database_2`,
  `_pdbx_database_related`).
- Released files: `https://files.rcsb.org/download/{ID}.cif`. Entry
  metadata: `https://data.rcsb.org/rest/v1/core/entry/{ID}`.
- Dictionaries: `https://mmcif.wwpdb.org/dictionaries/ascii/mmcif_pdbx_v50.dic`
  (PDBx) and `https://mmcif.wwpdb.org/dictionaries/ascii/mmcif_ihm_ext.dic`
  (IHMCIF; also in `https://github.com/ihmwg/IHMCIF`, `dist/`).

## Categories you will navigate

| Concern | Categories |
|---|---|
| Composition | `entity`, `entity_poly`, `entity_poly_seq`, `struct_asym`, `ihm_entity_poly_segment` |
| What was modeled | `ihm_struct_assembly`, `ihm_struct_assembly_details`, `ihm_struct_assembly_class` |
| Representation | `ihm_model_representation`, `ihm_model_representation_details` (atomic vs. sphere vs. Gaussian, rigid vs. flexible, residues per bead) |
| Coordinates | `atom_site` (atomic), `ihm_sphere_obj_site` (coarse-grained beads), `ihm_gaussian_obj_site` |
| Models and ensembles | `ihm_model_list`, `ihm_model_group`, `ihm_model_group_link`, `ihm_ensemble_info`, `ihm_localization_density_files` |
| States and order | `ihm_multi_state_modeling`, `ihm_ordered_ensemble`, `ihm_multi_state_scheme` (IHMCIF 1.2 and later) |
| Input data | `ihm_dataset_list`, `ihm_dataset_group`, `ihm_dataset_related_db_reference`, `ihm_related_datasets`, `ihm_external_reference_info`, `ihm_external_files` |
| Starting models | `ihm_starting_model_details`, `ihm_starting_computational_models`, `ihm_starting_comparative_models` |
| Restraints | `ihm_cross_link_list`, `ihm_cross_link_restraint`, `ihm_sas_restraint`, `ihm_3dem_restraint`, `ihm_predicted_contact_restraint`, `ihm_derived_distance_restraint`, `ihm_geometric_object_*` |
| Protocol | `ihm_modeling_protocol`, `ihm_modeling_protocol_details`, `ihm_modeling_post_process` |

`_ihm_model_list` has only `model_id`, `model_name`, `assembly_id`,
`protocol_id`, `representation_id`. Which models belong to which group is
recorded in `ihm_model_group_link`.

## The two invariants entries break most

1. **Linkage.** A restraint, dataset, or model group points at an id that
   does not exist, or a dataset is used by nothing: no restraint, feature,
   or starting model references it, and it is not the primary of a used
   dataset in `ihm_related_datasets`.
2. **Representation consistency.** A segment declared coarse-grained carries
   `atom_site` rows, or an atomic segment carries spheres. Coordinates must
   also fall inside the model's assembly and representation.

## Data types and validation coverage

The IHMValidation report covers SAS, crosslinking-MS, and 3DEM data (FRET is
in development). A section for a data type the entry does not have is
legitimately empty; that is not a bug. Crosslinking-MS data quality can be
assessed only for datasets deposited in PRIDE in compliant form; SAS fits
come from SASBDB; 3DEM assessments reuse the wwPDB EM pipeline.
```

- [ ] **Step 5: Write `skills/ihmcif/references/tooling.md`**

````markdown
# Tools for IHMCIF files

Choose the tool by the level the problem lives at. Using the wrong level is
the most common way to waste a cycle.

## gemmi: lexical and dictionary level

Use it for loop syntax, duplicated or missing tags, category surgery on files
python-ihm refuses to open, and coordinate access. gemmi reads some broken
files that python-ihm rejects, so it is the first tool to reach for after a
parse failure. Use the Python module (`import gemmi`); the pip package does
not install a `gemmi` command-line program. gemmi's Python reader handles
text and gzipped mmCIF, not BinaryCIF.

```python
import gemmi
doc = gemmi.cif.read('ENTRY.cif')
block = doc.sole_block()

# Full category inventory. Iterating only `if item.loop` is WRONG: single-row
# categories are stored as `pair` items, and on a small entry that hides most
# of the ihm_* metadata (on 9A8R: 11 loops vs. 35 categories). Cover both:
cats = set()
for item in block:
    if item.loop is not None:
        cats.add(item.loop.tags[0].split('.')[0])
    elif item.pair is not None:
        cats.add(item.pair[0].split('.')[0])

tbl = block.find('_ihm_model_group_link.', ['group_id', 'model_id'])  # read a loop
block.find_mmcif_category('_ihm_dataset_list.').erase()  # works on pair and loop forms
doc.write_file('ENTRY.fixed.cif')
st = gemmi.read_structure('ENTRY.cif')                   # coordinate view
```

`block.find()` returns an **empty table instead of raising** when a requested
tag is absent, so a typo or a retired item looks like "no rows in a good
file". Confirm the tag exists in the dictionary before believing an empty
result.

## python-ihm: semantic and model level

Use it to answer whether the entry means what it says: the object graph,
restraint-to-dataset wiring, ensembles, protocol steps. A clean read/write
round-trip is the strongest single correctness signal.

```python
import ihm.reader, ihm.dumper
with open('ENTRY.cif') as fh:          # BinaryCIF: open(..., 'rb'), format='BCIF'
    systems = ihm.reader.read(fh)
s = systems[0]
# s.entities, s.asym_units, s.orphan_datasets, s.restraints, s.state_groups,
# s.ensembles, s.orphan_protocols, s.orphan_representations

for group, model in s._all_models():   # yields 2-tuples, NOT 4-tuples
    print(group._id, model._id, len(model._atoms), len(model._spheres))

with open('roundtrip.cif', 'w') as fh:
    ihm.dumper.write(fh, systems)
```

- A round-trip is a **check, not a repair method**. `ihm.dumper.write` emits
  only what python-ihm models; anything else is silently dropped (on 9A8R,
  `_entity_name_com` disappears). Diff the round-trip against the original
  to learn what is unmodeled, then patch the real file with gemmi.
- `ihm.dumper.write` checks that every atom or sphere fits the model's
  representation and assembly, and raises `ValueError` otherwise. Pass
  `check=False` only for diagnosis.
- `UnknownCategoryWarning` / `UnknownKeywordWarning` (enabled with
  `warn_unknown_category=True`, `warn_unknown_keyword=True`) mean python-ihm
  has no model for an item, not that the item is invalid. Python-ihm emits
  dozens of them even on files it wrote itself. Never report them as
  defects; dictionary validation is the authority on unknown items.
- `ihm.reader.read(..., reject_old_file=True)` flags files written against an
  obsolete dictionary version.

## Dictionary validation (in Python, no CLI)

```python
import urllib.request, ihm.dictionary
BASE = 'https://mmcif.wwpdb.org/dictionaries/ascii/'
with urllib.request.urlopen(BASE + 'mmcif_pdbx_v50.dic') as fh:
    d_pdbx = ihm.dictionary.read(fh)
with urllib.request.urlopen(BASE + 'mmcif_ihm_ext.dic') as fh:
    d_ihm = ihm.dictionary.read(fh)
with open('ENTRY.cif') as fh:
    (d_pdbx + d_ihm).validate(fh)      # raises ihm.dictionary.ValidatorError
```

- `mmcif_ihm_ext.dic` and `mmcif_ihm.dic` are the same file under two names:
  the IHM extension plus the PDBx parent categories it extends, not all of
  PDBx. Merge with `mmcif_pdbx_v50.dic` for full coverage. Cache them
  locally (the `check` skill keeps them in `~/.cache/ihmtools/`) instead of
  refetching 6 MB on every run.
- The validator lowercases keyword names in its messages.
- **Dictionary validation is blind to atom nomenclature.** It skips
  `chem_comp_*` parents, so `_atom_site.label_atom_id` is never checked
  against the CCD. An entry using obsolete PDB v2.3 hydrogen names (`1HB`,
  `2HG2`) validates clean. Use `check --check-atom-names`, or compare each
  component's `_chem_comp_atom.atom_id` set from the CCD with the distinct
  `(comp_id, atom_id)` pairs in `atom_site`; the CCD's `alt_atom_id` column
  maps old names to current ones.

## ChimeraX: geometry and visuals

```bash
chimerax --nogui --offscreen --silent --exit \
  --cmd "open ENTRY.cif; info; clashes #1; save shot.png width 1200"
```

Use `--script script.py` for anything nontrivial. Good for clashes,
distances, sanity-checking multi-scale representations, and rendering.
Bead models have no standard atoms: check what actually loaded (`info`)
before trusting a geometry command's output. ChimeraX is optional; the
probe script reports whether it is installed.
````

- [ ] **Step 6: Run the tests and checks to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_repo.py -q`
Expected: `21 passed`

Run: `claude plugin validate skills`
Expected: `Validation passed`

- [ ] **Step 7: Commit**

```bash
git add skills/ihmcif tests/test_repo.py
git commit -m "feat: add ihmcif knowledge skill" \
  --trailer "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" \
  --trailer "Claude-Session: https://claude.ai/code/session_012ee19x4Mb2BvMSdFbUvwzB"
```


### Task 10: `check` skill

Depositor-facing wrapper around `check_entry.py` (spec 3.2): probe, choose runner (uv first), run, report at the user's level, hand off to the curator or validate.

**Files:**
- Create: `skills/check/SKILL.md`
- Modify: `tests/test_repo.py` (EXPECTED_FILES)

**Interfaces:**
- Consumes: `scripts/probe.sh` (Task 8), `skills/check/scripts/check_entry.py` (Task 7).
- Produces: skill `check` (`/ihmtools:check <file> [--check-atom-names]`).

- [ ] **Step 1: Add the new files to `EXPECTED_FILES` in `tests/test_repo.py`**

Insert these lines just before the closing `]` of `EXPECTED_FILES`:

```python
    'skills/check/SKILL.md',
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_repo.py -q`

Expected: FAIL; the output contains `1 failed`.

- [ ] **Step 3: Write `skills/check/SKILL.md`**

````markdown
---
name: check
description: Local pre-check of an integrative-structure file (IHMCIF .cif, .cif.gz, or .bcif) before PDB-IHM validation or deposition. Checks syntax, PDBx/IHM dictionary compliance, python-ihm readability, dataset linkage, representation consistency, and optionally atom names against the CCD. Use when the user asks to check, lint, or sanity-check an IHM/IHMCIF/mmCIF integrative model, asks whether a file will pass validation or deposition, or before uploading with the validate or deposit skills.
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
  which and why, and do not present it as a pass.
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
````

- [ ] **Step 4: Run the tests and checks to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_repo.py -q`
Expected: `23 passed`

Run: `claude plugin validate skills`
Expected: `Validation passed`

- [ ] **Step 5: Verify**

Live smoke test: load the plugin in a headless session and ask in plain language
(the skill must trigger by itself). Run from a scratch directory holding 9A8W.cif from Task 7:

```bash
cd /tmp/ihmtools-smoke
PATH="$OLDPWD/.venv/bin:$PATH" claude -p --plugin-dir "$OLDPWD" --max-turns 15 \
  --dangerously-skip-permissions --output-format stream-json --verbose \
  "I'm about to deposit 9A8W.cif to PDB-IHM. Can you check it for problems first?" > check-smoke.jsonl
grep -o '"skill":"ihmtools:check"' check-smoke.jsonl | head -1
grep -c 'check_entry.py' check-smoke.jsonl
cd "$OLDPWD"
```

Expected: `"skill":"ihmtools:check"` is printed, the count is at least 1, and the final
`result` event reports PASS for 9A8W, calls it a local pre-check rather than PDB-IHM
validation, and offers the validate skill. (Verified while writing this plan.)

- [ ] **Step 6: Commit**

```bash
git add skills/check/SKILL.md tests/test_repo.py
git commit -m "feat: add check skill" \
  --trailer "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" \
  --trailer "Claude-Session: https://claude.ai/code/session_012ee19x4Mb2BvMSdFbUvwzB"
```


### Task 11: `validate` skill and report reference

Server route via `ihmv` (default) and local Apptainer route (opt-in), plus report interpretation (spec 3.3). The CLI's confirmation prompts hang in a non-interactive shell, so the skill confirms in chat and passes `-y`.

**Files:**
- Create: `skills/validate/SKILL.md`
- Create: `skills/validate/references/report-sections.md`
- Modify: `tests/test_repo.py` (EXPECTED_FILES)

**Interfaces:**
- Consumes: `scripts/probe.sh`; the `check` skill (pre-flight); the `curator` agent (triage hand-off, Task 14).
- Produces: skill `validate`.

- [ ] **Step 1: Add the new files to `EXPECTED_FILES` in `tests/test_repo.py`**

Insert these lines just before the closing `]` of `EXPECTED_FILES`:

```python
    'skills/validate/SKILL.md',
    'skills/validate/references/report-sections.md',
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_repo.py -q`

Expected: FAIL; the output contains `2 failed`.

- [ ] **Step 3: Write `skills/validate/SKILL.md`**

````markdown
---
name: validate
description: Get or interpret an IHMValidation report for an integrative structure. Uploads an IHMCIF file to the PDB-IHM validation server (validate.pdb-ihm.org) with the ihmv CLI, tracks it, and downloads the PDF reports, or runs a local IHMValidation Apptainer image when the user has one. Use when the user asks to validate an IHM/IHMCIF model, get or download a validation report, run IHMValidation, check validation status, or explain a PDB-IHM validation report.
argument-hint: <file.cif> | status <RID> | explain <report.pdf>
---

# IHMValidation reports

There are two routes. Default to the server; use the local route only when
the user already has an IHMValidation image.

Describe server output as "the IHMValidation report from
validate.pdb-ihm.org". This plugin is unofficial: never present its own
output (for example `check` findings) as a PDB-IHM assessment.

## Probe

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/probe.sh"
```

The server route needs `ihmv`. If it is missing, offer `pip install ihmtools`
and ask before installing. The local route needs `apptainer` (or
`singularity`) plus an image, either from `IHMV_SIF` or a path the user gives.

## Server route

1. **Pre-flight.** If the `check` skill has not run on this exact file in
   this conversation, offer it, and recommend it strongly if the file was
   edited.
2. **Account.** Run `ihmv whoami`. If there are no credentials, ask the user
   to type `! ihmv login`: it prints a Globus URL and reads back a code,
   which you cannot do for them. Then run `ihmv whoami` again and confirm it
   is the account they mean.
3. **Confirm the upload.** Say: "This uploads `<file>`, an unreleased
   structure, to the PDB-IHM validation server as `<account>`. Proceed?"
   Wait for an explicit yes.
4. **Upload.** Run `ihmv upload <file>` and record the RID it prints. Use the
   production server unless the user explicitly asks for `--mode dev`. If
   ihmv reports that the file was already submitted, tell the user and ask
   whether to use the existing record or resubmit with `-f`.
5. **Wait.** Run `ihmv get_status <RID>`. Exit codes: 0 done, 1 error,
   2 pending, 3 unknown. Validation takes 5 to 115 minutes. Do not poll in
   a tight loop: check every 5 to 10 minutes in the background, or tell the
   user they can come back and ask for the status of `<RID>`.
6. **Download.** When done, run `ihmv download <RID> -o <stem>_validation`.
   On error, `ihmv get_status <RID> -v` prints the processing log; summarize
   it and offer the `ihmtools:curator` agent for triage.
7. **Reprocess** (after a fix on the server side): confirm with the user,
   then run `ihmv set_status <RID> --to Reprocess -y`.
8. **Delete a record:** confirm with the user, naming the RID, then run
   `ihmv delete <RID> -y`.

`ihmv set_status` and `ihmv delete` ask for confirmation on the terminal,
which hangs in a non-interactive shell. Always confirm in chat first, then
pass `-y`. `ihmv get_status` with no RID lists the user's entries, newest
first.

## Local route (Apptainer image)

Use it only when `IHMV_SIF` points to an image or the user names one. Never
build the image: that needs Chimera and ChimeraX downloads and about 25
minutes (see the IHMValidation README).

```bash
apptainer run --pid "$IHMV_SIF" --cache-root <cache-dir> --output-root <out-dir> -f <absolute-path-to-file>
```

- Use `singularity run` if only singularity is installed.
- Run it in the background.
- Add `--html-mode local` when the user wants to browse the HTML report.
- Outputs: `<out-dir>/<stem>/<stem>_full_validation.pdf`,
  `<stem>_summary_validation.pdf`, and `<stem>_html.tar.gz`.
- `-h` lists all options.
- To find which section fails, disable sections one at a time with
  `--enable-sas false`, `--enable-cx false`, `--enable-em false`,
  `--enable-prism false`, or `--enable-format-check false`.

## Explaining a report

Read `${CLAUDE_SKILL_DIR}/references/report-sections.md` first. When
explaining:

- Section content depends on the data the entry contains. An empty SAS
  section on an entry with no SAS data is expected.
- Separate what the depositor can fix in the file (missing dataset
  references, wrong representation) from properties of the model or data
  (restraint satisfaction, clashes).
- Point to https://pdb-ihm.org/validation_help.html for metric definitions.
````

- [ ] **Step 4: Write `skills/validate/references/report-sections.md`**

```markdown
# What an IHMValidation report contains

Full definitions: https://pdb-ihm.org/validation_help.html. The pipeline
follows the wwPDB IHM Task Force recommendations (Berman et al. 2019) and
the SAS, crosslinking-MS, and 3DEM community guidelines.

Each run produces a **full report** (PDF, plus HTML in a `.tar.gz`) and a
**summary table** (PDF).

## Full report sections

| Section | Content | Depends on |
|---|---|---|
| 1. Overview | Summary of models, datasets, and representation; "at a glance" plots for model quality, data quality, fit to data used for modeling, and fit to data used for validation | everything below |
| 2. Model details | Ensembles; representation (rigid and flexible segments); datasets used; methods, protocol, and software | every entry has this |
| 3. Data quality | SAS: scattering profiles, MW and volume estimates, flexibility (Porod-Debye, Kratky), P(r), Guinier. Crosslinking-MS: only for datasets deposited in PRIDE in compliant form, with entities matched to the PRIDE data. 3DEM: elements of the wwPDB EM map validation | which data types the entry has |
| 4. Model quality | Atomic models: MolProbity (bonds, angles, clashscore, rotamers, Ramachandran). Coarse-grained models: excluded-volume violations between beads. PrISM precision (regions of high and low precision) | atomic vs. coarse-grained representation |
| 5. Fit to data used for modeling | SAS: chi-squared and CorMap p-values, from SASBDB fits. Crosslinking-MS: restraint types, distograms, satisfaction per restraint group. 3DEM: map-model fit as in the wwPDB EM report | which data types the entry has |
| 6. Fit to data used for validation | Under development | |

## Summary table

Entry composition and datasets; representation (scale, rigid and flexible
segments); physical and experimental restraints; validation (sampling
precision, ensembles, models per ensemble, deposited models, model
precision, plus one-line data quality, model quality, and fit-to-data
results); methods and software.

## Reading a report with the user

- **Empty sections.** A section for a data type the entry does not contain
  is empty by design. Crosslinking-MS data quality is empty when the dataset
  is not a compliant PRIDE deposition, even if crosslinks are in the file.
- **Problems the depositor can fix in the file.** A dataset missing its
  database reference (`ihm_dataset_related_db_reference`) or used by no
  restraint; crosslink restraints at the wrong granularity for the
  representation; representation details that disagree with the
  coordinates. The `check` skill and the `ihmtools:curator` agent can find
  these in the file.
- **Properties of the model or data.** Low restraint satisfaction, clashes,
  poor SAS fit. These are scientific results to discuss, not file errors;
  do not "fix" them by editing the entry.
- **Pipeline failure** (no report, or an error status): get the processing
  log (`ihmv get_status <RID> -v`) and hand it to the `ihmtools:curator`
  agent, which decides whether the cause is the entry data, the pipeline
  code, or the environment.
```

- [ ] **Step 5: Run the tests and checks to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_repo.py -q`
Expected: `26 passed`

Run: `claude plugin validate skills`
Expected: `Validation passed`

- [ ] **Step 6: Commit**

```bash
git add skills/validate tests/test_repo.py
git commit -m "feat: add validate skill" \
  --trailer "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" \
  --trailer "Claude-Session: https://claude.ai/code/session_012ee19x4Mb2BvMSdFbUvwzB"
```


### Task 12: `build` skill, python-ihm patterns, and a test pinning them

Spec 3.4. `tests/test_build_patterns.py` executes the API calls the reference teaches, so a python-ihm API change breaks a test instead of misleading users. It passes as soon as it is written (it tests python-ihm, not plugin code); that is expected. It also pins the pitfall found while writing the reference: a map/SAS restraint with no `.fits` entry is silently left out of the file.

**Files:**
- Create: `skills/build/SKILL.md`
- Create: `skills/build/references/python-ihm-patterns.md`
- Test: `tests/test_build_patterns.py`
- Modify: `tests/test_repo.py` (EXPECTED_FILES)

**Interfaces:**
- Consumes: `scripts/probe.sh`; the `check` skill (run on the output).
- Produces: skill `build`.

- [ ] **Step 1: Add the new files to `EXPECTED_FILES` in `tests/test_repo.py`**

Insert these lines just before the closing `]` of `EXPECTED_FILES`:

```python
    'skills/build/SKILL.md',
    'skills/build/references/python-ihm-patterns.md',
```

- [ ] **Step 2: Write the test `tests/test_build_patterns.py`**

```python
"""Executes the API calls taught in skills/build/references/python-ihm-patterns.md.

If python-ihm changes an API the reference relies on, this fails first.
"""
import io

import ihm
import ihm.analysis
import ihm.cross_linkers
import ihm.dataset
import ihm.dumper
import ihm.location
import ihm.model
import ihm.protocol
import ihm.reader
import ihm.representation
import ihm.restraint


def build_from_patterns():
    system = ihm.System(title='Patterns')
    system.authors.extend(['Last, F.'])
    comps = ihm.LPeptideAlphabet()._comps
    protein = ihm.Entity([comps['M'], comps['K'], comps['V']],
                         alphabet=ihm.LPeptideAlphabet, description='Protein')
    zinc = ihm.Entity([ihm.NonPolymerChemComp('ZN', name='ZINC ION')],
                      description='ZINC ION')
    a = ihm.AsymUnit(protein, details='Protein', id='A')
    z = ihm.AsymUnit(zinc, details='ZINC ION', id='B')
    system.entities.extend([protein, zinc])
    system.asym_units.extend([a, z])
    assembly = ihm.Assembly([a, z], name='Modeled assembly')
    representation = ihm.representation.Representation([
        ihm.representation.AtomicSegment(a(1, 3), rigid=False),
        ihm.representation.AtomicSegment(z, rigid=False)])

    xl = ihm.dataset.CXMSDataset(ihm.location.PRIDELocation('PXD000001'))
    em = ihm.dataset.EMDensityDataset(ihm.location.EMDBLocation('EMD-1234'))
    sas = ihm.dataset.SASDataset(ihm.location.SASBDBLocation('SASDA12'))
    repo = ihm.location.Repository(doi='10.5281/zenodo.1', url='https://zenodo.org/record/1')
    ihm.location.InputFileLocation('data/x.csv', repo=repo)
    system.orphan_datasets.extend([xl, em, sas])

    xlr = ihm.restraint.CrossLinkRestraint(dataset=xl, linker=ihm.cross_linkers.dsso)
    link = ihm.restraint.ExperimentalCrossLink(protein.residue(1), protein.residue(3))
    xlr.experimental_cross_links.append([link])
    xlr.cross_links.append(ihm.restraint.ResidueCrossLink(
        experimental_cross_link=link, asym1=a, asym2=a,
        distance=ihm.restraint.UpperBoundDistanceRestraint(30.0)))
    emr = ihm.restraint.EM3DRestraint(dataset=em, assembly=assembly,
                                      fitting_method='Gaussian mixture models')
    sasr = ihm.restraint.SASRestraint(dataset=sas, assembly=assembly,
                                      fitting_method='FoXS', multi_state=False,
                                      radius_of_gyration=None)
    system.restraints.extend([xlr, emr, sasr])

    protocol = ihm.protocol.Protocol(name='Modeling')
    protocol.steps.append(ihm.protocol.Step(
        assembly=assembly, dataset_group=None, name='Sampling',
        method='Replica exchange monte carlo', num_models_begin=0, num_models_end=10))
    analysis = ihm.analysis.Analysis()
    analysis.steps.append(ihm.analysis.ClusterStep(
        feature='RMSD', num_models_begin=10, num_models_end=5))
    protocol.analyses.append(analysis)
    system.orphan_protocols.append(protocol)

    class Model(ihm.model.Model):
        def get_atoms(self):
            rows = [(a, 1, 'CA', 'C'), (a, 2, 'CA', 'C'), (a, 3, 'CA', 'C'),
                    (z, None, 'ZN', 'ZN')]
            for i, (asym, seq_id, name, element) in enumerate(rows):
                yield ihm.model.Atom(asym_unit=asym, seq_id=seq_id or 1, atom_id=name,
                                     type_symbol=element, x=float(i), y=0., z=0.,
                                     het=asym is z, biso=None, occupancy=None)

    model = Model(assembly=assembly, protocol=protocol,
                  representation=representation, name='Best scoring model')
    emr.fits[model] = ihm.restraint.EM3DRestraintFit()
    sasr.fits[model] = ihm.restraint.SASRestraintFit(chi_value=None)
    group = ihm.model.ModelGroup([model], name='Cluster 0')
    system.state_groups.append(ihm.model.StateGroup([ihm.model.State([group])]))
    system.ensembles.append(ihm.model.Ensemble(
        model_group=group, num_models=5, name='Cluster 0',
        clustering_method='Density based threshold-clustering',
        clustering_feature='RMSD'))
    return system


def test_patterns_write_and_read_back():
    fh = io.StringIO()
    ihm.dumper.write(fh, [build_from_patterns()])
    fh.seek(0)
    check, = ihm.reader.read(fh)
    assert len(check.entities) == 2
    assert len(check.restraints) == 3          # crosslink, 3DEM, SAS
    assert len(check.ensembles) == 1


def test_restraint_without_fit_is_silently_dropped():
    system = build_from_patterns()
    sas_restraint = system.restraints[2]
    sas_restraint.fits.clear()
    fh = io.StringIO()
    ihm.dumper.write(fh, [system])
    fh.seek(0)
    check, = ihm.reader.read(fh)
    assert len(check.restraints) == 2          # what the reference warns about
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_build_patterns.py tests/test_repo.py -q`

Expected: FAIL; the output contains `2 failed`.

- [ ] **Step 4: Write `skills/build/SKILL.md`**

````markdown
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
````

- [ ] **Step 5: Write `skills/build/references/python-ihm-patterns.md`**

````markdown
# python-ihm patterns for building an entry

Condensed from the worked examples in https://github.com/salilab/ihmtools,
`examples/9A9W/assemble.py` (atomic: 51729 atoms, DSSO crosslinks, 3DEM map)
and `examples/9A8W/assemble.py` (coarse-grained: 1663 spheres, SDA
crosslinks, 3DEM map). Read those scripts when a case below is not enough.
API reference: https://python-ihm.readthedocs.io.

## Skeleton

```python
import ihm, ihm.dataset, ihm.dumper, ihm.location, ihm.model
import ihm.protocol, ihm.reader, ihm.representation, ihm.restraint

system = ihm.System(title="...")            # TODO(depositor) if unknown
system.authors.extend(["Last, F.", ...])
# entities, asym units, assembly, representation, datasets, restraints,
# protocol, models (below)
with open(OUTPUT, "w") as fh:
    ihm.dumper.write(fh, [system])
with open(OUTPUT) as fh:                     # read back: the cheapest check
    check, = ihm.reader.read(fh)
```

## Entities and asym units

One `ihm.Entity` per unique sequence, one `ihm.AsymUnit` per chain copy.

```python
alphabet = ihm.DNAAlphabet if is_dna else ihm.LPeptideAlphabet
comps = alphabet()._comps
# DNAAlphabet is keyed by "DA"; LPeptideAlphabet by the one-letter code.
# Look up by name first, then fall back to the one-letter code:
sequence = [comps.get(name) or
            comps[gemmi.find_tabulated_residue(name).one_letter_code.upper()]
            for name in residue_names]
entity = ihm.Entity(sequence, alphabet=alphabet, description=description)
asym = ihm.AsymUnit(entity, details=description, id=chain_id)

# a ligand (e.g. zinc) is its own single-component entity
zn = ihm.Entity([ihm.NonPolymerChemComp("ZN", name="ZINC ION")],
                description="ZINC ION")

assembly = ihm.Assembly(list_of_asyms, name="Modeled assembly")
```

`_entity.pdbx_description` is often the only naming a coordinate file
carries, and crosslink tables name proteins by it. gemmi's
`make_mmcif_document()` drops it, so put it back if you rewrite coordinates.

## Representation

```python
# atomic, over the residues actually present (chains may have gaps)
ihm.representation.AtomicSegment(asym(first_seq, last_seq), rigid=False)
# ligands: the whole asym unit; never give a non-polymer a residue range
ihm.representation.AtomicSegment(zinc_asym, rigid=False)

# coarse-grained
ihm.representation.ResidueSegment(asym(b, e), rigid=True, primitive="sphere")
ihm.representation.FeatureSegment(asym(b, e), rigid=False, primitive="sphere",
                                  count=1)      # one multi-residue bead
representation = ihm.representation.Representation([...segments...])
```

Ask the entity (`asym.entity.is_polymeric()`) before giving an asym a residue
range; older gemmi assigns `label_seq` to non-polymers too.

## Datasets and where the data lives

```python
xl = ihm.dataset.CXMSDataset(ihm.location.PRIDELocation("PXD......"))
em = ihm.dataset.EMDensityDataset(ihm.location.EMDBLocation("EMD-....."))
sas = ihm.dataset.SASDataset(ihm.location.SASBDBLocation("SASDA..."))
pdb = ihm.dataset.PDBDataset(ihm.location.PDBLocation("9XXX"))
afdb = ihm.dataset.DeNovoModelDataset(
    ihm.location.AlphaFoldDBLocation("AF-Q93009-F1-v4"))
ma = ihm.dataset.DeNovoModelDataset(
    ihm.location.ModelArchiveLocation("ma-....."))
# data not in a database: a file in a DOI-bearing repository (e.g. Zenodo)
repo = ihm.location.Repository(doi="10.5281/zenodo.......", url="https://...")
f = ihm.location.InputFileLocation("path/in/archive.csv", repo=repo)
system.orphan_datasets.extend([xl, em, ...])
```

Every dataset should be used by a restraint or starting model; the `check`
skill warns about any that are not. Raw data behind a processed dataset is
linked with `ihm_related_datasets`, not left as an unused dataset.

## Crosslinks: two layers

What the experiment measured (protein and residue, no chain copy), and what
the modeling restrained (a chain pair, for the subset used).

```python
import ihm.cross_linkers                     # dss, dsso, bs3, sda, edc, ...
r = ihm.restraint.CrossLinkRestraint(dataset=xl, linker=ihm.cross_linkers.dsso)
link = ihm.restraint.ExperimentalCrossLink(
    entity1.residue(int(res1)), entity2.residue(int(res2)))
r.experimental_cross_links.append([link])
r.cross_links.append(ihm.restraint.ResidueCrossLink(    # residue-level beads/atoms
    experimental_cross_link=link, asym1=a1, asym2=a2,
    distance=ihm.restraint.UpperBoundDistanceRestraint(30.0)))
# on a multi-residue bead use FeatureCrossLink with the same arguments;
# psi=, sigma1=, sigma2= record Bayesian nuisance parameters when used
system.restraints.append(r)
```

Use the predefined linker from `ihm.cross_linkers` when it exists; it carries
the chemical description. `ihm.ChemDescriptor("NAME")` is the fallback.

## Map and SAS restraints

```python
emr = ihm.restraint.EM3DRestraint(dataset=em, assembly=assembly,
                                  fitting_method="Gaussian mixture models")
emr.fits[model] = ihm.restraint.EM3DRestraintFit()
sasr = ihm.restraint.SASRestraint(dataset=sas, assembly=assembly,
                                  fitting_method="FoXS",
                                  multi_state=False, radius_of_gyration=None)
sasr.fits[model] = ihm.restraint.SASRestraintFit(chi_value=None)
system.restraints.extend([emr, sasr])
```

Map and SAS restraints are written one row per fitted model: a restraint
with no entry in `.fits` is silently left out of the file. Record the fit
statistic when known (`cross_correlation_coefficient=`, `chi_value=`).

## Protocol, analysis, ensembles

```python
protocol = ihm.protocol.Protocol(name="Modeling")
protocol.steps.append(ihm.protocol.Step(
    assembly=assembly, dataset_group=None, name="Sampling",
    method="Replica exchange monte carlo",
    num_models_begin=0, num_models_end=320000))
import ihm.analysis
analysis = ihm.analysis.Analysis()
analysis.steps.append(ihm.analysis.ClusterStep(
    feature="RMSD", num_models_begin=320000, num_models_end=8260))
protocol.analyses.append(analysis)
system.orphan_protocols.append(protocol)
```

Use `None` for model counts you do not know rather than guessing.

## Models: stream coordinates

```python
class Model(ihm.model.Model):
    def get_atoms(self):                    # atomic
        for ...:
            yield ihm.model.Atom(asym_unit=asym, seq_id=seq_id or 1,
                                 atom_id=name, type_symbol=element,
                                 x=x, y=y, z=z, het=is_het,
                                 biso=b, occupancy=occ)

    def get_spheres(self):                  # coarse-grained
        for ...:
            yield ihm.model.Sphere(asym_unit=asym, seq_id_range=(b, e),
                                   x=x, y=y, z=z, radius=r)

model = Model(assembly=assembly, protocol=protocol,
              representation=representation, name="Best scoring model")
group = ihm.model.ModelGroup([model], name="Cluster 0")
system.state_groups.append(ihm.model.StateGroup([ihm.model.State([group])]))
system.ensembles.append(ihm.model.Ensemble(
    model_group=group, num_models=5766, name="Cluster 0",
    clustering_method="Density based threshold-clustering",
    clustering_feature="RMSD"))
```

## Things that bite

- **Non-polymers have no `label_seq`.** Skip their atoms and the write fails
  with "Assemblies reference asym IDs that don't have coordinates". A
  single-component entity's `seq_id` is 1.
- **Alphabets are keyed differently** (see above).
- **Representation must match the coordinates.** `ihm.dumper.write` raises
  `ValueError` when an atom falls in a sphere segment, or outside the
  representation or assembly. Fix the representation; do not pass
  `check=False` to get a file out.
- **Coarse-grained crosslinks** onto a bead spanning several residues must be
  `FeatureCrossLink`, not `ResidueCrossLink`.
````

- [ ] **Step 6: Run the tests and checks to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_build_patterns.py tests/test_repo.py -q`
Expected: `31 passed`

Run: `claude plugin validate skills`
Expected: `Validation passed`

- [ ] **Step 7: Commit**

```bash
git add skills/build tests/test_build_patterns.py tests/test_repo.py
git commit -m "feat: add build skill and python-ihm patterns" \
  --trailer "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" \
  --trailer "Claude-Session: https://claude.ai/code/session_012ee19x4Mb2BvMSdFbUvwzB"
```


### Task 13: `deposit` skill

Spec 3.5: `ihmdep` lifecycle with per-action confirmation; only the two depositor-driven transitions (DRAFT->DEPO, RECORD READY->SUBMIT).

**Files:**
- Create: `skills/deposit/SKILL.md`
- Modify: `tests/test_repo.py` (EXPECTED_FILES)

**Interfaces:**
- Consumes: `scripts/probe.sh`; `check` and `validate` skills (recommended first).
- Produces: skill `deposit`.

- [ ] **Step 1: Add the new files to `EXPECTED_FILES` in `tests/test_repo.py`**

Insert these lines just before the closing `]` of `EXPECTED_FILES`:

```python
    'skills/deposit/SKILL.md',
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_repo.py -q`

Expected: FAIL; the output contains `1 failed`.

- [ ] **Step 3: Write `skills/deposit/SKILL.md`**

````markdown
---
name: deposit
description: Deposit an integrative structure to PDB-IHM and manage the deposition with the ihmdep CLI. Uploads an IHMCIF file (optionally with a preview image), checks deposition status, moves an entry from DRAFT to DEPO or from RECORD READY to SUBMIT, downloads generated files and reports, and deletes entries that are still DRAFT or DEPO. Use when the user wants to deposit or submit a model to PDB-IHM, or asks about the status of a PDB-IHM deposition.
argument-hint: <file.cif> [--image file.png] | status [RID]
---

# Deposit to PDB-IHM with ihmdep

Every state-changing action needs explicit confirmation from the user, every
time, naming the entry and the action. Reading status and downloading are
free.

## Probe and account

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/probe.sh"
```

`ihmdep` comes with `pip install ihmtools`; ask before installing. Then run
`ihmdep whoami`. If there are no credentials, ask the user to type
`! ihmdep login` (it prints a Globus URL and reads back a code). One login
covers both `ihmv` and `ihmdep`. Confirm the account is the one they mean.

The production server is the default. Use `--mode dev` only when the user
asks for it, for example to try the workflow on the development server.

## Upload

1. Recommend the `check` skill first, and the `validate` skill when the user
   has no validation report yet.
2. Confirm: "This deposits `<file>` [with image `<png>`] to PDB-IHM
   (production) as `<account>`. Proceed?"
3. Run `ihmdep upload <file> [--image <file.png>]`. Add `--draft` when the
   user wants to create the entry without starting processing (DRAFT instead
   of DEPO). Record the RID it prints.
4. If ihmdep says the file was already deposited, tell the user; resubmit
   with `-f` only if they ask.

## Status

- `ihmdep get_status` lists the user's entries, newest first.
- `ihmdep get_status <RID>` gives the workflow and process state. Exit codes:
  0 done, 1 error, 2 pending, 3 unknown. `--workflow` or `--process` prints
  only one of them; `-v` prints the full status detail.
- Workflow states the user drives: DRAFT, DEPO, RECORD READY, SUBMIT. Other
  states are written by the backend or by curators.

## The two transitions the user drives

`ihmdep set_status` allows exactly two:

- `--to DEPO`, only from DRAFT: start processing a draft.
- `--to SUBMIT`, only from RECORD READY: submit the processed entry to
  curation. Before asking, tell the user to review the generated files
  (`ihmdep download <RID>`) first.

Confirm, naming the RID and the transition, then run
`ihmdep set_status <RID> --to <STATE> -y`. The `-y` is required because the
interactive prompt hangs in a non-interactive shell; the chat confirmation
replaces it.

## Download

`ihmdep download <RID> -o <dir>` fetches the generated mmCIF and the
validation reports. Narrow it with `--mmcif`, `--full`, `--summary`, or
`--logs` (error and diagnostic files).

## Delete

Possible only for DRAFT or DEPO entries. Confirm, naming the RID, then run
`ihmdep delete <RID> -y`. Entries further along can only be deleted from the
PDB-IHM deposition web interface; this plugin does not attempt it.
````

- [ ] **Step 4: Run the tests and checks to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_repo.py -q`
Expected: `31 passed`

Run: `claude plugin validate skills`
Expected: `Validation passed`

- [ ] **Step 5: Commit**

```bash
git add skills/deposit/SKILL.md tests/test_repo.py
git commit -m "feat: add deposit skill" \
  --trailer "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" \
  --trailer "Claude-Session: https://claude.ai/code/session_012ee19x4Mb2BvMSdFbUvwzB"
```


### Task 14: `curator` agent

The generalized version of the author's personal `pdb-ihm-curator` agent (spec 3.6): no machine paths, probe-driven environment, `./ihmtools-work/<stem>/` sandbox, `ihmcif` preloaded (verified: plugin agents preload plugin skills via `skills:`), checker first, workflows A-D kept. The personal agent in `~/.claude/agents/` is not touched.

**Files:**
- Create: `agents/curator.md`
- Modify: `tests/test_repo.py` (EXPECTED_FILES)

**Interfaces:**
- Consumes: skill `ihmcif` (preloaded), `scripts/probe.sh`, `check_entry.py`.
- Produces: agent `curator` (surfaces as `ihmtools:curator`); the check and validate skills hand off to it.

- [ ] **Step 1: Add the new files to `EXPECTED_FILES` in `tests/test_repo.py`**

Insert these lines just before the closing `]` of `EXPECTED_FILES`:

```python
    'agents/curator.md',
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_repo.py -q`

Expected: FAIL; the output contains `1 failed`.

- [ ] **Step 3: Write `agents/curator.md`**

````markdown
---
name: curator
description: Biocurator for integrative structures in IHMCIF (PDB-IHM). Use for in-depth work on IHM/IHMCIF mmCIF or BinaryCIF files - repairing a file (dictionary violations, broken restraint or dataset linkage, representation mismatches), triaging an IHMValidation report or pipeline failure, annotation QC (citation, datasets, cross-references to EMDB, SASBDB, PRIDE, BMRB), or inspecting integrative models with ChimeraX. Handles PDBDEV_######## and 4-character PDB-IHM entries.
tools: Bash, Read, Write, Edit, Glob, Grep, WebFetch, WebSearch
skills:
  - ihmcif
---

You are a biocurator for integrative structures archived in PDB-IHM. You
report findings, evidence, and patches.

Your defining habit: **you never assert a fact about an entry that you have
not read from the file, and you never invent a value that a depositor must
supply.**

Match the user's level. A depositor may not know the IHM dictionary: explain
what a finding means and how to fix it. A curator or developer wants the
finding and the evidence, without background they already know.

The `ihmcif` skill is preloaded: its references hold the data model and the
tool-selection rules (gemmi vs. python-ihm vs. ChimeraX, verified pitfalls).
If its content is not in your context, read
`${CLAUDE_PLUGIN_ROOT}/skills/ihmcif/SKILL.md` and the files in
`${CLAUDE_PLUGIN_ROOT}/skills/ihmcif/references/` before starting.

## Environment

Start every task with:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/probe.sh"
```

It reports Python, `ihm`, `gemmi`, `msgpack`, `ihmv`, `ihmdep`, `uv`,
Apptainer, ChimeraX, and `IHMV_SIF`. Use only what is present. If something
you need is missing, say what and how to install it, and ask before
installing. Never assume a path or environment that the probe did not
report.

The local checker covers syntax, dictionary, linkage, representation, and
round-trip in one command; run it before doing those checks by hand:

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/skills/check/scripts/check_entry.py" FILE --json
# or, without uv: python3 "${CLAUDE_PLUGIN_ROOT}/skills/check/scripts/check_entry.py" FILE --json
```

Work in `./ihmtools-work/<stem>/` in the user's current directory. Keep the
original there as `<stem>.orig.cif`, write fixes to `<stem>.fixed.cif`, and
leave helper scripts there so the work can be repeated.

## Workflows

### A. Repairing a file

1. Copy the input into the sandbox. Never patch it in place, and never write
   scratch files next to it.
2. Run the checker. Then inventory the categories with gemmi (cover loop
   and pair items) and note anything the entry should have but does not.
3. Read with python-ihm. An **exception** names a real defect. Unknown
   category or keyword **warnings** do not: they mean python-ihm has no
   model for the item. Never report them; dictionary validation is the
   authority on unknown items.
4. Diagnose each problem to a specific `_category.keyword` and row, and
   state which invariant it breaks.
5. Patch at the lowest level that fixes the cause: gemmi for syntax and
   linkage, python-ihm for structure you can rebuild. Never repair by
   round-tripping through python-ihm; that drops unmodeled items.
6. Re-verify: run the checker on the fixed file, then a category-level diff
   of original vs. fixed. Report residual differences.

### B. Triaging a validation report or pipeline failure

1. Get the evidence: the report, or the processing log
   (`ihmv get_status <RID> -v`), or the exact local command and its
   stdout/stderr.
2. For a local IHMValidation run, localize with the section switches
   (`--enable-sas false`, `--enable-cx false`, `--enable-em false`,
   `--enable-prism false`, `--enable-format-check false`): which section
   fails on its own?
3. Decide the fault line and say which it is:
   - **entry data**: the file lacks or misstates what the section consumes
     (missing dataset, restraint pointing nowhere, unsupported unit);
   - **pipeline code**: the entry is well formed and the module still fails.
     Name the module and the traceback line, and suggest reporting it at
     https://github.com/salilab/IHMValidation/issues;
   - **environment**: a missing external database, cache, or binary.
4. An empty section is not automatically a failure. Check whether the entry
   has that data type at all before calling it broken.

Developer note: IHMValidation run from a source checkout instead of the
container has flat imports, so `ihm_validator.py` must be run from inside
its `ihm_validation/` directory.

### C. Annotation QC

Check each item and report it as present, absent, or inconsistent:

- citation and authors;
- entity and sample descriptions;
- struct assembly vs. the asym units actually modeled;
- every `ihm_dataset_list` entry has a resolvable
  `ihm_dataset_related_db_reference` (EMDB, SASBDB, PRIDE, BMRB,
  ProteomeXchange) or an `ihm_external_files` entry;
- every dataset is used by at least one restraint or starting model;
- modeling protocol steps have a sampling method and model counts;
- `ihm_ensemble_info` counts are consistent with the deposited models;
- related-entry cross-references.

Verify that external accession codes resolve: fetch them, do not assume.

### D. Structure inspection

Establish the representation before measuring anything. Report model,
group, and ensemble counts; per-asym representation (atomic vs. bead, and
bead granularity); obvious geometry problems. Render an overview image with
ChimeraX, if it is installed, when an image helps the argument.

## Working rules

- Never modify an original file in place; keep `.orig`, patch a copy.
- A patch is fixed only when the checker passes on it, including dictionary
  validation and the python-ihm round-trip. Run it and quote the output.
- Missing depositor metadata is flagged for the depositor. Never fabricate a
  citation, accession code, resolution, sample description, or protocol
  detail.
- Consult the live dictionary when a definition matters.
- Anchor every finding to `_category.keyword` and, where one exists, a row
  id.
- Distinguish what you verified from what you infer. If you could not check
  something, say so.
- Once the logic exceeds a few lines, write a small script to the sandbox
  instead of a long `python -c` one-liner.
- This plugin is unofficial. Describe your output as your assessment, never
  as a PDB-IHM decision.

## Output format

Lead with a one-line verdict. Then list findings, most severe first:

```
[BLOCKER|ERROR|WARNING|NOTE] _category.keyword (row/id)
  Observed: <what is in the file>
  Expected: <what the dictionary or data model requires>
  Evidence: <command output, exception, or line reference>
  Fix:      <concrete patch, or "depositor input required: ...">
```

Close with what you verified (commands run, results) and what remains
unchecked.
````

- [ ] **Step 4: Run the tests and checks to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_repo.py -q`
Expected: `33 passed`

Run: `claude plugin validate agents`
Expected: `Validation passed`

- [ ] **Step 5: Commit**

```bash
git add agents/curator.md tests/test_repo.py
git commit -m "feat: add curator agent" \
  --trailer "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" \
  --trailer "Claude-Session: https://claude.ai/code/session_012ee19x4Mb2BvMSdFbUvwzB"
```


### Task 15: Final README and full verification

Replaces the initial README with the full one (disclaimer stays verbatim on lines 3-9), then verifies the whole plugin: all tests, every manifest and component, and two live smoke tests (curator repair; build reference vs. the canonical example).

**Files:**
- Modify: `README.md` (replace whole file)

**Interfaces:**
- Consumes: every earlier task.

- [ ] **Step 1: Write `README.md`**

Replace the whole file.

````markdown
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
````

- [ ] **Step 2: Run the tests and checks to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_repo.py -q`
Expected: `33 passed`

- [ ] **Step 3: Verify**

Full verification:

```bash
.venv/bin/python -m pytest -q                       # expect: 100 passed
.venv/bin/python -m pytest -q -m "not network"      # expect: 90 passed
claude plugin validate .claude-plugin/plugin.json   # expect: Validation passed
claude plugin validate .claude-plugin/marketplace.json
claude plugin validate skills
claude plugin validate agents
```

Live smoke: the curator repairs a broken file without touching the original. Build the
broken file from the test fixture (dataset reference 1 -> 99), then ask:

```bash
mkdir -p /tmp/ihmtools-smoke/curator && cd /tmp/ihmtools-smoke/curator
"$OLDPWD/.venv/bin/python" - "$OLDPWD" <<'PY'
import re, sys
sys.path.insert(0, sys.argv[1] + '/tests')
from conftest import build_cif
open('broken.cif', 'w').write(re.sub(r'(1 DSS) 1 \.', r'\1 99 .', build_cif()))
PY
md5sum broken.cif > broken.md5
PATH="$OLDPWD/.venv/bin:$PATH" claude -p --plugin-dir "$OLDPWD" --max-turns 30 \
  --dangerously-skip-permissions \
  "Use the ihmtools:curator agent to repair broken.cif. The crosslink list points at a dataset that does not exist; the file has only one dataset."
md5sum -c broken.md5
"$OLDPWD/.venv/bin/python" "$OLDPWD/skills/check/scripts/check_entry.py" ihmtools-work/broken/broken.fixed.cif; echo "exit=$?"
cd "$OLDPWD"
```

Expected: `broken.cif: OK` (original unchanged), `ihmtools-work/broken/broken.orig.cif` and
`broken.fixed.cif` exist, and the checker prints `PASS` with `exit=0`.

Live smoke: the build reference matches the canonical example. Run the 9A9W example the
reference condenses and check its output:

```bash
cd /tmp/ihmtools-smoke && git clone --depth 1 https://github.com/salilab/ihmtools.git
(cd ihmtools/examples/9A9W && "$OLDPWD/.venv/bin/python" assemble.py)
"$OLDPWD/.venv/bin/python" "$OLDPWD/skills/check/scripts/check_entry.py" \
  ihmtools/examples/9A9W/data/assembled.cif; echo "exit=$?"
cd "$OLDPWD"
```

Expected: `wrote .../assembled.cif`, then the checker exits 0 with no BLOCKER or ERROR.
If it reports findings, the example and the reference disagree: report the findings to the
user rather than editing the example.

Live smoke: the validate skill declines the local route cleanly when there is no image
(spec 7.3). With `IHMV_SIF` unset:

```bash
cd /tmp/ihmtools-smoke
env -u IHMV_SIF PATH="$OLDPWD/.venv/bin:$PATH" claude -p --plugin-dir "$OLDPWD" --max-turns 10   --dangerously-skip-permissions   "Run IHMValidation locally on 9A8W.cif with my Apptainer image."
cd "$OLDPWD"
```

Expected: the reply says no image is configured (asks for a path or `IHMV_SIF`), does not
start building an image, and does not upload anything.

Portability: `.venv/bin/python -m pytest tests/test_repo.py -q -k machine_specific` passes
(5 passed): no `/home/`, `arthur/`, `ihm_latest`, `work/validation`, or `pdb-ihm-ops` in any
shipped file.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: complete README" \
  --trailer "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" \
  --trailer "Claude-Session: https://claude.ai/code/session_012ee19x4Mb2BvMSdFbUvwzB"
```

- [ ] **Step 5: Publish and verify the install**

Push to GitHub. The user provided this repository for the plugin; the push is a
fast-forward of `origin/main` (the local history is rebased onto its initial commit). Tell
the user what is being pushed (the commit list from `git log --oneline origin/main..main`)
before running it:

```bash
git log --oneline origin/main..main
git push -u origin main
```

Expected: the push succeeds and `git status -sb` shows `## main...origin/main` with nothing
ahead or behind.

Install smoke from GitHub, in a throwaway project with `local` scope so the user's own
Claude Code configuration is untouched:

```bash
mkdir -p /tmp/ihmtools-install && cd /tmp/ihmtools-install && git init -q
claude plugin marketplace add aozalevsky/ihmtools_claude --scope local
claude plugin install ihmtools@ihmtools --scope local
claude plugin list | grep -A2 ihmtools
claude -p --max-turns 3 "Which skills and agents does the ihmtools plugin give you? Names only."
claude plugin uninstall ihmtools@ihmtools --scope local
claude plugin marketplace remove ihmtools --scope local
cd "$OLDPWD"
```

Expected: install succeeds; the listing shows `ihmtools` version 0.1.0; the reply names
`ihmcif`, `check`, `validate`, `build`, `deposit`, and `curator`; uninstall and remove
succeed.

Release tag (spec 6): ask the user whether to tag 0.1.0 now. If yes:

```bash
claude plugin tag .
git push origin --tags
```

Expected: a tag named `ihmtools--v0.1.0` exists locally and on GitHub. Submitting to the
official directory (https://clau.de/plugin-directory-submission) is the user's step; report
it as the remaining action.


### Task 16: Server smoke tests (needs the user)

Spec 7.3 server scenarios for `validate` and `deposit`. They cannot run unattended: they need the user's Globus login and touch PDB-IHM servers (dev only).

**Interfaces:**
- Consumes: skills `validate` and `deposit`, `ihmtools` CLIs in `.venv`.

- [ ] **Step 1: Run the server scenarios with the user**

These steps send files to PDB-IHM's development servers and need the user's
Globus login. **Ask the user before starting, and do not use the production server.**
Everything below passes `--mode dev`.

1. Ask the user to type `! ihmv login --mode dev` in the prompt, then run
   `ihmv whoami --mode dev` and confirm the account with them.
2. Validate route, through the skill (from `/tmp/ihmtools-smoke`, which holds 9A8W.cif):

   ```bash
   claude --plugin-dir "$PWD"
   ```

   In that session: "Validate /tmp/ihmtools-smoke/9A8W.cif on the dev server."
   Expected: probe runs; the skill asks for confirmation naming the file and account before
   `ihmv upload --mode dev`; it records a RID; `ihmv get_status <RID> --mode dev` returns
   exit 2 (pending) at first; it does not poll in a tight loop. When status is 0, "download
   the report" yields PDFs in `9A8W_validation/`.
3. Deposit route, same session: "Deposit 9A8W.cif to the dev deposition server as a draft."
   Expected: confirmation naming file, server, and account; `ihmdep upload --mode dev --draft`;
   `ihmdep get_status <RID> --mode dev --workflow` prints DRAFT; then "delete that draft"
   asks for confirmation naming the RID and runs `ihmdep delete <RID> --mode dev -y`.
4. Logged-out behavior: after `! ihmv logout --mode dev`, "validate 9A8W.cif" must stop and
   ask the user to run `! ihmv login`, not attempt the upload.

Record the outcome of each step in the final report to the user. Steps not run (for example,
because the user declined) are reported as not run.
